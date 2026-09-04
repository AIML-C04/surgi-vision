import os
from typing import BinaryIO
from .base import StorageProvider

class SupabaseStorageProvider(StorageProvider):
    def __init__(self):
        # Initialize Supabase client
        from supabase import create_client, Client
        url: str = os.environ.get("SUPABASE_URL", "")
        key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        self.bucket = os.environ.get("SUPABASE_BUCKET", "surgivision-videos")
        
        if url and key:
            self.supabase: Client = create_client(url, key)
        else:
            self.supabase = None
            
    def upload_file(self, user_id: str, file_id: str, file_name: str, file: BinaryIO) -> str:
        if not self.supabase:
            raise Exception("Supabase not configured")
            
        file_path = f"users/{user_id}/videos/{file_id}_{file_name}"
        # Read file contents
        file_bytes = file.read()
        
        # Always save a local copy as safety net
        local_dir = os.path.join("uploads", "users", str(user_id), "videos")
        os.makedirs(local_dir, exist_ok=True)
        local_full_path = os.path.join("uploads", file_path)
        with open(local_full_path, "wb") as f:
            f.write(file_bytes)
        
        # Upload to Supabase
        try:
            res = self.supabase.storage.from_(self.bucket).upload(
                path=file_path,
                file=file_bytes,
                file_options={"content-type": "video/mp4"}
            )
        except Exception as e:
            print(f"Supabase upload error: {e}")
            if os.path.exists(local_full_path):
                os.remove(local_full_path)
            raise Exception(f"Supabase storage upload failed: {str(e)}")
        
        return file_path

    def get_file_url(self, file_path: str) -> str:
        if not self.supabase:
            # No Supabase client configured, try local fallback
            return self._local_fallback(file_path)
        try:
            # Create a signed URL valid for 1 hour
            res = self.supabase.storage.from_(self.bucket).create_signed_url(file_path, 3600)
            if isinstance(res, dict) and 'signedURL' in res:
                return res['signedURL']
            # supabase-py v2 returns an object with .signed_url attribute
            if hasattr(res, 'signed_url') and res.signed_url:
                return res.signed_url
            if isinstance(res, dict) and 'signed_url' in res:
                return res['signed_url']
            if isinstance(res, str) and res.startswith('http'):
                return res
            # If we got here, the response was unexpected — try local fallback
            print(f"Unexpected Supabase signed URL response: {type(res)} {res}")
            return self._local_fallback(file_path)
        except Exception as e:
            print(f"Supabase signed URL error: {e}")
            # Fall back to local file serving if the file exists on disk
            return self._local_fallback(file_path)

    def _local_fallback(self, file_path: str) -> str:
        """Fall back to serving the file from the local uploads directory."""
        local_path = os.path.join("uploads", file_path)
        if os.path.exists(local_path):
            print(f"Supabase unavailable, serving locally: /files/{file_path}")
            return f"/files/{file_path}"
        return ""

    def delete_file(self, file_path: str) -> bool:
        if not self.supabase:
            return False
        res = self.supabase.storage.from_(self.bucket).remove([file_path])
        return len(res) > 0
