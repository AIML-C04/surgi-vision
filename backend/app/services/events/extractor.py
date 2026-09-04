from collections import defaultdict
from statistics import mean, median
from typing import Iterable
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.event import SurgicalEvent
from app.models.video import AnalysisSession, Detection, Track


def _gap_threshold(timestamps: Iterable[float]) -> float:
    gaps = [
        current - previous
        for previous, current in zip(sorted(set(timestamps)), sorted(set(timestamps))[1:])
        if current > previous
    ]
    if not gaps:
        return 0.0
    # Derive the grouping window from observed sampling cadence, not a fixed second.
    return median(gaps) * 3.0


def _group_by_temporal_gap(items: list, timestamp_getter) -> list[list]:
    if not items:
        return []
    ordered = sorted(items, key=timestamp_getter)
    threshold = _gap_threshold([timestamp_getter(item) for item in ordered])
    groups = [[ordered[0]]]
    for item in ordered[1:]:
        if threshold <= 0 or timestamp_getter(item) - timestamp_getter(groups[-1][-1]) <= threshold:
            groups[-1].append(item)
        else:
            groups.append([item])
    return groups


def _evidence(detections: list[Detection], track_ids: list[int] | None, model_version: str | None) -> dict:
    return {
        "timestamps": [d.timestamp for d in detections],
        "frame_ids": [d.frame_id for d in detections],
        "detection_ids": [str(d.id) for d in detections],
        "track_ids": track_ids or [],
        "model_version": model_version,
    }


def _event(
    *,
    analysis: AnalysisSession,
    event_type: str,
    start_time: float,
    end_time: float,
    detections: list[Detection],
    metadata: dict,
    track_ids: list[int] | None = None,
    dedupe_key: str,
) -> SurgicalEvent:
    track_ids = track_ids or []
    return SurgicalEvent(
        video_id=analysis.video_id,
        analysis_id=analysis.id,
        event_type=event_type,
        start_time=start_time,
        end_time=end_time,
        confidence=mean([d.confidence for d in detections]) if detections else None,
        event_metadata=metadata,
        evidence=_evidence(detections, track_ids, analysis.model_version),
        source_detection_ids=[str(d.id) for d in detections],
        source_track_ids=[str(track_id) for track_id in track_ids],
        model_version=analysis.model_version,
        dedupe_key=dedupe_key,
    )


def extract_events(db: Session, analysis_id: str) -> int:
    """Extract supported temporal events from one persisted analysis.

    Supported now: tracked instrument entry/removal/activity and same-frame
    instrument co-occurrence. Untracked detections become grouped detection
    events. Phase, tissue, and medical visual events require future providers.
    Existing events for this analysis are replaced so the operation is idempotent.
    """
    analysis_uuid = UUID(str(analysis_id))
    analysis = db.query(AnalysisSession).filter(AnalysisSession.id == analysis_uuid).first()
    if not analysis:
        raise ValueError(f"Analysis session not found: {analysis_id}")

    detections = (
        db.query(Detection)
        .filter(Detection.analysis_id == analysis.id)
        .order_by(Detection.timestamp, Detection.frame_id)
        .all()
    )
    tracks = db.query(Track).filter(Track.analysis_id == analysis.id).all()
    db.query(SurgicalEvent).filter(SurgicalEvent.analysis_id == analysis.id).delete(synchronize_session=False)

    events: list[SurgicalEvent] = []
    detections_by_track: dict[int, list[Detection]] = defaultdict(list)
    untracked_by_class: dict[str, list[Detection]] = defaultdict(list)
    detections_by_frame: dict[int, list[Detection]] = defaultdict(list)

    for detection in detections:
        detections_by_frame[detection.frame_id].append(detection)
        if detection.track_id is None:
            untracked_by_class[detection.class_name].append(detection)
        else:
            detections_by_track[detection.track_id].append(detection)

    track_by_id = {track.track_id: track for track in tracks}
    for track_id, track_detections in detections_by_track.items():
        track = track_by_id.get(track_id)
        if not track:
            continue
        ordered = sorted(track_detections, key=lambda detection: detection.timestamp)
        first = ordered[0]
        last = ordered[-1]
        instrument = track.class_name
        events.append(_event(
            analysis=analysis,
            event_type="INSTRUMENT_ENTERED",
            start_time=track.first_seen,
            end_time=track.first_seen,
            detections=[first],
            metadata={"instrument": instrument, "track_id": track_id},
            track_ids=[track_id],
            dedupe_key=f"entered:{track_id}:{track.first_seen:.6f}",
        ))
        events.append(_event(
            analysis=analysis,
            event_type="INSTRUMENT_REMOVED",
            start_time=track.last_seen,
            end_time=track.last_seen,
            detections=[last],
            metadata={"instrument": instrument, "track_id": track_id},
            track_ids=[track_id],
            dedupe_key=f"removed:{track_id}:{track.last_seen:.6f}",
        ))
        for segment_index, segment in enumerate(
            _group_by_temporal_gap(ordered, lambda detection: detection.timestamp)
        ):
            events.append(_event(
                analysis=analysis,
                event_type="INSTRUMENT_ACTIVITY",
                start_time=segment[0].timestamp,
                end_time=segment[-1].timestamp,
                detections=segment,
                metadata={"instrument": instrument, "track_id": track_id},
                track_ids=[track_id],
                dedupe_key=f"activity:{track_id}:{segment_index}:{segment[0].timestamp:.6f}",
            ))

    for instrument, class_detections in untracked_by_class.items():
        for segment_index, segment in enumerate(
            _group_by_temporal_gap(class_detections, lambda detection: detection.timestamp)
        ):
            events.append(_event(
                analysis=analysis,
                event_type="INSTRUMENT_DETECTED",
                start_time=segment[0].timestamp,
                end_time=segment[-1].timestamp,
                detections=segment,
                metadata={"instrument": instrument},
                dedupe_key=f"detected:{instrument}:{segment_index}:{segment[0].timestamp:.6f}",
            ))

    cooccurrence_frames = [
        frame_detections
        for frame_detections in detections_by_frame.values()
        if len({detection.class_name for detection in frame_detections}) > 1
    ]
    for segment_index, segment in enumerate(
        _group_by_temporal_gap(
            cooccurrence_frames,
            lambda frame_detections: min(d.timestamp for d in frame_detections),
        )
    ):
        segment_detections = [detection for frame in segment for detection in frame]
        instruments = sorted({detection.class_name for detection in segment_detections})
        track_ids = sorted({detection.track_id for detection in segment_detections if detection.track_id is not None})
        events.append(_event(
            analysis=analysis,
            event_type="INSTRUMENT_CO_OCCURRENCE",
            start_time=min(detection.timestamp for detection in segment_detections),
            end_time=max(detection.timestamp for detection in segment_detections),
            detections=segment_detections,
            metadata={"instruments": instruments, "track_ids": track_ids},
            track_ids=track_ids,
            dedupe_key=f"cooccurrence:{segment_index}:{segment[0][0].timestamp:.6f}",
        ))

    db.add_all(events)
    db.commit()
    return len(events)