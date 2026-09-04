import asyncio
import os
import time
from collections import defaultdict
from typing import Any, Awaitable, Callable

from app.services.ai.mock_provider import MockInferenceProvider
from app.services.ai.processor import get_provider


class LiveInferenceSession:
    def __init__(self, session_id: str, send_update: Callable[[dict[str, Any]], Awaitable[None]], max_queue_size: int = 1):
        self.session_id = session_id
        self.send_update = send_update
        self.queue: asyncio.Queue[tuple[int, float, Any]] = asyncio.Queue(maxsize=max_queue_size)
        self.provider = None
        self.task: asyncio.Task | None = None
        self.sequence = 0
        self.dropped_frames = 0
        self.started_at = time.monotonic()
        self.active_tracks: dict[int, dict[str, Any]] = {}
        self.missing_counts: defaultdict[int, int] = defaultdict(int)
        self.recent_events: list[dict[str, Any]] = []
        self.last_cooccurrence: tuple[str, float] | None = None
        self.running = False
        self.error: str | None = None

    async def start(self) -> None:
        try:
            self.provider = get_provider()
        except Exception as exc:
            self.error = str(exc)
        self.running = True
        self.task = asyncio.create_task(self._run())
        await self.send_update(self.snapshot(status="model_unavailable" if self.error else "processing"))

    async def submit(self, frame: Any) -> None:
        if not self.running:
            return
        item = (self.sequence, time.monotonic() - self.started_at, frame)
        self.sequence += 1
        if self.queue.full():
            try:
                self.queue.get_nowait()
                self.dropped_frames += 1
            except asyncio.QueueEmpty:
                pass
        await self.queue.put(item)

    async def stop(self) -> None:
        self.running = False
        if self.task:
            await self.task
        self.active_tracks.clear()

    async def _run(self) -> None:
        while self.running or not self.queue.empty():
            try:
                sequence, timestamp, frame = await asyncio.wait_for(self.queue.get(), timeout=0.25)
            except asyncio.TimeoutError:
                continue
            if self.error:
                continue
            started = time.perf_counter()
            try:
                if isinstance(self.provider, MockInferenceProvider):
                    prediction = self.provider.analyze_frame(sequence, timestamp)
                    model_status = "test_mock"
                else:
                    prediction = self.provider.analyze_frame(sequence, timestamp, frame)
                    model_status = "real"
                detections = self._normalize_detections(prediction.get("detections", []), sequence, timestamp)
                events = self._update_tracks(detections, timestamp)
                latency_ms = round((time.perf_counter() - started) * 1000, 2)
                await self.send_update({
                    "type": "live_intelligence",
                    "session_id": self.session_id,
                    "sequence": sequence,
                    "timestamp": timestamp,
                    "model_provider": getattr(self.provider, "__class__", type(self.provider)).__name__,
                    "model_version": getattr(self.provider, "model_version", None) or os.getenv("MODEL_VERSION") or os.getenv("MODEL_PATH") or os.getenv("MODEL_PROVIDER", "mock"),
                    "model_status": model_status,
                    "processing_status": "processing",
                    "latency_ms": latency_ms,
                    "dropped_frames": self.dropped_frames,
                    "detections": detections,
                    "active_tracks": list(self.active_tracks.values()),
                    "recent_events": events,
                    "co_occurrences": [event for event in events if event["event_type"] == "INSTRUMENT_CO_OCCURRENCE"],
                })
            except Exception as exc:
                self.error = str(exc)
                await self.send_update(self.snapshot(status="error"))

    def _normalize_detections(self, raw: list[dict[str, Any]], sequence: int, timestamp: float) -> list[dict[str, Any]]:
        normalized = []
        for detection in raw:
            confidence = detection.get("confidence")
            bbox = detection.get("bbox")
            name = detection.get("class") or detection.get("class_name")
            if not isinstance(name, str) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
                continue
            if not isinstance(bbox, list) or len(bbox) != 4:
                continue
            track_id = detection.get("track_id")
            normalized.append({
                "frame_id": sequence,
                "timestamp": timestamp,
                "class": name,
                "confidence": float(confidence),
                "bbox": [float(value) for value in bbox],
                "track_id": int(track_id) if isinstance(track_id, int) else None,
            })
        return normalized

    def _update_tracks(self, detections: list[dict[str, Any]], timestamp: float) -> list[dict[str, Any]]:
        events = []
        seen_tracks = set()
        for detection in detections:
            track_id = detection.get("track_id")
            if track_id is None:
                continue
            seen_tracks.add(track_id)
            existing = self.active_tracks.get(track_id)
            if existing is None:
                self.active_tracks[track_id] = {"track_id": track_id, "instrument": detection["class"], "first_seen": timestamp, "last_seen": timestamp, "latest_confidence": detection["confidence"], "latest_bbox": detection["bbox"], "detection_count": 1}
                events.append(self._event("INSTRUMENT_ENTERED", timestamp, detection["class"], [track_id]))
            else:
                existing.update(last_seen=timestamp, latest_confidence=detection["confidence"], latest_bbox=detection["bbox"], detection_count=existing["detection_count"] + 1)
            self.missing_counts[track_id] = 0

        for track_id in list(self.active_tracks):
            if track_id not in seen_tracks:
                self.missing_counts[track_id] += 1
                if self.missing_counts[track_id] >= 3:
                    track = self.active_tracks.pop(track_id)
                    events.append(self._event("INSTRUMENT_REMOVED", timestamp, track["instrument"], [track_id]))
                    self.missing_counts.pop(track_id, None)

        instruments = sorted({item["instrument"] for item in self.active_tracks.values()})
        if len(instruments) > 1 and (self.last_cooccurrence is None or self.last_cooccurrence[0] != "+".join(instruments) or timestamp - self.last_cooccurrence[1] >= 2):
            self.last_cooccurrence = ("+".join(instruments), timestamp)
            events.append({"event_type": "INSTRUMENT_CO_OCCURRENCE", "timestamp": timestamp, "instruments": instruments, "interpretation": "Simultaneous model detection; not interaction or exchange."})
        self.recent_events.extend(events)
        self.recent_events = self.recent_events[-20:]
        return events

    @staticmethod
    def _event(event_type: str, timestamp: float, instrument: str, track_ids: list[int]) -> dict[str, Any]:
        return {"event_type": event_type, "timestamp": timestamp, "instrument": instrument, "track_ids": track_ids}

    def snapshot(self, status: str) -> dict[str, Any]:
        return {"type": "live_intelligence", "session_id": self.session_id, "sequence": self.sequence, "model_status": "unavailable" if self.error else "unknown", "processing_status": status, "error": self.error, "dropped_frames": self.dropped_frames, "detections": [], "active_tracks": list(self.active_tracks.values()), "recent_events": self.recent_events[-20:], "co_occurrences": []}
