from fastapi.testclient import TestClient
from app.main import app
from app.core.database import Base, engine, get_db
from sqlalchemy.orm import sessionmaker
import pytest

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "SurgiVision AI Backend is running"}

def test_register():
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "password", "full_name": "Test User", "role": "Researcher"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"

def test_login():
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "test@example.com", "password": "password"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
