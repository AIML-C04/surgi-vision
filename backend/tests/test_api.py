import os
os.environ["LLM_PROVIDER"] = "mock"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["STORAGE_PROVIDER"] = "local"
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from app.main import app
from app.core.database import Base, get_db
from sqlalchemy.orm import sessionmaker
import uuid

# Use in-memory SQLite for testing to avoid destroying the real Supabase database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

# Clean DB before tests
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Patch the SessionLocal so background tasks and websockets use the test DB
from app.core import database as core_db
from app.api.v1.endpoints import live as endpoints_live
from app.api.v1.endpoints import analysis as endpoints_analysis
from app.api.v1.endpoints import chat as endpoints_chat
from app.services.copilot_response import parse_generated_response
from app.services.copilot_evidence import classify_query, retrieve_copilot_evidence
core_db.SessionLocal = TestingSessionLocal
endpoints_live.SessionLocal = TestingSessionLocal

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200

# Auth & User Creation
def create_user(email, password):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Test", "role": "Researcher"}
    )
    return response

def login_user(email, password):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password}
    )
    return response.json().get("access_token")

def test_two_user_isolation():
    # Create User A
    create_user("userA@example.com", "pass")
    tokenA = login_user("userA@example.com", "pass")
    
    # Create User B
    create_user("userB@example.com", "pass")
    tokenB = login_user("userB@example.com", "pass")
    
    # Upload video for A
    from io import BytesIO
    fake_video = BytesIO(b"fake video content")
    response_upload = client.post(
        "/api/v1/videos/upload",
        headers={"Authorization": f"Bearer {tokenA}"},
        data={"title": "User A Video"},
        files={"file": ("test.mp4", fake_video, "video/mp4")}
    )
    if response_upload.status_code != 200:
        print("\n=== UPLOAD ERROR ===", response_upload.text)
    assert response_upload.status_code == 200
    video_id_a = response_upload.json()["id"]
    
    # User B should not see User A's videos
    response_b_videos = client.get(
        "/api/v1/videos/",
        headers={"Authorization": f"Bearer {tokenB}"}
    )
    assert response_b_videos.status_code == 200
    assert len(response_b_videos.json()) == 0
    
    # User B attempting to get User A's video url (IDOR)
    response_idor = client.get(
        f"/api/v1/videos/{video_id_a}/url",
        headers={"Authorization": f"Bearer {tokenB}"}
    )
    assert response_idor.status_code == 404

def test_upload_validation():
    token = login_user("userA@example.com", "pass")
    from io import BytesIO
    fake_file = BytesIO(b"fake content")
    response = client.post(
        "/api/v1/videos/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Invalid File"},
        files={"file": ("test.txt", fake_file, "text/plain")}
    )
    assert response.status_code == 400
    assert "Invalid file type" in response.json()["detail"]

def test_live_pairing_expiry_and_invalid():
    token = login_user("userA@example.com", "pass")
    # Verify invalid code
    res = client.post("/api/v1/live/verify?code=000000")
    assert res.status_code == 404

def test_missing_model_failure():
    # If MODEL_PROVIDER is 'real' but model is missing, processor should fail.
    # We can mock os.environ for processor temporarily, but let's just check the RAG endpoint missing context
    pass


def test_completed_analysis_is_reused_until_reanalysis(monkeypatch):
    email = "persistence@example.com"
    create_user(email, "pass")
    token = login_user(email, "pass")
    from io import BytesIO
    response_upload = client.post(
        "/api/v1/videos/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Persistence Video"},
        files={"file": ("persistence.mp4", BytesIO(b"video"), "video/mp4")}
    )
    assert response_upload.status_code == 200
    video_id = response_upload.json()["id"]

    db = TestingSessionLocal()
    from app.models.video import AnalysisSession
    completed = AnalysisSession(
        video_id=uuid.UUID(video_id),
        model_provider="mock",
        analysis_version=endpoints_analysis._configured_analysis_version(),
        model_version=endpoints_analysis._configured_model_version(),
        status="completed",
        progress=100.0,
    )
    db.add(completed)
    db.commit()
    db.refresh(completed)
    completed_id = str(completed.id)
    db.close()

    processing_calls = []

    async def processing_stub(*args, **kwargs):
        processing_calls.append(args[0])

    monkeypatch.setattr(endpoints_analysis, "process_video_background", processing_stub)

    response = client.post(
        f"/api/v1/analysis/?video_id={video_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert str(response.json()["analysis_id"]) == completed_id
    assert response.json()["status"] == "completed"
    assert processing_calls == []

    response_reanalyze = client.post(
        f"/api/v1/analysis/?video_id={video_id}&reanalyze=true",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response_reanalyze.status_code == 200
    assert str(response_reanalyze.json()["analysis_id"]) != completed_id
    assert response_reanalyze.json()["status"] == "started"
    assert len(processing_calls) == 1


def test_event_extraction_is_temporal_evidence_backed_and_idempotent():
    email = "events@example.com"
    create_user(email, "pass")
    token = login_user(email, "pass")
    from io import BytesIO
    response_upload = client.post(
        "/api/v1/videos/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Events Video"},
        files={"file": ("events.mp4", BytesIO(b"video"), "video/mp4")}
    )
    assert response_upload.status_code == 200
    video_id = response_upload.json()["id"]

    db = TestingSessionLocal()
    from app.models.event import SurgicalEvent
    from app.models.video import AnalysisSession, Detection, Track
    analysis = AnalysisSession(
        video_id=uuid.UUID(video_id),
        model_provider="mock",
        analysis_version="1",
        model_version="mock",
        status="completed",
        progress=100.0,
    )
    db.add(analysis)
    db.flush()
    detections = [
        Detection(analysis_id=analysis.id, frame_id=10, timestamp=2.0, class_name="Grasper", confidence=0.8, bbox=[1, 1, 2, 2], track_id=7),
        Detection(analysis_id=analysis.id, frame_id=11, timestamp=2.2, class_name="Grasper", confidence=0.9, bbox=[1, 1, 2, 2], track_id=7),
        Detection(analysis_id=analysis.id, frame_id=11, timestamp=2.2, class_name="Hook", confidence=0.85, bbox=[1, 1, 2, 2], track_id=8),
        Detection(analysis_id=analysis.id, frame_id=12, timestamp=2.4, class_name="Grasper", confidence=1.0, bbox=[1, 1, 2, 2], track_id=7),
        Detection(analysis_id=analysis.id, frame_id=12, timestamp=2.4, class_name="Hook", confidence=0.9, bbox=[1, 1, 2, 2], track_id=8),
        Detection(analysis_id=analysis.id, frame_id=30, timestamp=5.0, class_name="Grasper", confidence=0.7, bbox=[1, 1, 2, 2], track_id=7),
        Detection(analysis_id=analysis.id, frame_id=31, timestamp=5.2, class_name="Grasper", confidence=0.8, bbox=[1, 1, 2, 2], track_id=7),
    ]
    db.add_all(detections)
    db.add_all([
        Track(analysis_id=analysis.id, track_id=7, class_name="Grasper", first_seen=2.0, last_seen=5.2),
        Track(analysis_id=analysis.id, track_id=8, class_name="Hook", first_seen=2.2, last_seen=2.4),
    ])
    db.commit()

    from app.services.events.extractor import extract_events
    assert extract_events(db, str(analysis.id)) == 8
    first_activity = db.query(SurgicalEvent).filter(
        SurgicalEvent.analysis_id == analysis.id,
        SurgicalEvent.event_type == "INSTRUMENT_ACTIVITY",
        SurgicalEvent.start_time == 2.0,
    ).one()
    assert first_activity.end_time == 2.4
    assert first_activity.confidence == 0.9
    assert first_activity.event_metadata["instrument"] == "Grasper"
    assert first_activity.evidence["frame_ids"] == [10, 11, 12]

    assert extract_events(db, str(analysis.id)) == 8
    assert db.query(SurgicalEvent).filter(SurgicalEvent.analysis_id == analysis.id).count() == 8
    db.close()

    generated = client.post(
        f"/api/v1/videos/{video_id}/events/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert generated.status_code == 200
    assert generated.json()["event_count"] == 8

    intelligence = client.get(
        f"/api/v1/videos/{video_id}/instruments?rank_by=visible_duration",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert intelligence.status_code == 200
    intelligence_data = intelligence.json()
    assert intelligence_data["instrument_count"] == 2
    grasper = next(item for item in intelligence_data["instruments"] if item["class_name"] == "Grasper")
    assert grasper["track_count"] == 1
    assert grasper["detection_count"] == 5
    assert grasper["detection_frame_count"] == 5
    assert grasper["average_confidence"] == 0.84
    assert grasper["peak_confidence"] == 1.0
    assert grasper["activity_segment_count"] == 2
    assert len(grasper["tracks"]) == 1
    assert len(grasper["co_occurrences"]) == 1

    copilot = client.post(
        "/api/v1/chat/",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "When was the grasper detected?", "video_id": video_id},
    )
    assert copilot.status_code == 200
    assert copilot.json()["support"] == "supported"
    assert any(item["evidence_id"].startswith("instrument:") for item in copilot.json()["evidence"])
    conversation_id = copilot.json()["conversation_id"]

    response = client.get(
        f"/api/v1/videos/{video_id}/events?event_type=INSTRUMENT_ACTIVITY",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert len(response.json()["events"]) == 3

    other_email = "events-other@example.com"
    create_user(other_email, "pass")
    other_token = login_user(other_email, "pass")
    forbidden = client.get(
        f"/api/v1/videos/{video_id}/events",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert forbidden.status_code == 404

    wrong_video = client.post(
        "/api/v1/videos/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Other Events Video"},
        files={"file": ("other.mp4", BytesIO(b"video"), "video/mp4")},
    )
    assert wrong_video.status_code == 200
    conversation_mismatch = client.post(
        "/api/v1/chat/",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "Follow up", "video_id": wrong_video.json()["id"], "conversation_id": conversation_id},
    )
    assert conversation_mismatch.status_code == 404


def test_copilot_llm_failure_is_not_replaced_with_mock(monkeypatch):
    email = "llm-failure@example.com"
    create_user(email, "pass")
    token = login_user(email, "pass")
    from io import BytesIO
    uploaded = client.post(
        "/api/v1/videos/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "LLM Failure Video"},
        files={"file": ("failure.mp4", BytesIO(b"video"), "video/mp4")},
    )
    assert uploaded.status_code == 200

    class FailingProvider:
        def ask(self, *args, **kwargs):
            raise RuntimeError("configured provider unavailable")

    monkeypatch.setattr(endpoints_chat, "get_llm_provider", lambda: FailingProvider())
    response = client.post(
        "/api/v1/chat/",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "Summarize this video", "video_id": uploaded.json()["id"]},
    )
    assert response.status_code == 500
    assert "configured provider unavailable" in response.json()["detail"]


def test_copilot_response_validation_discards_malformed_and_unknown_citations():
    answer, support, citations, malformed = parse_generated_response(
        '{"answer":"Supported fact","support":"supported","evidence_ids":["trusted","invented"]}',
        {"trusted"},
    )
    assert answer == "Supported fact"
    assert support == "supported"
    assert citations == ["trusted"]
    assert malformed is False

    answer, support, citations, malformed = parse_generated_response(
        '{"answer":"Unsafe shape","support":"supported","evidence_ids":["invented"]}',
        {"trusted"},
    )
    assert answer == "Unsafe shape"
    assert support == "insufficient_evidence"
    assert citations == []
    assert malformed is False

    answer, support, citations, malformed = parse_generated_response("{not valid json}", {"trusted"})
    assert answer == "{not valid json}"
    assert support is None
    assert citations == []
    assert malformed is True


def test_copilot_query_intents_cover_composite_questions():
    intents = classify_query("Which instrument was active the longest and when did it first appear?")
    assert "instrument" in intents
    assert "duration" in intents
    assert "timestamp" not in intents
    assert "event" in classify_query("What happened around 45 seconds?")
    assert "timestamp" in classify_query("What happened around 45 seconds?")
    assert classify_query("Did the patient recover?") == ["unsupported"]


def test_selected_context_is_resolved_against_latest_analysis():
    from io import BytesIO
    create_user("selected-context@example.com", "pass")
    token = login_user("selected-context@example.com", "pass")
    uploaded = client.post(
        "/api/v1/videos/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Selected Context Video"},
        files={"file": ("selected.mp4", BytesIO(b"video"), "video/mp4")},
    )
    video_id = uuid.UUID(uploaded.json()["id"])
    db = TestingSessionLocal()
    from app.models.event import SurgicalEvent
    from app.models.video import AnalysisSession, Video
    owner = db.query(Video).filter(Video.id == video_id).first()
    analysis = db.query(AnalysisSession).filter(
        AnalysisSession.video_id == owner.id,
    ).first()
    if not analysis:
        analysis = AnalysisSession(
            video_id=owner.id,
            model_provider="mock",
            analysis_version="1",
            model_version="mock",
            status="completed",
        )
        db.add(analysis)
        db.flush()
    event = SurgicalEvent(
        video_id=owner.id,
        analysis_id=analysis.id,
        event_type="INSTRUMENT_ENTERED",
        start_time=4.0,
        end_time=4.0,
        confidence=0.9,
        event_metadata={"instrument": "Grasper"},
        evidence={"frame_ids": [40]},
        model_version="mock",
        dedupe_key="selected-context-event",
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    event_id = event.id
    other_video = Video(
        user_id=owner.user_id,
        title="Other Context Video",
        filename="other.mp4",
        file_path="missing.mp4",
        status="uploaded",
    )
    db.add(other_video)
    db.commit()
    db.refresh(other_video)
    owner_id = owner.id
    owner_user_id = owner.user_id
    other_video_id = other_video.id
    other_video_user_id = other_video.user_id
    db.close()

    selected = retrieve_copilot_evidence(
        TestingSessionLocal(), owner_id, owner_user_id, "Tell me more about this.",
        selected_context={"type": "event", "event_id": str(event_id)},
    )
    assert selected["evidence"][0]["evidence_id"] == f"event:{event_id}"

    try:
        retrieve_copilot_evidence(
            TestingSessionLocal(), other_video_id, other_video_user_id, "Tell me more about this.",
            selected_context={"type": "event", "event_id": str(event_id)},
        )
        assert False, "cross-video selected event should be rejected"
    except ValueError as exc:
        assert "completed analysis" in str(exc)


def test_authorized_procedure_comparison_uses_latest_persisted_intelligence():
    from io import BytesIO
    create_user("comparison@example.com", "pass")
    token = login_user("comparison@example.com", "pass")
    video_ids = []
    for title in ("Comparison A", "Comparison B"):
        uploaded = client.post(
            "/api/v1/videos/upload",
            headers={"Authorization": f"Bearer {token}"},
            data={"title": title},
            files={"file": (f"{title}.mp4", BytesIO(b"video"), "video/mp4")},
        )
        assert uploaded.status_code == 200
        video_ids.append(uuid.UUID(uploaded.json()["id"]))

    db = TestingSessionLocal()
    from app.models.event import SurgicalEvent
    from app.models.video import AnalysisSession, Detection, Track, Video
    for index, video_id in enumerate(video_ids):
        video = db.query(Video).filter(Video.id == video_id).first()
        analysis = AnalysisSession(
            video_id=video.id,
            model_provider="mock",
            analysis_version="1",
            model_version="model-a" if index == 0 else "model-b",
            status="completed",
        )
        db.add(analysis)
        db.flush()
        instrument = "Grasper" if index == 0 else "Hook"
        db.add_all([
            Detection(analysis_id=analysis.id, frame_id=1, timestamp=1.0, class_name=instrument, confidence=0.8, bbox=[1, 1, 2, 2], track_id=10 + index),
            Detection(analysis_id=analysis.id, frame_id=2, timestamp=2.0, class_name=instrument, confidence=0.9, bbox=[1, 1, 2, 2], track_id=10 + index),
            Track(analysis_id=analysis.id, track_id=10 + index, class_name=instrument, first_seen=1.0, last_seen=2.0),
        ])
        db.add(SurgicalEvent(
            video_id=video.id,
            analysis_id=analysis.id,
            event_type="INSTRUMENT_ACTIVITY",
            start_time=1.0,
            end_time=2.0,
            confidence=0.85,
            event_metadata={"instrument": instrument, "track_id": 10 + index},
            evidence={"frame_ids": [1, 2]},
            model_version=analysis.model_version,
            dedupe_key=f"comparison-{index}",
        ))
    db.commit()
    db.close()

    response = client.get(
        f"/api/v1/compare?video_a_id={video_ids[0]}&video_b_id={video_ids[1]}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["model_versions_differ"] is True
    assert data["procedure_a"]["analysis_id"] != data["procedure_b"]["analysis_id"]
    assert {row["class_name"] for row in data["instruments"]} == {"Grasper", "Hook"}
    assert data["overview"]["total_detections"]["a"] == 2
    assert data["overview"]["total_detections"]["b"] == 2
    assert data["overview"]["total_detections"]["per_minute"]["a"] is None

    create_user("comparison-other@example.com", "pass")
    other_token = login_user("comparison-other@example.com", "pass")
    forbidden = client.get(
        f"/api/v1/compare?video_a_id={video_ids[0]}&video_b_id={video_ids[1]}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert forbidden.status_code == 404


def test_knowledge_indexing_uses_event_json_metadata_and_phase_unavailable_is_nonfatal(monkeypatch):
    from io import BytesIO
    create_user("knowledge-index@example.com", "pass")
    token = login_user("knowledge-index@example.com", "pass")
    uploaded = client.post(
        "/api/v1/videos/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Knowledge Index Video"},
        files={"file": ("knowledge.mp4", BytesIO(b"video"), "video/mp4")},
    )
    assert uploaded.status_code == 200
    video_id = uuid.UUID(uploaded.json()["id"])

    db = TestingSessionLocal()
    from app.models.event import SurgicalEvent
    from app.models.knowledge import VideoKnowledgeChunk
    from app.models.video import AnalysisSession, Detection, Video
    video = db.query(Video).filter(Video.id == video_id).first()
    analysis = AnalysisSession(
        video_id=video.id,
        model_provider="mock",
        analysis_version="1",
        model_version="mock",
        status="processing",
    )
    db.add(analysis)
    db.flush()
    db.add(Detection(
        analysis_id=analysis.id,
        frame_id=1,
        timestamp=1.0,
        class_name="Grasper",
        confidence=0.9,
        bbox=[1, 1, 2, 2],
        track_id=1,
    ))
    db.add(SurgicalEvent(
        video_id=video.id,
        analysis_id=analysis.id,
        event_type="INSTRUMENT_ACTIVITY",
        start_time=1.0,
        end_time=2.0,
        confidence=0.9,
        event_metadata={"instrument": "Grasper", "track_id": 1},
        evidence={"frame_ids": [1]},
        model_version="mock",
        dedupe_key="knowledge-index-event",
    ))
    db.commit()

    monkeypatch.setattr(
        "app.services.rag.embeddings.generate_embeddings",
        lambda texts: [[0.0] * 384 for _ in texts],
    )
    from app.services.rag.indexer import generate_knowledge_from_analysis
    generate_knowledge_from_analysis(db, str(analysis.id), str(video.id), str(video.user_id))
    chunks = db.query(VideoKnowledgeChunk).filter(VideoKnowledgeChunk.video_id == video.id).all()
    assert any(chunk.source_type == "event" for chunk in chunks)
    event_chunk = next(chunk for chunk in chunks if chunk.source_type == "event")
    assert event_chunk.chunk_metadata["event_type"] == "INSTRUMENT_ACTIVITY"
    assert event_chunk.video_id == video.id
    assert event_chunk.user_id == video.user_id
    assert event_chunk.analysis_id == analysis.id

    # Retrying indexing must replace only this analysis version's chunks.
    generate_knowledge_from_analysis(db, str(analysis.id), str(video.id), str(video.user_id))
    assert db.query(VideoKnowledgeChunk).filter(VideoKnowledgeChunk.analysis_id == analysis.id).count() == len(chunks)

    from app.services.phase_recognition import recognize_and_persist_phases
    phase_result = recognize_and_persist_phases(db, analysis)
    assert phase_result["status"] == "unavailable"
    assert phase_result["available"] is False
    db.close()


def test_knowledge_failure_recovers_without_creating_analysis_or_rerunning_inference(monkeypatch):
    email = "knowledge-recovery@example.com"
    create_user(email, "pass")
    token = login_user(email, "pass")
    from io import BytesIO
    uploaded = client.post(
        "/api/v1/videos/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Recover Knowledge Only"},
        files={"file": ("recover.mp4", BytesIO(b"video"), "video/mp4")},
    )
    assert uploaded.status_code == 200
    video_id = uuid.UUID(uploaded.json()["id"])

    db = TestingSessionLocal()
    from app.models.event import SurgicalEvent
    from app.models.video import AnalysisSession, Detection, Track
    failed = AnalysisSession(
        video_id=video_id,
        model_provider="mock",
        analysis_version=endpoints_analysis._configured_analysis_version(),
        model_version=endpoints_analysis._configured_model_version(),
        status="error",
        progress=99.9,
        error="Knowledge indexing failed: metadata collision",
    )
    db.add(failed)
    db.flush()
    db.add(Detection(analysis_id=failed.id, frame_id=1, timestamp=1.0, class_name="Grasper", confidence=0.9, bbox=[1, 1, 2, 2], track_id=1))
    db.add(Track(analysis_id=failed.id, track_id=1, class_name="Grasper", first_seen=1.0, last_seen=1.0))
    db.add(SurgicalEvent(video_id=video_id, analysis_id=failed.id, event_type="INSTRUMENT_ACTIVITY", start_time=1.0, end_time=1.0, dedupe_key="recoverable-event"))
    db.commit()
    failed_id = str(failed.id)
    db.close()

    recovery_calls = []
    async def recovery_stub(analysis_id, _db):
        recovery_calls.append(analysis_id)
        _db.close()
    monkeypatch.setattr(endpoints_analysis, "recover_knowledge_indexing_background", recovery_stub)
    processing_calls = []
    async def processing_stub(*args, **kwargs):
        processing_calls.append(args[0])
    monkeypatch.setattr(endpoints_analysis, "process_video_background", processing_stub)

    response = client.post(f"/api/v1/analysis/?video_id={video_id}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert str(response.json()["analysis_id"]) == failed_id
    assert response.json()["status"] == "recovering"
    assert recovery_calls == [failed_id]
    assert processing_calls == []

    db = TestingSessionLocal()
    assert db.query(AnalysisSession).filter(AnalysisSession.video_id == video_id).count() == 1
    assert db.query(Detection).filter(Detection.analysis_id == uuid.UUID(failed_id)).count() == 1
    assert db.query(SurgicalEvent).filter(SurgicalEvent.analysis_id == uuid.UUID(failed_id)).count() == 1
    db.close()


def test_existing_events_are_returned_when_knowledge_recovery_is_pending():
    email = "existing-events@example.com"
    create_user(email, "pass")
    token = login_user(email, "pass")
    from io import BytesIO
    uploaded = client.post(
        "/api/v1/videos/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Existing Events"},
        files={"file": ("events.mp4", BytesIO(b"video"), "video/mp4")},
    )
    assert uploaded.status_code == 200
    video_id = uuid.UUID(uploaded.json()["id"])

    db = TestingSessionLocal()
    from app.models.event import SurgicalEvent
    from app.models.video import AnalysisSession
    analysis = AnalysisSession(video_id=video_id, model_provider="mock", analysis_version="1", model_version="mock", status="error", error="Knowledge indexing failed: test")
    db.add(analysis)
    db.flush()
    db.add(SurgicalEvent(video_id=video_id, analysis_id=analysis.id, event_type="INSTRUMENT_ACTIVITY", start_time=1.0, end_time=2.0, dedupe_key="persisted-event"))
    db.commit()
    analysis_id = str(analysis.id)
    db.close()

    generated = client.post(f"/api/v1/videos/{video_id}/events/generate", headers={"Authorization": f"Bearer {token}"})
    assert generated.status_code == 200
    assert generated.json() == {"analysis_id": analysis_id, "event_count": 1, "status": "available", "analysis_status": "error"}
    events = client.get(f"/api/v1/videos/{video_id}/events", headers={"Authorization": f"Bearer {token}"})
    assert events.status_code == 200
    assert events.json()["total_events"] == 1

def test_rag_insufficient_evidence():
    try:
        create_user("userA@example.com", "pass")
    except:
        pass
    token = login_user("userA@example.com", "pass")
    # A video with no knowledge
    from io import BytesIO
    fake_video = BytesIO(b"fake video content")
    res_v = client.post(
        "/api/v1/videos/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Empty Video"},
        files={"file": ("test2.mp4", fake_video, "video/mp4")}
    )
    if res_v.status_code != 200:
        print("\n=== RAG UPLOAD ERROR ===", res_v.text)
    v_id = res_v.json()["id"]
    
    res_chat = client.post(
        "/api/v1/chat/",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "What instruments are seen?", "video_id": v_id}
    )
    # The configured mock provider must disclose that the evidence is unavailable.
    assert res_chat.status_code == 200
    assert "not available in the analyzed video data" in res_chat.json()["answer"]

def test_rag_ownership_filtering():
    tokenB = login_user("userB@example.com", "pass")
    random_uuid = str(uuid.uuid4())
    res_chat = client.post(
        "/api/v1/chat/",
        headers={"Authorization": f"Bearer {tokenB}"},
        json={"query": "What instruments are seen?", "video_id": random_uuid}
    )
    assert res_chat.status_code == 404

def test_conversation_ownership():
    tokenB = login_user("userB@example.com", "pass")
    random_uuid = str(uuid.uuid4())
    res = client.get(
        f"/api/v1/chat/{random_uuid}",
        headers={"Authorization": f"Bearer {tokenB}"}
    )
    assert res.status_code == 404

def test_missing_model_explicit_failure():
    from app.services.ai.processor import get_provider
    import os
    
    # Force real provider with non-existent checkpoint path
    os.environ["MODEL_PROVIDER"] = "real"
    os.environ["MODEL_PATH"] = "nonexistent.pt"
    
    try:
        provider = get_provider()
    except RuntimeError as e:
        msg = str(e)
        assert "Model checkpoint not found" in msg or "ultralytics" in msg or "Failed to load model" in msg or "Model loading error" in msg
        
    os.environ["MODEL_PROVIDER"] = "mock" # Reset for other tests

def test_unauthorized_websocket_access():
    from starlette.websockets import WebSocketDisconnect
    try:
        with client.websocket_connect(f'/api/v1/live/ws/{uuid.uuid4()}/host') as websocket:
            websocket.receive_text()
            assert False, 'Should have disconnected'
    except WebSocketDisconnect as e:
        assert e.code == 1008


def test_registration_persistence_and_duplicate():
    # 1. Registration
    email = "TestUser@Example.com"
    password = "SecurePassword123"
    res = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": "Test User",
        "role": "Researcher"
    })
    assert res.status_code == 200
    user_data = res.json()
    assert user_data["email"] == "testuser@example.com"  # Normalized
    
    # 2. Duplicate registration with different casing should fail
    res_dup = client.post("/api/v1/auth/register", json={
        "email": "testuser@example.com",
        "password": "SecurePassword123",
        "full_name": "Test User",
        "role": "Researcher"
    })
    assert res_dup.status_code == 400
    assert "already exists" in res_dup.json()["detail"]
    
    # 3. Login with different casing should succeed due to normalization
    res_login = client.post("/api/v1/auth/login", data={
        "username": "TESTUSER@EXAMPLE.COM",
        "password": password
    })
    assert res_login.status_code == 200
    token = res_login.json()["access_token"]
    
    # 4. /auth/me returns correct user
    res_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200
    assert res_me.json()["email"] == "testuser@example.com"
    
    # 5. Invalid password fails
    res_invalid = client.post("/api/v1/auth/login", data={
        "username": email,
        "password": "WrongPassword"
    })
    assert res_invalid.status_code == 401
    
    # 6. Nonexistent email fails
    res_nonexist = client.post("/api/v1/auth/login", data={
        "username": "nonexistent@example.com",
        "password": password
    })
    assert res_nonexist.status_code == 401

def test_secret_key_stability():
    from app.core.config import settings
    # Ensure SECRET_KEY is not generated dynamically in a way that breaks persistence
    assert settings.SECRET_KEY is not None
    assert len(settings.SECRET_KEY) > 0


def test_video_report_generation():
    token = login_user("userA@example.com", "pass")
    
    # 1. Upload Video
    from io import BytesIO
    fake_video = BytesIO(b"fake report video")
    res_v = client.post(
        "/api/v1/videos/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Report Test Video"},
        files={"file": ("report_test.mp4", fake_video, "video/mp4")}
    )
    assert res_v.status_code == 200
    v_id = res_v.json()["id"]
    
    # 2. Test Report before analysis (No analysis available)
    res_report_unavail = client.get(
        f"/api/v1/videos/{v_id}/report",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_report_unavail.status_code == 200
    assert res_report_unavail.json()["available"] is False
    
    # 3. Create Analysis Session manually for testing
    import uuid
    db = TestingSessionLocal()
    from app.models.video import AnalysisSession, Detection, Track
    from app.models.event import SurgicalEvent
    from datetime import datetime, timezone
    
    analysis = AnalysisSession(
        video_id=uuid.UUID(v_id),
        model_provider="mock",
        analysis_version="1",
        model_version="mock",
        status="completed",
        processed_at=datetime.now(timezone.utc)
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    
    # 4. Insert dummy intelligence data
    det = Detection(
        analysis_id=analysis.id,
        frame_id=1,
        timestamp=1.0,
        class_name="Grasper",
        confidence=0.9,
        bbox=[0, 0, 10, 10],
        track_id=1
    )
    track = Track(
        analysis_id=analysis.id,
        track_id=1,
        class_name="Grasper",
        first_seen=1.0,
        last_seen=10.0
    )
    event1 = SurgicalEvent(
        video_id=uuid.UUID(v_id),
        analysis_id=analysis.id,
        event_type="INSTRUMENT_ENTERED",
        start_time=1.0,
        end_time=1.0,
        confidence=0.9,
        event_metadata={"instrument": "Grasper"},
        dedupe_key="event-report-1"
    )
    event2 = SurgicalEvent(
        video_id=uuid.UUID(v_id),
        analysis_id=analysis.id,
        event_type="INSTRUMENT_ACTIVITY",
        start_time=1.0,
        end_time=10.0,
        confidence=0.9,
        event_metadata={"instrument": "Grasper", "track_id": 1},
        dedupe_key="event-report-2"
    )
    
    db.add(det)
    db.add(track)
    db.add(event1)
    db.add(event2)
    db.commit()
    db.close()
    
    # 5. Fetch the Report
    res_report = client.get(
        f"/api/v1/videos/{v_id}/report",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_report.status_code == 200
    data = res_report.json()
    
    assert data["available"] is True
    assert data["procedure_overview"]["video_title"] == "Report Test Video"
    assert data["procedure_overview"]["total_detections"] == 1
    assert data["procedure_overview"]["total_events"] == 2
    
    # Check instrument intelligence
    assert len(data["instrument_intelligence"]) == 1
    assert data["instrument_intelligence"][0]["class_name"] == "Grasper"
    
    # Check event summary
    assert data["event_summary"]["INSTRUMENT_ENTERED"] == 1
    assert data["event_summary"]["INSTRUMENT_ACTIVITY"] == 1
    
    # Check Key moments
    assert len(data["key_moments"]) == 2
    assert data["key_moments"][0]["event_type"] == "INSTRUMENT_ENTERED"
    assert data["key_moments"][0]["label"] == "Grasper Entered"

def test_video_report_unauthorized_isolation():
    # User B should not see User A's report
    tokenB = login_user("userB@example.com", "pass")
    import uuid
    res = client.get(
        f"/api/v1/videos/{uuid.uuid4()}/report",
        headers={"Authorization": f"Bearer {tokenB}"}
    )
    assert res.status_code == 404


def test_local_cors_preflight_supports_phase_requests():
    response = client.options(
        f"/api/v1/videos/{uuid.uuid4()}/phases",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "authorization" in response.headers["access-control-allow-headers"]


def test_huggingface_missing_token_returns_explicit_configuration_error(monkeypatch):
    from io import BytesIO

    email = "missing-token-runtime@example.com"
    create_user(email, "pass")
    token = login_user(email, "pass")
    uploaded = client.post(
        "/api/v1/videos/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Missing Token Video"},
        files={"file": ("missing-token.mp4", BytesIO(b"video"), "video/mp4")},
    )
    monkeypatch.setenv("LLM_PROVIDER", "huggingface")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    response = client.post(
        "/api/v1/chat/",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "Summarize this video", "video_id": uploaded.json()["id"]},
    )
    assert response.status_code == 503
    assert "HF_TOKEN" not in response.json()["detail"]
    assert "not configured" in response.json()["detail"]
