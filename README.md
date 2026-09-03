# SurgiVision AI

**Surgical Video Intelligence**

Research / Educational Surgical Video Analytics Platform

## Overview
SurgiVision AI is a platform for analyzing surgical videos. It allows authenticated users to upload surgical videos, run them through AI models for instrument detection, and interact with the analyzed data via a specialized video knowledge retrieval system (RAG) and WebRTC live session sharing.

## Architecture

**Frontend Architecture**: React + Vite, Tailwind CSS. Implements a professional, clinical/research-oriented UI with proper routing, user-isolated video library, interactive AI dashboard, and Q&A chat interfaces.

**Backend Architecture**: FastAPI serving a modular monolith. Handles JWT authentication, file uploads, WebSocket signaling, and AI background processing.

**Database**: Uses Supabase PostgreSQL (or SQLite as a development fallback). Uses Alembic for proper schema migrations. Contains tables for `User`, `Video`, `AnalysisSession`, `Detection`, `Track`, `SurgicalPhase`, `VideoKnowledgeChunk`, `Conversation`, `Message`, and `LiveSession`.

**Storage Abstraction**: Configurable `StorageProvider` allowing easy swapping between `LocalStorageProvider` (for development) and `SupabaseStorageProvider` (for production storage). Employs signed URLs for secure, authorized media playback.

**AI Provider**: Configurable AI inference abstraction (`RealInferenceProvider`, `MockInferenceProvider`). Supports running the `yolov8s_cholec80.pt` YOLOv8 model for real object detection and BoT-SORT/ByteTrack tracking. The system gracefully fails if configured to use the real model but it cannot be loaded.
> **Note on Phase Model Limitation**: Phase recognition is architecturally supported but currently unavailable as a genuine phase model is not yet configured. The system explicitly reports this state rather than fabricating data.

**Knowledge Layer / RAG**: Generates and persists knowledge chunks based on detections. Retrieval is strictly isolated by authenticated user and the specific video to ensure secure, grounded context for Q&A.

**LLM Provider**: Contains an abstraction with `HuggingFaceLLMProvider` and `MockLLMProvider` for Q&A tasks. The LLM is explicitly prompted to state "NOT AVAILABLE / INSUFFICIENT EVIDENCE" when the context is lacking.

**Live Architecture**: Provides endpoints for creating WebRTC live sessions. Uses secure pairing codes and backend WebSocket signaling for peer-to-peer connections.

## Security
- Server-side tenant isolation for all resources.
- JWT authentication with hashed passwords.
- Environment-driven configuration.
- Storage URLs are securely generated via signed access or local authenticated routing.
- Secrets are explicitly excluded from version control.

## Local Setup

**Environment Variables**:
Create a `.env` file in the root based on `.env.example`:
```env
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
- A true phase recognition model needs to be integrated.
- WebRTC media stream integration and recording functionality need frontend implementation.
- Further quantitative model evaluations (mAP, Precision, Recall) are pending real-world benchmarks.
- No HTTPS / SSL claims are made as it is deployment-dependent.
