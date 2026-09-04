from collections import Counter
from statistics import mean
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.event import SurgicalEvent
from app.models.video import AnalysisSession, Detection, Video
from app.services.phase_recognition import serialize_phase
from app.services.instrument_intelligence import get_instrument_intelligence


def _per_minute(value: int | float | None, duration: float | None) -> float | None:
    if value is None or not duration or duration <= 0:
        return None
    return value / (duration / 60.0)


def _difference(left: int | float | None, right: int | float | None) -> dict[str, float | None]:
    if left is None or right is None:
        return {"absolute": None, "relative_to_a_percent": None}
    absolute = right - left
    return {
        "absolute": absolute,
        "relative_to_a_percent": (absolute / left) * 100 if left else None,
    }


def _metric_pair(left: int | float | None, right: int | float | None, duration_a: float | None, duration_b: float | None) -> dict[str, Any]:
    return {
        "a": left,
        "b": right,
        "difference": _difference(left, right),
        "per_minute": {
            "a": _per_minute(left, duration_a),
            "b": _per_minute(right, duration_b),
            "difference": _difference(_per_minute(left, duration_a), _per_minute(right, duration_b)),
        },
    }


def _procedure_payload(video: Video, analysis: AnalysisSession, intelligence: dict[str, Any], events: list[SurgicalEvent]) -> dict[str, Any]:
    return {
        "video_id": str(video.id),
        "analysis_id": str(analysis.id),
        "title": video.title,
        "duration": video.duration,
        "analysis_version": analysis.analysis_version,
        "model_version": analysis.model_version,
        "processed_at": analysis.processed_at,
        "detection_count": intelligence["detection_count"],
        "track_count": intelligence["track_count"],
        "event_count": len(events),
        "instrument_count": intelligence["instrument_count"],
        "co_occurrence_count": len(intelligence["co_occurrences"]),
        "average_detection_confidence": None,
        "instruments": intelligence["instruments"],
        "events": [_serialize_event(event) for event in events],
        "phases": [serialize_phase(phase) for phase in analysis.phases],
        "phase_model_provider": next((phase.model_provider for phase in analysis.phases if phase.model_provider), None),
        "phase_model_version": next((phase.model_version for phase in analysis.phases if phase.model_version), None),
        "phase_taxonomy_version": next((phase.taxonomy_version for phase in analysis.phases if phase.taxonomy_version), None),
    }


def _event_counts(events: list[SurgicalEvent]) -> Counter:
    return Counter(event.event_type for event in events)


def _serialize_event(event: SurgicalEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "event_type": event.event_type,
        "start_time": event.start_time,
        "end_time": event.end_time,
        "confidence": event.confidence,
        "metadata": event.event_metadata,
        "evidence": event.evidence,
        "model_version": event.model_version,
    }


def compare_procedures(db: Session, video_a: Video, analysis_a: AnalysisSession, video_b: Video, analysis_b: AnalysisSession) -> dict[str, Any]:
    intelligence_a = get_instrument_intelligence(db, analysis_a)
    intelligence_b = get_instrument_intelligence(db, analysis_b)
    events_a = db.query(SurgicalEvent).filter(SurgicalEvent.analysis_id == analysis_a.id).order_by(SurgicalEvent.start_time).all()
    events_b = db.query(SurgicalEvent).filter(SurgicalEvent.analysis_id == analysis_b.id).order_by(SurgicalEvent.start_time).all()
    detections_a = db.query(Detection).filter(Detection.analysis_id == analysis_a.id).all()
    detections_b = db.query(Detection).filter(Detection.analysis_id == analysis_b.id).all()
    average_a = mean([detection.confidence for detection in detections_a]) if detections_a else None
    average_b = mean([detection.confidence for detection in detections_b]) if detections_b else None

    procedure_a = _procedure_payload(video_a, analysis_a, intelligence_a, events_a)
    procedure_b = _procedure_payload(video_b, analysis_b, intelligence_b, events_b)
    procedure_a["average_detection_confidence"] = average_a
    procedure_b["average_detection_confidence"] = average_b
    phase_models_compatible = (
        procedure_a["phase_model_provider"] == procedure_b["phase_model_provider"]
        and procedure_a["phase_model_version"] == procedure_b["phase_model_version"]
        and procedure_a["phase_taxonomy_version"] == procedure_b["phase_taxonomy_version"]
        and procedure_a["phase_model_version"] is not None
    )

    overview_fields = {
        "duration": (video_a.duration, video_b.duration),
        "total_detections": (intelligence_a["detection_count"], intelligence_b["detection_count"]),
        "total_tracks": (intelligence_a["track_count"], intelligence_b["track_count"]),
        "total_events": (len(events_a), len(events_b)),
        "instrument_classes": (intelligence_a["instrument_count"], intelligence_b["instrument_count"]),
        "co_occurrences": (len(intelligence_a["co_occurrences"]), len(intelligence_b["co_occurrences"])),
        "average_detection_confidence": (average_a, average_b),
    }
    overview = {
        field: _metric_pair(left, right, video_a.duration, video_b.duration)
        for field, (left, right) in overview_fields.items()
    }

    by_instrument = {
        item["class_name"]: item
        for item in intelligence_a["instruments"] + intelligence_b["instruments"]
    }
    instrument_rows = []
    for class_name in sorted(by_instrument):
        left = next((item for item in intelligence_a["instruments"] if item["class_name"] == class_name), None)
        right = next((item for item in intelligence_b["instruments"] if item["class_name"] == class_name), None)
        metrics = {}
        for field in ("detection_count", "track_count", "visible_duration", "activity_segment_count", "average_confidence", "peak_confidence", "first_seen", "last_seen"):
            metrics[field] = _metric_pair(left.get(field) if left else None, right.get(field) if right else None, video_a.duration, video_b.duration)
        instrument_rows.append({"class_name": class_name, **metrics})

    counts_a = _event_counts(events_a)
    counts_b = _event_counts(events_b)
    event_types = sorted(set(counts_a) | set(counts_b))
    event_rows = [
        {
            "event_type": event_type,
            "count": _metric_pair(counts_a.get(event_type, 0), counts_b.get(event_type, 0), video_a.duration, video_b.duration),
        }
        for event_type in event_types
    ]

    pair_counts_a = Counter(tuple(sorted((event.event_metadata or {}).get("instruments", []))) for event in events_a if event.event_type == "INSTRUMENT_CO_OCCURRENCE")
    pair_counts_b = Counter(tuple(sorted((event.event_metadata or {}).get("instruments", []))) for event in events_b if event.event_type == "INSTRUMENT_CO_OCCURRENCE")
    pairs = sorted(set(pair_counts_a) | set(pair_counts_b))
    cooccurrence_rows = [
        {
            "instruments": list(pair),
            "count": _metric_pair(pair_counts_a.get(pair, 0), pair_counts_b.get(pair, 0), video_a.duration, video_b.duration),
            "timestamps": {
                "a": [event.start_time for event in events_a if event.event_type == "INSTRUMENT_CO_OCCURRENCE" and tuple(sorted((event.event_metadata or {}).get("instruments", []))) == pair],
                "b": [event.start_time for event in events_b if event.event_type == "INSTRUMENT_CO_OCCURRENCE" and tuple(sorted((event.event_metadata or {}).get("instruments", []))) == pair],
            },
        }
        for pair in pairs if pair
    ]

    highlights = []
    total_event_diff = len(events_b) - len(events_a)
    if total_event_diff:
        highlights.append(f"Procedure B contains {abs(total_event_diff)} {'more' if total_event_diff > 0 else 'fewer'} persisted events.")
    for row in instrument_rows:
        difference = row["visible_duration"]["difference"]["absolute"]
        if difference:
            highlights.append(f"{row['class_name']} visible duration is {abs(difference):.2f} seconds {'higher' if difference > 0 else 'lower'} in Procedure B.")
        left_exists = row["detection_count"]["a"] not in (None, 0)
        right_exists = row["detection_count"]["b"] not in (None, 0)
        if left_exists != right_exists:
            highlights.append(f"{row['class_name']} detections are present in Procedure {'A' if left_exists else 'B'} only.")

    return {
        "procedure_a": procedure_a,
        "procedure_b": procedure_b,
        "overview": overview,
        "instruments": instrument_rows,
        "events": event_rows,
        "co_occurrences": cooccurrence_rows,
        "phases": {
            "available": phase_models_compatible,
            "reason": None if phase_models_compatible else "Phase comparison unavailable because the phase model/taxonomy differs.",
            "a": procedure_a["phases"] if phase_models_compatible else [],
            "b": procedure_b["phases"] if phase_models_compatible else [],
        },
        "timeline": {
            "a": {"activity": [{"instrument": item["class_name"], "segments": item["activity_segments"]} for item in intelligence_a["instruments"]], "events": [_serialize_event(event) for event in events_a]},
            "b": {"activity": [{"instrument": item["class_name"], "segments": item["activity_segments"]} for item in intelligence_b["instruments"]], "events": [_serialize_event(event) for event in events_b]},
        },
        "model_versions_differ": analysis_a.model_version != analysis_b.model_version,
        "analysis_versions_differ": analysis_a.analysis_version != analysis_b.analysis_version,
        "highlights": highlights[:12],
        "limitations": [
            "Comparison reflects model-derived video intelligence only.",
            "Higher or lower detected activity does not establish clinical quality, safety, success, or surgical correctness.",
        ],
    }
