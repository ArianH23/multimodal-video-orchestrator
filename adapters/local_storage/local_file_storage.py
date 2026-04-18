import os
import shutil
from domain.ports.storage import StoragePort


class LocalFileStorageAdapter(StoragePort):
    def __init__(self, base_directory: str):
        self.base_directory = base_directory
        os.makedirs(self.base_directory, exist_ok=True)

    def save(self, file_path: str, data: bytes) -> str:
        full_path = os.path.join(self.base_directory, file_path)

        target_directory = os.path.dirname(full_path)
        os.makedirs(target_directory, exist_ok=True)

        with open(full_path, 'wb') as file:
            file.write(data)

        return full_path

    def retrieve(self, file_path: str) -> bytes:
        full_path = os.path.join(self.base_directory, file_path)
        with open(full_path, 'rb') as file:
            return file.read()

    def move(self, source_path: str, destination_path: str) -> str:
        full_source = os.path.join(self.base_directory, source_path)
        full_dest = os.path.join(self.base_directory, destination_path)

        # Double-check: Ensure the destination directory actually exists before moving
        dest_dir = os.path.dirname(full_dest)
        os.makedirs(dest_dir, exist_ok=True)

        try:
            shutil.move(full_source, full_dest)
            return full_dest
        except FileNotFoundError:
            raise ValueError(f"Cannot move file: Source {source_path} does not exist.")

    def delete(self, file_path: str) -> bool:
        full_path = os.path.join(self.base_directory, file_path)
        try:
            os.remove(full_path)
            return True
        except FileNotFoundError:
            return False
