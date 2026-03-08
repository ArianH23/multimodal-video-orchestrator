import os
from domain.ports.storage import StoragePort


class LocalFileStorageAdapter(StoragePort):
    def __init__(self, base_directory: str):
        self.base_directory = base_directory
        os.makedirs(self.base_directory, exist_ok=True)

    def save(self, file_path: str, data: bytes) -> str:
        full_path = os.path.join(self.base_directory, file_path)

        with open(full_path, 'wb') as file:
            file.write(data)

        return full_path

    def retrieve(self, file_path: str) -> bytes:
        full_path = os.path.join(self.base_directory, file_path)
        with open(full_path, 'rb') as file:
            return file.read()