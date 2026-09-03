from abc import ABC, abstractmethod
from typing import BinaryIO

class StorageProvider(ABC):
    @abstractmethod
    def upload_file(self, user_id: str, file_id: str, file_name: str, file: BinaryIO) -> str:
        """Uploads a file and returns the storage path/URI"""
        pass
        
    @abstractmethod
    def get_file_url(self, file_path: str) -> str:
        """Returns an accessible URL for the file"""
        pass
        
    @abstractmethod
    def delete_file(self, file_path: str) -> bool:
        """Deletes a file"""
        pass
