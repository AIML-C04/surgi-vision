# SurgiVision AI

**Surgical Video Intelligence**

Research / Educational Surgical Video Analytics Platform

## Overview
SurgiVision AI is a platform for analyzing surgical videos. It allows authenticated users to upload surgical videos, run them through AI models for instrument detection, and interact with the analyzed data via a specialized video knowledge retrieval system (RAG) and WebRTC live session sharing.

## Architecture

**Frontend Architecture**: React + Vite, Tailwind CSS. Implements a professional, clinical/research-oriented UI with proper routing, user-isolated video library, interactive AI dashboard, and Q&A chat interfaces.

**Backend Architecture**: FastAPI serving a modular monolith. Handles JWT authentication, file uploads, WebSocket signaling, and AI background processing.

**Database**: Designed for **Supabase PostgreSQL** utilizing `pgvector` (`Vector(384)`) for semantic retrieval. (Automatically degrades to SQLite JSON columns during local dev without vectors). Contains tables for `User`, `Video`, `AnalysisSession`, `Detection`, `Track`, `SurgicalPhase`, `VideoKnowledgeChunk`, `Conversation`, `Message`, and `LiveSession`.

**Storage Abstraction**: Configurable `StorageProvider` allowing easy swapping between `LocalStorageProvider` (for development) and `SupabaseStorageProvider` (for production storage). Employs signed URLs for secure, authorized media playback.

**AI Provider**: Configurable AI inference abstraction (`RealInferenceProvider`, `MockInferenceProvider`). Supports running the `yolov8s_cholec80.pt` YOLOv8 model for real object detection and BoT-SORT/ByteTrack tracking. The system explicitly crashes early if the real model is missing.

> **Note on Phase Model Limitation**: Phase recognition is architecturally supported but currently omitted. The system explicitly reports this state rather than fabricating data.

**Knowledge Layer / RAG**: Generates and persists knowledge chunks based on detections. Retrieval is executed via `pgvector` cosine-similarity search, isolated by authenticated user and specific video to ensure secure, grounded context for Q&A.

**Live Architecture**: Provides endpoints for creating WebRTC live sessions. Uses secure pairing codes and backend WebSocket signaling for peer-to-peer connections. Note that production deployments across NATs will strictly require configured STUN/TURN servers.

## Security
- Server-side tenant isolation for all resources preventing IDOR.
- JWT authentication with hashed passwords.
- Secure HTTP-Only WebSockets matching via token strings.
- Never exposes Supabase service roles to the frontend.

## Local Setup

**Environment Variables**:
Create a `.env` file in the root:
```env
# Use PostgreSQL for full pgvector support, or SQLite for local dev
DATABASE_URL=sqlite:///./surgivision.db

STORAGE_PROVIDER=local
MODEL_PROVIDER=mock
LLM_PROVIDER=mock
SECRET_KEY=yoursecretkey
VITE_API_URL=http://localhost:8000
```

**Backend**:
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

**Frontend**:
```bash
cd frontend
npm install
npm run dev
```

## Limitations & Future Scope
- The system is a Research / Educational Prototype and is not clinically validated or certified.
- A true phase recognition model is explicitly not included.
- Production live streaming requires STUN/TURN configuration.
- Further quantitative model evaluations (mAP, Precision, Recall) are pending real-world benchmarks.
