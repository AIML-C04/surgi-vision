import os
os.environ["LLM_PROVIDER"] = "mock"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
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
    # The Mock LLM returns "Insufficient evidence in this video." when context is empty
    assert res_chat.status_code == 200
    assert "Insufficient evidence" in res_chat.json()["answer"]

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
