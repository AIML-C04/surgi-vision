import os, sys
sys.path.insert(0, '.')
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(r'c:\6136\MAJOR PROJECT\Surgi_vision\.env'))

from app.core.database import SessionLocal
from app.models.video import Video
from app.models.user import User

db = SessionLocal()

# Get all videos
videos = db.query(Video).all()
for v in videos:
    user = db.query(User).filter(User.id == v.user_id).first()
    email = user.email if user else "MISSING USER"
    local_path = os.path.join('uploads', v.file_path)
    local_exists = os.path.exists(local_path)
    print(f"Video: {v.id}")
    print(f"  title: {v.title}")
    print(f"  user: {v.user_id} ({email})")
    print(f"  file_path: {v.file_path}")
    print(f"  local exists: {local_exists}")
    print()

print(f"Total videos: {len(videos)}")

# List all users
print("\n--- Users ---")
users = db.query(User).all()
for u in users:
    print(f"User: {u.id} | {u.email}")
