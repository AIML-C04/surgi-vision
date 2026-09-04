# SurgiVision AI — Local Setup Guide

> **Single source of truth for team members.**
>
> Follow this document after cloning the repository. It explains the software/hardware requirements, exact local setup, Supabase database and storage creation, API keys/tokens, AI model setup, environment variables, migrations, startup commands, testing, troubleshooting, and team Git rules.

## 1. Project

**SurgiVision AI: A Real-Time Intelligent Surgical Video Analytics Platform for Instrument Detection, Tracking, and Surgical Phase Recognition**

The project is a **research/educational surgical video analytics prototype**. It is not a clinical diagnosis system, treatment recommender, autonomous surgical controller, certified medical device, or replacement for clinicians.

### Main capabilities

- Authentication and JWT-based access
- Multi-user data isolation
- Video upload and persistent storage
- Video Workspace
- Store & Understand / video knowledge indexing
- Real YOLO-based surgical instrument detection
- Bounding boxes, confidence and tracking
- Temporal video knowledge
- Sentence Transformer embeddings
- PostgreSQL + pgvector retrieval
- Video-specific RAG
- Hugging Face text-generation LLM Q&A
- Timestamp evidence and video seeking
- Analysis timeline/reports
- Live camera/session architecture
- Live recording save/discard
- Supabase PostgreSQL
- Supabase Storage

---

# 2. Architecture

```text
Browser
  │
  ▼
React + Vite
  │ HTTP / WebSocket
  ▼
FastAPI Backend
  ├── Authentication
  ├── Video Service
  ├── Analysis Service
  ├── Knowledge Service
  ├── Q&A / RAG Service
  └── Live Service
        │
        ├──────────────► Supabase PostgreSQL + pgvector
        │
        └──────────────► Supabase Storage
        │
        ▼
     AI Layer
        ├── YOLO surgical instrument detector
        ├── Tracking
        ├── Temporal knowledge extraction
        ├── Sentence Transformer embeddings
        └── Hugging Face text-generation LLM
```

### Video analysis

```text
Video
 ↓
Supabase Storage
 ↓
FastAPI
 ↓
OpenCV frame extraction
 ↓
YOLOv8 surgical model
 ├─ instrument class
 ├─ confidence
 ├─ bounding box
 └─ tracking ID
 ↓
Temporal knowledge
 ↓
Sentence Transformer
 ↓
Embeddings
 ↓
PostgreSQL + pgvector
```

### Q&A

```text
Question
 ↓
Authenticate user
 ↓
Verify video ownership
 ↓
Question embedding
 ↓
pgvector similarity search
 ↓
ONLY selected video's knowledge
 ↓
Grounded prompt
 ↓
Hugging Face text-generation LLM
 ↓
Answer + evidence/timestamps
```

---

# 3. Required Software

| Software | Recommended |
|---|---|
| OS | Windows 10/11 64-bit |
| Python | 3.10.x or 3.11.x |
| Node.js | 24.x LTS |
| npm | Bundled with Node.js |
| Git | Current maintained Git for Windows |
| Docker Desktop | Latest stable, when Docker workflow is used |
| FFmpeg | 9.x, when required by video tooling |
| Browser | Chrome or Microsoft Edge |
| Database | Supabase PostgreSQL |
| Vector search | PostgreSQL + pgvector |

**Important:** the repository's `package-lock.json`, `requirements.txt`, Dockerfiles and migration files are the final source of truth. Do not randomly upgrade core packages.

---

# 4. Official Downloads

### Git
https://git-scm.com/install/windows

Verify:

```powershell
git --version
```

### Python
https://www.python.org/downloads/

Install Python 3.10.x or 3.11.x and enable:

```text
Add Python to PATH
```

Verify:

```powershell
python --version
```

If necessary:

```powershell
py --version
```

### Node.js
https://nodejs.org/en/download

Install the LTS release.

Verify:

```powershell
node --version
npm --version
```

### VS Code
https://code.visualstudio.com/download

Recommended extensions:

- Python
- Pylance
- ESLint
- Docker
- Prettier, if used by the repository

### Docker Desktop
https://www.docker.com/products/docker-desktop/

Verify:

```powershell
docker --version
```

### FFmpeg
https://ffmpeg.org/download.html

Verify:

```powershell
ffmpeg -version
```

---

# 5. Hardware Requirements

### Minimum practical development machine

```text
CPU: modern 4+ core processor
RAM: 16 GB
Storage: SSD
Internet: required for Supabase/Hugging Face/model downloads
```

### Recommended AI development machine

```text
CPU: 6–8+ cores
RAM: 16–32 GB
GPU: NVIDIA CUDA-capable GPU if available
VRAM: 6–8 GB+
Storage: SSD
```

The project can run on CPU, but YOLO video analysis can be considerably slower.

Do not claim a specific FPS unless it has actually been measured on that machine.

---

# 6. Clone the Repository

```powershell
git clone https://github.com/AIML-C04/surgi-vision.git
cd surgi-vision
```

Check:

```powershell
git status
```

Repository:

https://github.com/AIML-C04/surgi-vision

---

# 7. Expected Project Layout

The exact layout can evolve, but the repository should contain concepts similar to:

```text
surgi-vision/
├── backend/
│   ├── app/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── ...
├── frontend/
│   ├── src/
│   ├── package.json
│   ├── package-lock.json
│   └── ...
├── models/
│   └── yolov8s_cholec80.pt
├── alembic/
├── .env.example
├── .gitignore
├── docker-compose.yml
├── README.md
└── LOCAL_SETUP.md
```

If the actual repository differs, follow the current repository paths.

---

# 8. Create the Python Virtual Environment

From the project root:

```powershell
python -m venv .venv
```

Activate:

```powershell
.\.venv\Scripts\Activate.ps1
```

The terminal should show:

```text
(.venv)
```

### If PowerShell blocks activation

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then:

```powershell
.\.venv\Scripts\Activate.ps1
```

### Command Prompt alternative

```cmd
.venv\Scripts\activate
```

Verify:

```powershell
python --version
```

---

# 9. Install Backend Dependencies

```powershell
cd backend
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Verify key packages:

```powershell
python -c "import fastapi; print('FastAPI OK')"
python -c "import sqlalchemy; print('SQLAlchemy OK')"
python -c "import ultralytics; print('Ultralytics OK')"
python -c "import sentence_transformers; print('Sentence Transformers OK')"
python -c "import supabase; print('Supabase SDK OK')"
```

Return:

```powershell
cd ..
```

If a package is missing from `requirements.txt`, fix the dependency file in the repository rather than requiring every developer to install it manually.

---

# 10. Install Frontend Dependencies

```powershell
cd frontend
```

If `package-lock.json` exists:

```powershell
npm ci
```

Otherwise:

```powershell
npm install
```

Then:

```powershell
cd ..
```

### Why `npm ci`?

It installs the versions recorded in the lock file and gives team members a reproducible frontend environment.

---

# 11. Create `.env`

The repository should contain:

```text
.env.example
```

Copy it:

```powershell
Copy-Item .env.example .env
```

Never commit `.env`.

`.env.example` contains placeholders only.

---

# 12. Generate the JWT Secret

With the Python virtual environment active:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Put the generated value into:

```env
SECRET_KEY=YOUR_RANDOM_SECRET
```

Never commit this value.

---

# 13. Supabase Account

Create an account:

https://supabase.com/

Dashboard:

https://supabase.com/dashboard

Click:

```text
New project
```

For an individual developer, a project such as:

```text
surgivision-dev-yourname
```

is convenient.

For a shared team development environment, the team lead may provide access to one shared development project.

---

# 14. Supabase Database Password

When creating the Supabase project, create a strong database password.

Save it securely.

You will need it for:

```text
DATABASE_URL
```

Never put the database password in:

- GitHub
- README
- source code
- frontend code
- screenshots
- public chat

---

# 15. Get the Supabase Database Connection String

In Supabase:

```text
Project
 → Connect
 → PostgreSQL
 → Session Pooler
```

For the persistent FastAPI/SQLAlchemy backend, use the **Session Pooler** when appropriate.

It normally uses:

```text
port 5432
```

Example format:

```text
postgresql://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres
```

Do not type the example literally.

Copy the actual connection string from the Supabase dashboard.

Official documentation:

https://supabase.com/docs/guides/database/connecting-to-postgres

---

# 16. Configure `DATABASE_URL`

In `.env`:

```env
DATABASE_URL=YOUR_SUPABASE_SESSION_POOLER_CONNECTION_STRING
```

Supabase distinguishes:

```text
Session pooler → 5432
Transaction pooler → 6543
```

Use the connection mode expected by the repository.

If the project is using persistent SQLAlchemy connections, Session Pooler is the documented default choice for IPv4-only environments.

---

# 17. Enable pgvector

SurgiVision uses vector embeddings for video-specific RAG.

In Supabase:

```text
Database
 → Extensions
 → Search "vector"
 → Enable vector
```

The application needs pgvector for:

```text
knowledge text
 ↓
embedding vector
 ↓
PostgreSQL vector column
 ↓
similarity search
```

Do not replace pgvector with a local vector database unless the architecture is intentionally changed.

---

# 18. Create Supabase Storage Bucket

Open:

```text
Supabase
 → Storage
```

Create:

```text
surgivision-videos
```

The spelling must match the application configuration.

Use a:

```text
PRIVATE bucket
```

Do not make the bucket public just to make playback work.

The backend should generate signed URLs after checking video ownership.

---

# 19. Supabase Storage Layout

The application is designed to store objects conceptually as:

```text
users/
└── USER_ID/
    └── videos/
        └── VIDEO_ID_FILENAME.mp4
```

The database stores video metadata.

The private bucket stores the actual video file.

---

# 20. Get Supabase Backend Credentials

In Supabase:

```text
Project Settings
 → API
```

The backend requires:

```env
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_SERVICE_ROLE_KEY=YOUR_BACKEND_SECRET
```

Depending on the current Supabase dashboard wording, use the backend/server secret key provided for server-side access.

### CRITICAL

The service-role/backend secret is server-only.

Never expose it through:

```text
React
Vite
VITE_* variables
browser JavaScript
public GitHub
```

Never create:

```env
VITE_SUPABASE_SERVICE_ROLE_KEY=...
```

---

# 21. Hugging Face Account

Create an account:

https://huggingface.co/join

Sign in:

https://huggingface.co/

The project uses Hugging Face for the text-generation LLM provider.

---

# 22. Create Hugging Face Token

Open:

https://huggingface.co/settings/tokens

Create an access token with the minimum permissions required by the configured model/provider.

For normal read/inference access, prefer the least-privileged option.

Add to `.env`:

```env
HF_TOKEN=hf_YOUR_TOKEN
```

Never commit it.

Official token documentation:

https://huggingface.co/docs/hub/security-tokens

---

# 23. Hugging Face LLM Configuration

The project separates computer vision from language generation.

Computer vision:

```env
MODEL_PROVIDER=real
```

Language model:

```env
LLM_PROVIDER=huggingface
```

The LLM model variable is whatever is defined in the current `.env.example`, for example:

```env
LLM_MODEL=YOUR_HUGGINGFACE_MODEL_ID
```

or:

```env
HF_LLM_MODEL=YOUR_HUGGINGFACE_MODEL_ID
```

**Use the variable name in the repository's current `.env.example`. Do not invent another one.**

---

# 24. YOLO Surgical Model

Current prototype model:

```text
yolov8s_cholec80.pt
```

Source:

https://huggingface.co/cesaraha/yolov8s-surgical-instrument-detection-cholec80

The model is a YOLOv8s surgical instrument detector trained for laparoscopic cholecystectomy video.

Supported classes include:

```text
Grasper
Hook
Irrigator
Bipolar
Bag
Scissors
Clipper
```

The model card identifies it as research/educational and not clinically validated.

---

# 25. Download the YOLO Model

Create the directory if needed:

```powershell
mkdir models
```

Download:

```text
yolov8s_cholec80.pt
```

from:

https://huggingface.co/cesaraha/yolov8s-surgical-instrument-detection-cholec80/tree/main

Place it at:

```text
surgi-vision/
└── models/
    └── yolov8s_cholec80.pt
```

The model path should normally be:

```env
MODEL_PATH=models/yolov8s_cholec80.pt
```

### Model license

The current model card lists:

```text
CC BY-NC-SA 4.0
```

Check the current license before redistribution or commercial use.

---

# 26. Configure Real YOLO Mode

In `.env`:

```env
MODEL_PROVIDER=real
MODEL_PATH=models/yolov8s_cholec80.pt
MODEL_CONFIDENCE_THRESHOLD=0.5
PROCESS_EVERY_N_FRAMES=5
```

For normal project demonstrations, use:

```env
MODEL_PROVIDER=real
```

Real mode must never silently fall back to mock detections.

---

# 27. Test the YOLO Model Directly

With the virtual environment active:

```powershell
python -c "from ultralytics import YOLO; m=YOLO('models/yolov8s_cholec80.pt'); print(m.names)"
```

You should see the model's class names.

If this fails, check:

```text
Python version
Ultralytics installation
PyTorch installation
model file
model path
```

---

# 28. Complete `.env` Template

Use the repository's `.env.example` as the final authority.

Conceptually:

```env
APP_ENV=development

SECRET_KEY=GENERATE_A_RANDOM_SECRET
ACCESS_TOKEN_EXPIRE_MINUTES=60

DATABASE_URL=YOUR_SUPABASE_SESSION_POOLER_URL

STORAGE_PROVIDER=supabase
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_SERVICE_ROLE_KEY=YOUR_BACKEND_SECRET
SUPABASE_BUCKET=surgivision-videos

MODEL_PROVIDER=real
MODEL_PATH=models/yolov8s_cholec80.pt
MODEL_CONFIDENCE_THRESHOLD=0.5
PROCESS_EVERY_N_FRAMES=5

LLM_PROVIDER=huggingface
HF_TOKEN=YOUR_HUGGINGFACE_TOKEN
LLM_MODEL=YOUR_CONFIGURED_MODEL

VITE_API_URL=http://localhost:8000

CORS_ORIGINS=http://localhost:5173
```

Do not copy a variable blindly if the current `.env.example` uses a different name.

---

# 29. Apply Database Migrations

The project uses Alembic.

From the location where `alembic.ini` is configured:

```powershell
alembic upgrade head
```

If Alembic is inside `backend`:

```powershell
cd backend
alembic upgrade head
cd ..
```

Migrations should create/update the required application schema.

Typical entities include:

```text
users
videos
analysis_sessions
detections
tracks
surgical_phases
knowledge records / embeddings
```

The actual current migration files are authoritative.

---

# 30. Do Not Manually Recreate the Database

Do not ask each developer to manually create every table in the Supabase Table Editor.

The repository should contain migration files.

The intended process is:

```text
Clone repository
 ↓
Configure .env
 ↓
Run migrations
 ↓
Database schema ready
```

If a schema changes, create a migration and commit it.


---

# 31. RLS and Security

The application enforces ownership in the FastAPI backend.

Supabase database security should also be reviewed and maintained.

Do not create permissive policies such as:

```sql
USING (true)
```

for private application data just to remove an error.

The logical tenant boundary must remain:

```text
User A
 ├── User A videos
 ├── User A analyses
 ├── User A knowledge
 └── User A Q&A

User B
 ├── User B videos
 ├── User B analyses
 ├── User B knowledge
 └── User B Q&A
```

A user must not gain access by changing a video ID, analysis ID, knowledge ID, or other resource ID.

---

# 32. Start the Backend

Open Terminal 1.

From project root:

```powershell
.\.venv\Scripts\Activate.ps1
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Expected backend:

```text
http://localhost:8000
```

Swagger:

```text
http://localhost:8000/docs
```

Keep this terminal running.

---

# 33. Start the Frontend

Open Terminal 2.

From project root:

```powershell
cd frontend
npm run dev
```

Expected frontend:

```text
http://localhost:5173
```

Open:

```text
http://localhost:5173
```

---

# 34. Normal Two-Terminal Workflow

### Terminal 1 — Backend

```powershell
cd surgi-vision
.\.venv\Scripts\Activate.ps1
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Terminal 2 — Frontend

```powershell
cd surgi-vision\frontend
npm run dev
```

---

# 35. First Application Test

Open:

```text
http://localhost:5173
```

Then:

```text
Register
 ↓
Login
 ↓
Dashboard
```

Refresh the browser.

The account should remain authenticated according to the application's authentication design.

---

# 36. Upload a Video

Go to:

```text
Upload Video
```

Upload a supported surgical video.

Verify:

- Upload succeeds
- Video appears in Video Workspace
- Video metadata exists in PostgreSQL
- Object exists in Supabase Storage
- Video can be played
- Video belongs to the current user

---

# 37. Store & Understand

Store & Understand should create persistent searchable video knowledge.

Conceptually:

```text
Video
 ↓
Processing
 ↓
Temporal observations
 ↓
Knowledge chunks
 ↓
Sentence Transformer embeddings
 ↓
pgvector
 ↓
Knowledge Ready
```

After the knowledge is ready, Q&A should retrieve it rather than reprocessing the entire video for every question.

---

# 38. Analyze Video

Analyze Video performs the expensive AI pipeline:

```text
Video
 ↓
Frame extraction
 ↓
YOLO detection
 ↓
Tracking
 ↓
Detection persistence
 ↓
Temporal knowledge
 ↓
Embeddings
 ↓
Vector storage
 ↓
Analysis results
```

---

# 39. IMPORTANT: Do Not Reprocess an Already Analyzed Video

After a video is analyzed:

```text
Analysis
 ↓
Video Workspace
 ↓
Analysis again
```

must load the existing analysis.

It must NOT start YOLO again just because the React Analysis page mounted again.

The same applies to:

- Browser refresh
- Back/forward navigation
- Opening the same video again
- Re-entering the Analysis page

Only an explicit:

```text
Re-analyze
```

action should intentionally start another expensive analysis.

The backend must also prevent duplicate concurrent analysis jobs.

---

# 40. Real YOLO Detection Verification

A genuine detection record should contain data such as:

```text
Frame: 150
Timestamp: 6.0 sec
Class: Grasper
Confidence: 0.82
Bounding box: [...]
Tracking ID: 4
```

The frontend overlay must be based on actual stored detection records.

Do not use hard-coded boxes in real mode.

---

# 41. Surgical Phase Recognition

If no validated surgical phase model is configured, the UI should clearly state that phase recognition is unavailable.

Do not generate fake phases using:

- hard-coded values
- random values
- mock values
- LLM guesses

Phase recognition must only be marked available when a validated model is actually loaded and verified.

---

# 42. Q&A / RAG

After knowledge and embeddings are ready, test:

```text
Which tools are used in this video?
```

Expected architecture:

```text
Question
 ↓
Question embedding
 ↓
pgvector search
 ↓
Selected video's knowledge
 ↓
Grounded prompt
 ↓
Hugging Face text-generation LLM
 ↓
Generated answer
```

The answer must be generated from the actual retrieved context.

Do not hard-code the answer.

---

# 43. Q&A Must Be Video-Specific

If the user selects:

```text
Video A
```

retrieval must only return:

```text
Video A knowledge
```

It must never retrieve knowledge from:

```text
Video B
Video C
another user's video
unrelated data
```

---

# 44. Q&A Must Be User-Specific

Create:

```text
User A
User B
```

Upload separate videos.

Verify:

```text
User A → User A resources only
User B → User B resources only
```

Try changing IDs manually in API requests.

Unauthorized access must fail.

---

# 45. Hugging Face Runtime Verification

When:

```env
LLM_PROVIDER=huggingface
```

the backend must make a real text-generation request.

It must not silently fall back to mock answers.

If the token is missing/invalid, show a clear configuration/service error.

Safe backend logs may include:

```text
LLM provider: huggingface
LLM model: <model id>
Retrieved context chunks: 5
Generating response...
```

Never log:

```text
HF_TOKEN=...
```

---

# 46. CORS

Normal local origins are:

```text
http://localhost:5173
```

and, if used:

```text
http://127.0.0.1:5173
```

If the browser reports:

```text
No 'Access-Control-Allow-Origin' header
```

check:

1. FastAPI is running.
2. Frontend uses `http://localhost:8000` as backend URL.
3. CORS middleware is configured.
4. The backend did not crash before returning a response.
5. Backend terminal contains no exception.
6. `CORS_ORIGINS` includes the actual frontend origin.

Do not permanently use unrestricted CORS in production.

---

# 47. Frontend API URL

Normal local configuration:

```env
VITE_API_URL=http://localhost:8000
```

The frontend should not accidentally call:

```text
http://localhost:5173/api/...
```

unless the project intentionally uses a Vite proxy.

---

# 48. Private Video Playback

The browser must not receive the Supabase service-role key.

Expected:

```text
React
 ↓
Authenticated FastAPI endpoint
 ↓
Ownership check
 ↓
Supabase signed URL
 ↓
Private video playback
```

Signed URLs should expire.

---

# 49. Live Analysis

Live analysis is separate from uploaded-video analysis.

Conceptually:

```text
Browser / external camera
 ↓
WebRTC / live transport
 ↓
Live session
 ↓
Inference
 ↓
YOLO
 ↓
Live results
 ↓
Optional recording
```

A pairing code identifies the live session; it is not itself a video transport.

---

# 50. Live Recording

When a live session ends:

```text
Stop
 ↓
Save recording?
 ├── Yes → persistent video → Supabase Storage
 └── No  → delete temporary media
```

Both paths must be tested.

---

# 51. Backend Tests

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Run:

```powershell
cd backend
pytest
```

The test suite should cover at least:

- Authentication
- Authorization
- User isolation
- Video CRUD
- Upload
- Analysis creation
- Analysis ownership
- Q&A ownership
- Knowledge retrieval
- Storage abstraction
- AI provider abstraction

---

# 52. Frontend Build

```powershell
cd frontend
npm run build
```

A successful production build should finish without errors.

---

# 53. Health / Swagger

With FastAPI running:

```text
http://localhost:8000/docs
```

should open Swagger.

If the repository has a health endpoint, use the endpoint currently documented by the backend.

Common examples are:

```text
http://localhost:8000/
```

or:

```text
http://localhost:8000/api/health
```

---

# 54. Common Error — `ModuleNotFoundError`

Example:

```text
ModuleNotFoundError: No module named 'ultralytics'
```

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Then:

```powershell
pip install -r backend\requirements.txt
```

If the dependency is absent from `requirements.txt`, update and commit the dependency file.

---

# 55. Common Error — Supabase Package Missing

Example:

```text
ModuleNotFoundError: No module named 'supabase'
```

Run:

```powershell
pip install -r backend\requirements.txt
```

The repository dependency file must contain the required Supabase package.

Do not depend on undocumented manual installations.

---

# 56. Common Error — Database Connection

Check:

```env
DATABASE_URL=...
```

Verify:

- Supabase project exists
- Database password is correct
- Connection string came from Supabase
- Host is correct
- Port is correct
- Password is correctly URL-encoded if necessary
- Internet connection works
- Supabase project is active

Official documentation:

https://supabase.com/docs/guides/database/connecting-to-postgres

---

# 57. Common Error — Authentication Failed

If PostgreSQL reports:

```text
password authentication failed
```

do not randomly modify application code.

Instead:

1. Open Supabase.
2. Open database connection settings.
3. Copy the current connection string.
4. Confirm/reset the database password if necessary.
5. Update `.env`.
6. Restart FastAPI.

---

# 58. Common Error — Bucket Not Found

Open:

```text
Supabase
 → Storage
```

Confirm:

```text
surgivision-videos
```

exists.

Then verify:

```env
SUPABASE_BUCKET=surgivision-videos
```

Spelling must match.

---

# 59. Common Error — Upload Works but Storage Is Empty

Check:

```env
STORAGE_PROVIDER=supabase
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_BUCKET=surgivision-videos
```

Restart the backend.

Then verify the actual object in:

```text
Supabase
 → Storage
 → surgivision-videos
```

Do not rely only on the frontend success message.

---

# 60. Common Error — Model Not Found

If the backend reports:

```text
FileNotFoundError
```

check:

```text
surgi-vision/
└── models/
    └── yolov8s_cholec80.pt
```

and:

```env
MODEL_PATH=models/yolov8s_cholec80.pt
```

---

# 61. Common Error — YOLO Model Fails

Run:

```powershell
python -c "from ultralytics import YOLO; m=YOLO('models/yolov8s_cholec80.pt'); print(m.names)"
```

If it fails, check:

```text
Python version
PyTorch
Ultralytics
model file
model path
CPU/GPU compatibility
```

Do not replace the model without documenting the change.

---

# 62. GPU Verification

If an NVIDIA GPU is available:

```powershell
python -c "import torch; print(torch.cuda.is_available())"
```

Expected when configured:

```text
True
```

If:

```text
False
```

the project can still run on CPU, but inference may be slower.

Install the PyTorch build compatible with the repository rather than randomly choosing a CUDA version.

---

# 63. Why Analysis Takes Time

Video analysis is computationally expensive:

```text
Video
 ↓
Frames
 ↓
YOLO
 ↓
Tracking
 ↓
Temporal aggregation
 ↓
Embeddings
```

The application may process every Nth frame, for example:

```env
PROCESS_EVERY_N_FRAMES=5
```

Do not change this value without understanding the speed/accuracy trade-off.

---

# 64. Persistent Analysis Results

A completed analysis should be treated as a reusable asset.

```text
First analysis
 ↓
AI processing
 ↓
Results saved
 ↓
COMPLETE

Later visit
 ↓
Read existing results
 ↓
No YOLO rerun
```

The backend must prevent duplicate processing jobs.

---

# 65. Git Ignore

The repository should ignore:

```gitignore
.env
.env.*
!.env.example

.venv/
venv/
myenv/

__pycache__/
*.pyc

node_modules/
dist/

*.db
test.db

backend/uploads/
uploads/

temporary/
```

Never commit secrets.

---

# 66. Files That Must Not Be Committed

Never commit:

```text
.env
.env.local
.env.production
database passwords
Supabase service-role/backend secrets
Hugging Face tokens
JWT secrets
.venv/
venv/
myenv/
node_modules/
dist/
temporary videos
local database files
temporary processed videos
```

Model weights must be distributed only when their size and license permit it. Otherwise document how to download them.

---

# 67. Git First-Time Setup

If Git identity is not configured:

```powershell
git config --global user.name "Your Name"
git config --global user.email "your-email@example.com"
```

Check:

```powershell
git config --global --list
```

---

# 68. Daily Team Workflow

```text
Pull latest code
 ↓
Activate .venv
 ↓
Install dependency changes
 ↓
Check .env
 ↓
Check model
 ↓
Run migrations
 ↓
Start backend
 ↓
Start frontend
 ↓
Test
 ↓
Run backend tests
 ↓
Run frontend build
 ↓
Check git diff/status
 ↓
Commit
 ↓
Push
```

---

# 69. Pull Latest Code

```powershell
git pull origin main
```

If working on a feature branch:

```powershell
git pull
```

Do not overwrite local changes without reviewing them.

---

# 70. After a Dependency Change

If Python requirements changed:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

If frontend lockfile changed:

```powershell
cd frontend
npm ci
cd ..
```

---

# 71. After a Database Migration Change

```powershell
cd backend
alembic upgrade head
cd ..
```

---

# 72. Creating a Migration

When the database schema changes:

```powershell
cd backend
alembic revision --autogenerate -m "describe schema change"
```

Inspect the generated migration.

Then:

```powershell
alembic upgrade head
```

Commit the migration.

Never blindly commit an autogenerated migration without reviewing it.

---

# 73. Shared vs Individual Supabase Projects

### Shared development project

```text
Developer A ─┐
Developer B ─┼──> Shared Supabase DEV
Developer C ─┘
```

This is convenient for team integration testing.

### Individual projects

```text
Developer A → Supabase A
Developer B → Supabase B
Developer C → Supabase C
```

This gives each developer isolated database/storage resources.

Both are valid.

For a student team, a shared development project can be convenient, while individual projects are safer for experimentation.

---

# 74. Team Credential Handling

Do not send secrets through public/group chat if avoidable.

Recommended:

```text
Team secret manager/password manager
 ↓
Developer creates local .env
 ↓
.env stays uncommitted
```

Never put shared credentials into GitHub.

---

# 75. If a Secret Is Leaked

Treat it as compromised.

Rotate:

```text
Supabase backend/service key
Hugging Face token
Database password
SECRET_KEY
```

Then update `.env`.

Deleting the secret from the latest source file is not enough if it was previously committed or exposed.

---

# 76. Local vs Production

Local:

```env
APP_ENV=development
VITE_API_URL=http://localhost:8000
CORS_ORIGINS=http://localhost:5173
```

Production should use:

```text
HTTPS
production domain
restricted CORS
production secrets
secure authentication configuration
production database
production storage
monitoring
```

Never reuse development secrets in production.

---

# 77. Docker

If the repository's Docker configuration is used:

```powershell
docker compose up --build
```

Stop:

```powershell
docker compose down
```

Check:

```powershell
docker ps
```

Follow the current `docker-compose.yml` because ports and services can change.

---

# 78. Useful Local URLs

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend | http://localhost:8000 |
| FastAPI Swagger | http://localhost:8000/docs |
| Supabase Dashboard | https://supabase.com/dashboard |
| Hugging Face | https://huggingface.co |
| GitHub Repository | https://github.com/AIML-C04/surgi-vision |

---

# 79. Official Documentation

- Python: https://docs.python.org/3/
- Node.js: https://nodejs.org/docs/
- Git: https://git-scm.com/doc
- FastAPI: https://fastapi.tiangolo.com/
- SQLAlchemy: https://docs.sqlalchemy.org/
- Alembic: https://alembic.sqlalchemy.org/
- React: https://react.dev/
- Vite: https://vite.dev/
- Supabase: https://supabase.com/docs
- Supabase database connections: https://supabase.com/docs/guides/database/connecting-to-postgres
- Supabase CLI: https://supabase.com/docs/guides/local-development/cli/getting-started
- Hugging Face: https://huggingface.co/docs
- Hugging Face tokens: https://huggingface.co/docs/hub/security-tokens
- Ultralytics: https://docs.ultralytics.com/
- Sentence Transformers: https://sbert.net/
- FFmpeg: https://ffmpeg.org/

---

# 80. Optional Supabase CLI

Use the Supabase CLI only if the repository adopts it.

Official documentation:

https://supabase.com/docs/guides/local-development/cli/getting-started

If the repository contains a `supabase/` directory and documents CLI migrations, follow those instructions.

Otherwise, use the existing Alembic migration workflow.

---

# 81. Fresh-Machine Quick Setup

```powershell
git clone https://github.com/AIML-C04/surgi-vision.git
cd surgi-vision

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r backend\requirements.txt

cd frontend
npm ci
cd ..

Copy-Item .env.example .env
```

Configure `.env`, download the model, configure Supabase and Hugging Face, then:

```powershell
cd backend
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Second terminal:

```powershell
cd surgi-vision\frontend
npm run dev
```

Open:

```text
http://localhost:5173
```

---

# 82. Fresh-Machine Verification

```text
[ ] Python installed
[ ] Node.js installed
[ ] Git installed
[ ] Docker installed if needed
[ ] FFmpeg installed if needed

[ ] Repository cloned
[ ] .venv created
[ ] Backend dependencies installed
[ ] Frontend dependencies installed

[ ] Supabase project ready
[ ] DATABASE_URL configured
[ ] Supabase URL configured
[ ] Backend Supabase secret configured
[ ] surgivision-videos bucket created
[ ] Bucket private
[ ] pgvector enabled
[ ] Migrations applied

[ ] YOLO model downloaded
[ ] MODEL_PATH correct
[ ] MODEL_PROVIDER=real

[ ] Hugging Face account created
[ ] HF token configured
[ ] LLM provider configured

[ ] Backend starts
[ ] Frontend starts
[ ] Registration works
[ ] Login works
[ ] Upload works
[ ] Storage works
[ ] Playback works
[ ] Real YOLO works
[ ] Detections persist
[ ] Tracking persists where available
[ ] Knowledge works
[ ] Embeddings work
[ ] pgvector retrieval works
[ ] Real LLM Q&A works
[ ] Video-specific retrieval works
[ ] User isolation works
[ ] Reopening Analysis does not reprocess
[ ] Backend tests pass
[ ] Frontend build passes
```

---

# 83. How to Prove the Project Is Working

Do not rely only on green UI indicators.

### Database

Verify records actually exist.

### Storage

Verify the video object exists in the private Supabase bucket.

### YOLO

Verify actual:

```text
frame
timestamp
class
confidence
bounding box
tracking ID
```

### Embeddings

Verify actual vectors exist in PostgreSQL/pgvector.

### RAG

Verify retrieved chunks belong to the selected video and current user.

### LLM

Verify the Hugging Face provider actually generated the response.

### Persistence

Verify reopening the Analysis page does not run YOLO again.

---

# 84. No Fake AI Rule

Real mode must never silently use mock output.

Do not use:

```text
fake boxes
fake confidence
fake tracking
fake phases
fake knowledge
fake embeddings
fake Q&A
hard-coded AI answers
random AI output
```

If a real dependency fails:

```text
Show an understandable error.
```

Do not pretend the feature worked.

---

# 85. Troubleshooting Order

### Backend

```text
Python
 ↓
Virtual environment
 ↓
Dependencies
 ↓
.env
 ↓
Database
 ↓
Imports
```

### Upload

```text
Authentication
 ↓
Video endpoint
 ↓
Supabase credentials
 ↓
Bucket
 ↓
Storage permissions
 ↓
Backend logs
```

### YOLO

```text
Model path
 ↓
Model file
 ↓
Ultralytics
 ↓
PyTorch
 ↓
CPU/GPU
 ↓
Video format
```

### Q&A

```text
Backend
 ↓
CORS
 ↓
Authentication
 ↓
Video ownership
 ↓
Knowledge
 ↓
Embeddings
 ↓
pgvector
 ↓
HF token
 ↓
LLM model
 ↓
Hugging Face request
```

### Repeated analysis

```text
Analysis status
 ↓
Existing analysis lookup
 ↓
Frontend mount behavior
 ↓
Duplicate job protection
 ↓
Database idempotency
```

---

# 86. Team Lead Responsibilities

The project owner/team lead should ensure the repository contains:

```text
README.md
LOCAL_SETUP.md
.env.example
.gitignore
backend/requirements.txt
frontend/package.json
frontend/package-lock.json
database migrations
model documentation
```

Whenever any of these change:

```text
Python version
Node version
dependency versions
database schema
environment variable
Supabase bucket
AI model
LLM provider
storage provider
startup command
migration process
```

update this setup document in the same change.

---

# 87. What the Repository Provides vs What Developers Create

### Repository provides

```text
Source code
requirements.txt
package.json
package-lock.json
database migrations
.env.example
.gitignore
Docker configuration
documentation
```

### Developer creates locally

```text
.env
.venv
node_modules
Supabase credentials
Hugging Face token
JWT secret
model weights when not committed
local test data
```

This is the correct separation.

---

# 88. Final Expected Flow

After setup:

```text
Open http://localhost:5173
        ↓
Register
        ↓
Login
        ↓
Upload Video
        ↓
Video Workspace
        ↓
Store & Understand / Analyze Video
        ↓
Real YOLO detection
        ↓
Persistent tracking/detections
        ↓
Temporal knowledge
        ↓
Embeddings
        ↓
pgvector
        ↓
Video-specific RAG
        ↓
Hugging Face text-generation LLM
        ↓
Q&A + evidence
        ↓
Analysis / reports
```

The project should persist completed analysis so:

```text
Analysis
 ↓
Video Workspace
 ↓
Analysis
```

does not re-run the expensive pipeline.

---

# 89. Final Team Checklist

```text
ENVIRONMENT
[ ] Python
[ ] Node.js
[ ] Git
[ ] Docker if required
[ ] FFmpeg if required

REPOSITORY
[ ] Clone
[ ] .venv
[ ] Backend dependencies
[ ] Frontend dependencies

SUPABASE
[ ] Project
[ ] Database password
[ ] DATABASE_URL
[ ] Supabase URL
[ ] Backend secret
[ ] Private storage bucket
[ ] pgvector
[ ] migrations

AI
[ ] YOLO model
[ ] MODEL_PROVIDER=real
[ ] Hugging Face account
[ ] HF token
[ ] LLM provider/model

APPLICATION
[ ] Backend on 8000
[ ] Frontend on 5173
[ ] Registration
[ ] Login
[ ] Upload
[ ] Playback
[ ] YOLO
[ ] Tracking
[ ] Knowledge
[ ] Embeddings
[ ] pgvector
[ ] RAG
[ ] Real LLM
[ ] User isolation
[ ] Persistent analysis
[ ] No duplicate processing

QUALITY
[ ] Backend tests
[ ] Frontend build
[ ] No secrets committed
[ ] Git status reviewed
```

---

# 90. Official Project Resources

**GitHub repository**

https://github.com/AIML-C04/surgi-vision

**Current surgical YOLO model**

https://huggingface.co/cesaraha/yolov8s-surgical-instrument-detection-cholec80

**Supabase**

https://supabase.com/

**Hugging Face**

https://huggingface.co/

---

## Maintenance

**Last updated:** 2026-09-04

This document must be updated whenever installation, dependencies, environment variables, database setup, storage setup, model setup, startup commands, or testing procedures change.
