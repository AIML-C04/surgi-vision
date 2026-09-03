import os
from .base import StorageProvider
from .local import LocalStorageProvider
from .supabase import SupabaseStorageProvider

def get_storage_provider() -> StorageProvider:
    provider_type = os.environ.get("STORAGE_PROVIDER", "local").lower()
    
    if provider_type == "supabase":
        return SupabaseStorageProvider()
    
    return LocalStorageProvider()
