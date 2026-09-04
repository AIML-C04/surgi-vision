import asyncio

from app.services import live_intelligence
from app.services.live_intelligence import LiveInferenceSession


class FakeProvider:
    def __init__(self):
        self.calls = 0

    def analyze_frame(self, frame_id, timestamp, frame):
        self.calls += 1
        if self.calls <= 4:
            return {"detections": [{"class": "Grasper", "confidence": 0.9, "bbox": [1, 2, 10, 12], "track_id": 4}]}
        return {"detections": [{"class": "Hook", "confidence": 0.8, "bbox": [2, 3, 11, 13], "track_id": 8}]}


def test_live_tracking_events_and_provider_output(monkeypatch):
    updates = []
    provider = FakeProvider()
    monkeypatch.setattr(live_intelligence, "get_provider", lambda: provider)

    async def collect(payload):
        updates.append(payload)

    async def run():
        session = LiveInferenceSession("session", collect)
        await session.start()
        for _ in range(5):
            await session.submit(object())
            await asyncio.sleep(0.02)
        await session.stop()
        return session

    session = asyncio.run(run())
    events = [event["event_type"] for update in updates for event in update.get("recent_events", [])]
    assert any(event == "INSTRUMENT_ENTERED" for event in events)
    assert any(update["detections"][0]["frame_id"] >= 0 for update in updates if update.get("detections"))
    assert session.error is None


def test_live_provider_failure_is_explicit(monkeypatch):
    updates = []
    monkeypatch.setattr(live_intelligence, "get_provider", lambda: (_ for _ in ()).throw(RuntimeError("model unavailable")))

    async def collect(payload):
        updates.append(payload)

    async def run():
        session = LiveInferenceSession("session", collect)
        await session.start()
        await session.stop()

    asyncio.run(run())
    assert updates[0]["processing_status"] == "model_unavailable"
    assert updates[0]["error"] == "model unavailable"
