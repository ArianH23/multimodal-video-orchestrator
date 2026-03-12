from abc import ABC, abstractmethod


class StoragePort(ABC):
    @abstractmethod
    def save(self, file_path: str, data: bytes) -> str:
        pass

    @abstractmethod
    def retrieve(self, file_path: str) -> bytes:
        pass

    @abstractmethod
    def move(self, source_path: str, destination_path: str) -> str:
        """Moves a file and returns the new absolute path."""
        pass

    @abstractmethod
    def delete(self, file_path: str) -> bool:
        """Deletes a file, returning True if successful."""
        pass