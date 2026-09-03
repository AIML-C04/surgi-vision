import os
import shutil
from typing import BinaryIO
from .base import StorageProvider
from app.core.config import settings

class LocalStorageProvider(StorageProvider):
    def __init__(self, base_dir: str = "uploads"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        
    def upload_file(self, user_id: str, file_id: str, file_name: str, file: BinaryIO) -> str:
        # e.g., users/{user_id}/videos/{file_id}_{file_name}
        # For local, we just flatten it or use directories. Let's use directories.
        user_dir = os.path.join(self.base_dir, "users", str(user_id), "videos")
        os.makedirs(user_dir, exist_ok=True)
        
        file_path = os.path.join(user_dir, f"{file_id}_{file_name}")
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file, buffer)
            
        # Return a relative path to be stored in DB
        return f"users/{user_id}/videos/{file_id}_{file_name}"

    def get_file_url(self, file_path: str) -> str:
        # In development, serve through static or a dedicated endpoint.
        # We can serve it through FastAPI by exposing /files/{file_path}
        # For now, return the relative path prefix
        return f"/files/{file_path}"

    def delete_file(self, file_path: str) -> bool:
        full_path = os.path.join(self.base_dir, file_path)
        if os.path.exists(full_path):
            os.remove(full_path)
            return True
        return False
