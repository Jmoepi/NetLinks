"""Document byte storage (plan A9): local directory by default, S3 when STORAGE_BACKEND=s3."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

from app.config import get_settings


class DocumentStore(Protocol):
    def put(self, key: str, data: bytes) -> str: ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


def safe_filename(filename: str) -> str:
    """Basename with only safe characters (no path traversal via uploaded filenames)."""
    name = Path(filename.replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return name or "document.pdf"


def document_key(sme_slug: str, sha256: str, filename: str) -> str:
    return f"smes/{safe_filename(sme_slug)}/{sha256[:16]}_{safe_filename(filename)}"


class LocalDocumentStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Storage key escapes the upload directory")
        return path

    def put(self, key: str, data: bytes) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class S3DocumentStore:
    """Private bucket, server-side encryption. Production target only; not exercised in the demo."""

    def __init__(self, bucket: str) -> None:
        import boto3

        if not bucket:
            raise ValueError("S3_BUCKET must be set when STORAGE_BACKEND=s3")
        self.bucket = bucket
        self._s3 = boto3.client("s3")

    def put(self, key: str, data: bytes) -> str:
        self._s3.put_object(Bucket=self.bucket, Key=key, Body=data, ServerSideEncryption="AES256")
        return key

    def get(self, key: str) -> bytes:
        return self._s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self._s3.delete_object(Bucket=self.bucket, Key=key)


def get_store() -> DocumentStore:
    settings = get_settings()
    if settings.storage_backend == "s3":
        return S3DocumentStore(settings.s3_bucket)
    return LocalDocumentStore(settings.upload_dir)
