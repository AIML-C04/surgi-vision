import os
from typing import BinaryIO
from .base import StorageProvider

class SupabaseStorageProvider(StorageProvider):
    def __init__(self):
        # Initialize Supabase client
        from supabase import create_client, Client
        url: str = os.environ.get("SUPABASE_URL", "")
        key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        self.bucket = os.environ.get("SUPABASE_BUCKET", "videos")
        
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
        
        res = self.supabase.storage.from_(self.bucket).upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": "video/mp4"} # Or get mime type
        )
        return file_path

    def get_file_url(self, file_path: str) -> str:
        if not self.supabase:
            return ""
        # Create a signed URL valid for 1 hour
        res = self.supabase.storage.from_(self.bucket).create_signed_url(file_path, 3600)
        if 'signedURL' in res:
            return res['signedURL']
        return ""

    def delete_file(self, file_path: str) -> bool:
        if not self.supabase:
            return False
        res = self.supabase.storage.from_(self.bucket).remove([file_path])
        return len(res) > 0
