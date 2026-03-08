from abc import ABC, abstractmethod

class StoragePort(ABC):
    @abstractmethod
    def save(self, file_path: str, data: bytes) -> str:
        """Saves the raw bytes and returns the final URI/path."""
        pass

    @abstractmethod
    def retrieve(self, file_path: str) -> bytes:
        """Retrieves raw bytes from storage."""
        pass