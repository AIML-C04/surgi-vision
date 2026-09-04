import re
from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.event import SurgicalEvent
from app.models.evaluation import EvaluationRun
from app.models.video import AnalysisSession, Detection, SurgicalPhase, Video
from app.services.instrument_intelligence import get_instrument_intelligence


def _parse_timestamp(query: str) -> float | None:
    match = re.search(r"(?<!\d)(?:(\d+)\s*:\s*)?(\d+(?:\.\d+)?)\s*(?:seconds?|secs?|s)?(?!\d)", query.lower())
    if not match:
        return None
    minutes = float(match.group(1) or 0)
    seconds = float(match.group(2))
    return minutes * 60 + seconds if match.group(1) else seconds


def classify_query(query: str) -> list[str]:
    text = query.lower()
    intents = []
    if any(term in text for term in ("instrument", "grasper", "hook", "clipper", "scissors", "forceps")):
        intents.append("instrument")
    if any(term in text for term in ("event", "happened", "occurred", "entered", "removed")):
        intents.append("event")
    if any(term in text for term in ("together", "co-occurrence", "simultaneously")):
        intents.append("co-occurrence")
    if _parse_timestamp(text) is not None or any(term in text for term in ("around", "at ")):
        intents.append("timestamp")
    if any(term in text for term in ("how long", "duration", "longest", "active", "visible")):
        intents.append("duration")
    if any(term in text for term in ("confidence", "highest", "lowest")):
        intents.append("confidence")
    if any(term in text for term in ("track", "track instances")):
        intents.append("track")
    if any(term in text for term in ("summarize", "summary", "what happened during", "procedure")):
        intents.append("summary")
    if any(term in text for term in ("compare", "difference")):
        intents.append("comparison")
    if any(term in text for term in ("phase", "stage", "workflow")):
        intents.append("phase")
    if any(term in text for term in ("what is", "what are", "used for", "definition")):
        intents.append("descriptive_knowledge")
    return intents or ["unsupported"]


def _evidence(*, evidence_id: str, video_id: UUID, analysis_id: UUID, evidence_type: str, source: str, start_time: float, end_time: float | None = None, confidence: float | None = None, **fields: Any) -> dict[str, Any]:
    result = {
        "evidence_id": evidence_id,
        "video_id": str(video_id),
        "analysis_id": str(analysis_id),
        "type": evidence_type,
        "start_time": start_time,
        "end_time": end_time if end_time is not None else start_time,
        "confidence": confidence,
        "source": source,
    }
    result.update(fields)
    return result


def retrieve_copilot_evidence(db: Session, video_id: UUID, user_id: UUID, query: str, limit: int = 24, selected_context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Retrieve compact, authorized structured evidence for one Copilot question."""
    video = db.query(Video).filter(Video.id == video_id, Video.user_id == user_id).first()
    if not video:
        raise ValueError("Video not found")
    analysis = (
        db.query(AnalysisSession)
        .filter(AnalysisSession.video_id == video.id, AnalysisSession.status == "completed")
        .order_by(AnalysisSession.created_at.desc())
        .first()
    )
    if not analysis:
        if selected_context:
            raise ValueError("Selected context requires a completed analysis for this video")
        return {"analysis": None, "evidence": [], "context": "No completed analysis is available for this video."}

    query_lower = query.lower()
    evidence: list[dict[str, Any]] = []
    phase_question = any(term in query_lower for term in ("phase", "stage", "workflow"))
    evaluation_question = any(term in query_lower for term in ("precision", "recall", "f1", "map", "accuracy", "evaluation", "ground truth"))
    if evaluation_question:
        run = db.query(EvaluationRun).filter(EvaluationRun.analysis_id == analysis.id, EvaluationRun.user_id == user_id, EvaluationRun.status == "completed").order_by(EvaluationRun.created_at.desc()).first()
        if not run:
            return {"analysis": {"id": str(analysis.id), "model_version": analysis.model_version}, "intents": classify_query(query), "evidence": [], "context": "Evaluation is unavailable because no evaluation run exists for this analysis.", "evaluation_unavailable": True, "evaluation_reason": "Evaluation is unavailable because no evaluation run exists for this analysis."}
        detection_metrics = (run.metrics or {}).get("detection", {})
        if detection_metrics.get("status") == "unavailable":
            return {"analysis": {"id": str(analysis.id), "model_version": analysis.model_version}, "intents": classify_query(query), "evidence": [], "context": detection_metrics.get("reason", "Evaluation is unavailable."), "evaluation_unavailable": True, "evaluation_reason": detection_metrics.get("reason", "Evaluation is unavailable.")}
        evidence.append(_evidence(
            evidence_id=f"evaluation:{run.id}", video_id=video.id, analysis_id=analysis.id,
            evidence_type="evaluation", source="persisted_evaluation_run", start_time=0,
            confidence=None, evaluation_run_id=str(run.id), metrics=run.metrics,
            dataset_id=str(run.dataset_id), model_version=run.model_version,
        ))
    phases = db.query(SurgicalPhase).filter(SurgicalPhase.analysis_id == analysis.id).order_by(SurgicalPhase.start_time).all()
    if phase_question and not phases:
        return {"analysis": {"id": str(analysis.id), "model_version": analysis.model_version}, "intents": classify_query(query), "evidence": [], "context": "Phase recognition is not available for this analysis.", "phase_unavailable": True}
    if phase_question:
        for phase in phases:
            evidence.append(_evidence(
                evidence_id=f"phase:{phase.id}", video_id=video.id, analysis_id=analysis.id,
                evidence_type="phase", source="persisted_phase_recognition", phase_name=phase.name,
                start_time=phase.start_time, end_time=phase.end_time, confidence=phase.confidence,
                model_provider=phase.model_provider, model_version=phase.model_version,
                taxonomy_version=phase.taxonomy_version, phase_evidence=phase.evidence or [],
            ))
    timestamp = _parse_timestamp(query)
    events_query = db.query(SurgicalEvent).filter(SurgicalEvent.analysis_id == analysis.id).order_by(SurgicalEvent.start_time)
    events = events_query.all()
    if selected_context:
        context_type = selected_context.get("type")
        selected_event = None
        if context_type == "event":
            try:
                selected_event = db.query(SurgicalEvent).filter(
                    SurgicalEvent.id == UUID(str(selected_context.get("event_id"))),
                    SurgicalEvent.video_id == video.id,
                    SurgicalEvent.analysis_id == analysis.id,
                ).first()
            except (TypeError, ValueError):
                selected_event = None
            if not selected_event:
                raise ValueError("Selected event is not part of the latest completed analysis")
            metadata = selected_event.event_metadata or {}
            evidence.append(_evidence(
                evidence_id=f"event:{selected_event.id}", video_id=video.id, analysis_id=analysis.id,
                evidence_type="selected_event", source="selected_timeline_context",
                event_id=str(selected_event.id), event_type=selected_event.event_type,
                instrument=metadata.get("instrument"), instruments=metadata.get("instruments", []),
                start_time=selected_event.start_time, end_time=selected_event.end_time,
                confidence=selected_event.confidence,
                frame_ids=(selected_event.evidence or {}).get("frame_ids", []),
                detection_ids=(selected_event.evidence or {}).get("detection_ids", []),
                track_ids=(selected_event.evidence or {}).get("track_ids", []), model_version=selected_event.model_version,
            ))
        elif context_type == "segment":
            instrument = selected_context.get("instrument")
            start = float(selected_context.get("start_time"))
            end = float(selected_context.get("end_time"))
            intelligence = get_instrument_intelligence(db, analysis)
            item = next((item for item in intelligence["instruments"] if item["class_name"] == instrument), None)
            segment = next((segment for segment in (item or {}).get("activity_segments", []) if abs(segment["start_time"] - start) < 0.01 and abs(segment["end_time"] - end) < 0.01), None)
            if not item or not segment:
                raise ValueError("Selected instrument segment is not part of the latest completed analysis")
            evidence.append(_evidence(
                evidence_id=f"instrument:{analysis.id}:{instrument}", video_id=video.id, analysis_id=analysis.id,
                evidence_type="selected_segment", source="selected_timeline_context", instrument=instrument,
                start_time=segment["start_time"], end_time=segment["end_time"],
                track_ids=[track["track_id"] for track in item["tracks"]], model_version=analysis.model_version, summary=item,
            ))
        else:
            raise ValueError("Unsupported selected context type")

    event_question = any(term in query_lower for term in ("event", "happened", "occurred", "co-occurrence", "together", "removed", "entered"))
    if timestamp is not None:
        events = [event for event in events if event.start_time <= timestamp + 5 and event.end_time >= timestamp - 5]
        detections = (
            db.query(Detection)
            .filter(
                Detection.analysis_id == analysis.id,
                Detection.timestamp >= max(0, timestamp - 5),
                Detection.timestamp <= timestamp + 5,
            )
            .order_by(Detection.timestamp)
            .limit(limit)
            .all()
        )
        grouped: dict[str, list[Detection]] = defaultdict(list)
        for detection in detections:
            grouped[detection.class_name].append(detection)
        for instrument, rows in grouped.items():
            evidence.append(_evidence(
                evidence_id=f"detection-window:{analysis.id}:{instrument}:{timestamp:.3f}",
                video_id=video.id,
                analysis_id=analysis.id,
                evidence_type="detection_window",
                source="structured_video_intelligence",
                instrument=instrument,
                start_time=rows[0].timestamp,
                end_time=rows[-1].timestamp,
                confidence=sum(row.confidence for row in rows) / len(rows),
                frame_ids=[row.frame_id for row in rows],
                detection_ids=[str(row.id) for row in rows],
                track_ids=sorted({row.track_id for row in rows if row.track_id is not None}),
                model_version=analysis.model_version,
            ))
    elif event_question:
        events = events[:min(12, limit)]
    else:
        events = []

    for event in events[:limit]:
        metadata = event.event_metadata or {}
        evidence.append(_evidence(
            evidence_id=f"event:{event.id}",
            video_id=video.id,
            analysis_id=analysis.id,
            evidence_type="event",
            source="structured_video_intelligence",
            event_id=str(event.id),
            event_type=event.event_type,
            instrument=metadata.get("instrument"),
            instruments=metadata.get("instruments", []),
            start_time=event.start_time,
            end_time=event.end_time,
            confidence=event.confidence,
            frame_ids=(event.evidence or {}).get("frame_ids", []),
            detection_ids=(event.evidence or {}).get("detection_ids", []),
            track_ids=(event.evidence or {}).get("track_ids", []),
            model_version=event.model_version,
        ))

    if any(term in query_lower for term in ("instrument", "grasper", "hook", "clipper", "scissors", "forceps", "longest", "detections", "active", "visible")) or not evidence:
        intelligence = get_instrument_intelligence(db, analysis)
        for item in intelligence["instruments"]:
            if item["class_name"].lower() not in query_lower and any(name in query_lower for name in ("grasper", "hook", "clipper", "scissors", "forceps")):
                continue
            evidence.append(_evidence(
                evidence_id=f"instrument:{analysis.id}:{item['class_name']}",
                video_id=video.id,
                analysis_id=analysis.id,
                evidence_type="instrument_summary",
                source="structured_video_intelligence",
                instrument=item["class_name"],
                start_time=item["first_seen"],
                end_time=item["last_seen"],
                confidence=item["average_confidence"],
                track_ids=[track["track_id"] for track in item["tracks"]],
                model_version=analysis.model_version,
                summary=item,
            ))

    deduplicated = []
    seen = set()
    for item in evidence:
        if item["evidence_id"] not in seen:
            seen.add(item["evidence_id"])
            deduplicated.append(item)
    deduplicated = deduplicated[:limit]

    context_lines = []
    for item in deduplicated:
        context_lines.append(
            f"EVIDENCE_ID={item['evidence_id']} TYPE={item['type']} "
            f"TIME={item['start_time']:.2f}-{item['end_time']:.2f} "
            f"CONFIDENCE={item['confidence']} DATA={item}"
        )
    context = "\n".join(context_lines) or "No structured evidence matched this question."
    return {
        "analysis": {"id": str(analysis.id), "model_version": analysis.model_version},
        "intents": classify_query(query),
        "evidence": deduplicated,
        "context": context,
    }
