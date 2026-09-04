from collections import defaultdict
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from app.models.event import SurgicalEvent
from app.models.video import AnalysisSession, Detection, Track


def _merge_intervals(intervals: list[tuple[float, float]]) -> tuple[list[dict[str, float]], float]:
    if not intervals:
        return [], 0.0
    merged: list[list[float]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    segments = [{"start_time": start, "end_time": end, "duration": end - start} for start, end in merged]
    return segments, sum(segment["duration"] for segment in segments)


def _track_metrics(track: Track, detections: list[Detection], activity_events: list[SurgicalEvent]) -> dict[str, Any]:
    ordered = sorted(detections, key=lambda detection: detection.timestamp)
    confidence_values = [detection.confidence for detection in ordered]
    activity_intervals = [(event.start_time, event.end_time) for event in activity_events]
    activity_segments, visible_duration = _merge_intervals(activity_intervals)
    return {
        "track_id": track.track_id,
        "instrument": track.class_name,
        "first_seen": track.first_seen,
        "last_seen": track.last_seen,
        "presence_span": max(0.0, track.last_seen - track.first_seen),
        "visible_duration": visible_duration,
        "detection_count": len(ordered),
        "detection_frame_count": len({detection.frame_id for detection in ordered}),
        "average_confidence": mean(confidence_values) if confidence_values else None,
        "peak_confidence": max(confidence_values) if confidence_values else None,
        "minimum_confidence": min(confidence_values) if confidence_values else None,
        "latest_confidence": confidence_values[-1] if confidence_values else None,
        "activity_segments": activity_segments,
        "activity_segment_count": len(activity_segments),
        "event_count": len(activity_events) + 2,
    }


def _transition_metrics(tracks: list[Track]) -> list[dict[str, Any]]:
    ordered = sorted(tracks, key=lambda track: (track.first_seen, track.last_seen, track.track_id))
    transitions = []
    for previous, current in zip(ordered, ordered[1:]):
        if previous.last_seen > current.first_seen:
            continue
        transitions.append({
            "from_instrument": previous.class_name,
            "to_instrument": current.class_name,
            "time": current.first_seen,
            "confidence": None,
            "evidence": {
                "previous_track_id": previous.track_id,
                "next_track_id": current.track_id,
                "previous_track_last_seen": previous.last_seen,
                "next_track_first_seen": current.first_seen,
                "interpretation": "Temporal instrument transition; not a confirmed exchange.",
            },
        })
    return transitions


def get_instrument_intelligence(db: Session, analysis: AnalysisSession) -> dict[str, Any]:
    """Derive instrument analytics from one completed analysis only.

    Class-level visible duration is the union of activity intervals across tracks,
    preventing overlapping track instances from being double-counted. Confidence
    metrics are calculated directly from persisted detection confidence values.
    """
    detections = (
        db.query(Detection)
        .filter(Detection.analysis_id == analysis.id)
        .order_by(Detection.timestamp, Detection.frame_id)
        .all()
    )
    tracks = (
        db.query(Track)
        .filter(Track.analysis_id == analysis.id)
        .order_by(Track.first_seen, Track.track_id)
        .all()
    )
    events = (
        db.query(SurgicalEvent)
        .filter(SurgicalEvent.analysis_id == analysis.id)
        .order_by(SurgicalEvent.start_time)
        .all()
    )

    detections_by_track: dict[int, list[Detection]] = defaultdict(list)
    detections_by_class: dict[str, list[Detection]] = defaultdict(list)
    for detection in detections:
        detections_by_class[detection.class_name].append(detection)
        if detection.track_id is not None:
            detections_by_track[detection.track_id].append(detection)

    activity_by_track: dict[int, list[SurgicalEvent]] = defaultdict(list)
    activity_by_class: dict[str, list[SurgicalEvent]] = defaultdict(list)
    entered_by_class: dict[str, int] = defaultdict(int)
    removed_by_class: dict[str, int] = defaultdict(int)
    detected_by_class: dict[str, int] = defaultdict(int)
    for event in events:
        metadata = event.event_metadata or {}
        if event.event_type == "INSTRUMENT_ACTIVITY":
            track_id = metadata.get("track_id")
            instrument = metadata.get("instrument")
            if track_id is not None:
                activity_by_track[int(track_id)].append(event)
            if instrument:
                activity_by_class[instrument].append(event)
        elif event.event_type == "INSTRUMENT_ENTERED":
            entered_by_class[metadata.get("instrument", "Unknown")] += 1
        elif event.event_type == "INSTRUMENT_REMOVED":
            removed_by_class[metadata.get("instrument", "Unknown")] += 1
        elif event.event_type == "INSTRUMENT_DETECTED":
            detected_by_class[metadata.get("instrument", "Unknown")] += 1

    tracks_by_class: dict[str, list[Track]] = defaultdict(list)
    for track in tracks:
        tracks_by_class[track.class_name].append(track)

    instruments = []
    for instrument, class_detections in sorted(detections_by_class.items()):
        class_tracks = tracks_by_class.get(instrument, [])
        track_metrics = [
            _track_metrics(track, detections_by_track[track.track_id], activity_by_track[track.track_id])
            for track in class_tracks
        ]
        class_segments, visible_duration = _merge_intervals([
            (segment["start_time"], segment["end_time"])
            for metric in track_metrics
            for segment in metric["activity_segments"]
        ])
        confidence_values = [detection.confidence for detection in class_detections]
        latest_detection = max(class_detections, key=lambda detection: detection.timestamp)
        cooccurrences = [
            {
                "start_time": event.start_time,
                "end_time": event.end_time,
                "confidence": event.confidence,
                "instruments": (event.event_metadata or {}).get("instruments", []),
                "evidence": event.evidence,
            }
            for event in events
            if event.event_type == "INSTRUMENT_CO_OCCURRENCE"
            and instrument in (event.event_metadata or {}).get("instruments", [])
        ]
        instruments.append({
            "class_name": instrument,
            "track_count": len(class_tracks),
            "first_seen": min((track.first_seen for track in class_tracks), default=min(d.timestamp for d in class_detections)),
            "last_seen": max((track.last_seen for track in class_tracks), default=max(d.timestamp for d in class_detections)),
            "presence_span": max((track.last_seen for track in class_tracks), default=max(d.timestamp for d in class_detections)) - min((track.first_seen for track in class_tracks), default=min(d.timestamp for d in class_detections)),
            "visible_duration": visible_duration,
            "activity_segments": class_segments,
            "activity_segment_count": len(class_segments),
            "detection_count": len(class_detections),
            "detection_frame_count": len({detection.frame_id for detection in class_detections}),
            "average_confidence": mean(confidence_values),
            "peak_confidence": max(confidence_values),
            "minimum_confidence": min(confidence_values),
            "latest_confidence": latest_detection.confidence,
            "event_count": len(activity_by_class[instrument]) + entered_by_class[instrument] + removed_by_class[instrument] + detected_by_class[instrument],
            "entered_event_count": entered_by_class[instrument],
            "removed_event_count": removed_by_class[instrument],
            "co_occurrences": cooccurrences,
            "tracks": track_metrics,
        })

    transitions = _transition_metrics(tracks)
    cooccurrences = [
        {
            "start_time": event.start_time,
            "end_time": event.end_time,
            "confidence": event.confidence,
            "instruments": (event.event_metadata or {}).get("instruments", []),
            "evidence": event.evidence,
        }
        for event in events
        if event.event_type == "INSTRUMENT_CO_OCCURRENCE"
    ]
    return {
        "video_id": str(analysis.video_id),
        "analysis_id": str(analysis.id),
        "model_version": analysis.model_version,
        "instrument_count": len(instruments),
        "track_count": len(tracks),
        "detection_count": len(detections),
        "instruments": instruments,
        "co_occurrences": cooccurrences,
        "transitions": transitions,
    }
