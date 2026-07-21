"""
Immutable Storage / Bucket Providers.

Provides an abstraction layer for storing, retrieving, and verifying files
immutably. Includes local (file-level read-only CAS), GCS, and S3 backends.
"""

import hashlib
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

logger = logging.getLogger("phantom.providers.storage")

# Default storage directory in home folder
DEFAULT_LOCAL_PATH = Path.home() / ".phantom" / "buckets"


class ImmutableBucketProvider(ABC):
    """Abstract base class for all immutable storage providers."""

    @abstractmethod
    def put(self, content: bytes | str, key: str | None = None) -> str:
        """
        Store content in the bucket.

        If key is None, uses Content-Addressable Storage (CAS) with SHA-256 hash as the key.
        If key is provided and already exists, raises a FileExistsError.

        Args:
            content: Raw bytes or string to store.
            key: Optional unique identifier.

        Returns:
            The key/address of the stored content.

        Raises:
            FileExistsError: If key is already occupied.
        """
        pass

    @abstractmethod
    def get(self, key: str) -> bytes:
        """
        Retrieve content by key.

        Args:
            key: Unique identifier.

        Returns:
            Raw bytes of the content.

        Raises:
            FileNotFoundError: If the key does not exist.
        """
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """
        Check if a key exists in the storage.

        Args:
            key: Unique identifier.

        Returns:
            True if exists, False otherwise.
        """
        pass

    @abstractmethod
    def list_keys(self) -> list[str]:
        """
        List all keys in the storage.

        Returns:
            List of all stored keys.
        """
        pass

    def _get_bytes(self, content: bytes | str) -> bytes:
        """Helper to ensure content is bytes."""
        if isinstance(content, str):
            return content.encode("utf-8")
        return content

    def _compute_hash(self, content_bytes: bytes) -> str:
        """Helper to compute SHA-256 hash of content."""
        return hashlib.sha256(content_bytes).hexdigest()


class LocalImmutableBucketProvider(ImmutableBucketProvider):
    """
    Local filesystem implementation of an immutable bucket.
    Enforces immutability at the file system level by marking written files read-only (0o444).
    """

    def __init__(self, base_dir: Path | str | None = None):
        self.base_dir = Path(base_dir or DEFAULT_LOCAL_PATH).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized LocalImmutableBucketProvider at: {self.base_dir}")

    def _safe_path(self, key: str) -> Path:
        """Resolve target path and check for path traversal."""
        target = (self.base_dir / key).resolve()
        # Verify target is inside base_dir to prevent directory traversal
        try:
            target.relative_to(self.base_dir)
        except ValueError as e:
            raise ValueError(f"Path traversal attempt detected: {key}") from e
        return target

    def put(self, content: bytes | str, key: str | None = None) -> str:
        content_bytes = self._get_bytes(content)
        target_key = key or self._compute_hash(content_bytes)
        file_path = self._safe_path(target_key)

        # Check if already exists
        if file_path.exists():
            raise FileExistsError(f"Key '{target_key}' already exists in storage.")

        # Ensure parent directory exists (for subdirectories inside keys, if any)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write data
        file_path.write_bytes(content_bytes)

        # Harden permissions: make the file read-only (0o444)
        try:
            os.chmod(file_path, 0o444)
        except OSError as e:
            logger.warning(f"Could not set read-only permissions for {file_path}: {e}")

        logger.debug(f"Saved immutable object to {file_path}")
        return target_key

    def get(self, key: str) -> bytes:
        file_path = self._safe_path(key)
        if not file_path.is_file():
            raise FileNotFoundError(f"Key '{key}' not found in storage.")
        return file_path.read_bytes()

    def exists(self, key: str) -> bool:
        try:
            file_path = self._safe_path(key)
            return file_path.is_file()
        except ValueError:
            return False

    def list_keys(self) -> list[str]:
        keys = []
        for p in self.base_dir.rglob("*"):
            if p.is_file():
                # Get path relative to base_dir
                rel_path = p.relative_to(self.base_dir)
                keys.append(str(rel_path))
        return sorted(keys)


class GCSImmutableBucketProvider(ImmutableBucketProvider):
    """
    Google Cloud Storage implementation of an immutable bucket.
    Note: Requires google-cloud-storage library.
    """

    def __init__(self, bucket_name: str, project_id: str | None = None):
        try:
            from google.cloud import storage
        except ImportError as e:
            raise ImportError(
                "google-cloud-storage is required to use GCSImmutableBucketProvider. "
                "Install it or configure a different provider."
            ) from e

        self.bucket_name = bucket_name
        self.client = storage.Client(project=project_id)
        self.bucket = self.client.bucket(bucket_name)
        logger.info(f"Initialized GCSImmutableBucketProvider for bucket: {bucket_name}")

    def put(self, content: bytes | str, key: str | None = None) -> str:
        content_bytes = self._get_bytes(content)
        target_key = key or self._compute_hash(content_bytes)
        blob = self.bucket.blob(target_key)

        # Check-before-write to prevent overwriting
        if blob.exists():
            raise FileExistsError(
                f"Key '{target_key}' already exists in bucket {self.bucket_name}."
            )

        blob.upload_from_string(content_bytes)
        logger.debug(f"Uploaded immutable object {target_key} to GCS bucket {self.bucket_name}")
        return target_key

    def get(self, key: str) -> bytes:
        blob = self.bucket.blob(key)
        if not blob.exists():
            raise FileNotFoundError(f"Key '{key}' not found in GCS bucket {self.bucket_name}.")
        return blob.download_as_bytes()

    def exists(self, key: str) -> bool:
        blob = self.bucket.blob(key)
        return blob.exists()

    def list_keys(self) -> list[str]:
        blobs = self.client.list_blobs(self.bucket)
        return sorted([blob.name for blob in blobs])


class S3ImmutableBucketProvider(ImmutableBucketProvider):
    """
    AWS S3 or MinIO implementation of an immutable bucket.
    Note: Requires boto3 library.
    """

    def __init__(
        self,
        bucket_name: str,
        endpoint_url: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        region_name: str | None = None,
    ):
        try:
            import boto3
        except ImportError as e:
            raise ImportError(
                "boto3 is required to use S3ImmutableBucketProvider. "
                "Install it or configure a different provider."
            ) from e

        self.bucket_name = bucket_name
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
        )
        logger.info(f"Initialized S3ImmutableBucketProvider for bucket: {bucket_name}")

    def put(self, content: bytes | str, key: str | None = None) -> str:
        content_bytes = self._get_bytes(content)
        target_key = key or self._compute_hash(content_bytes)

        # Check if already exists
        if self.exists(target_key):
            raise FileExistsError(
                f"Key '{target_key}' already exists in S3 bucket {self.bucket_name}."
            )

        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=target_key,
            Body=content_bytes,
        )
        logger.debug(f"Uploaded immutable object {target_key} to S3 bucket {self.bucket_name}")
        return target_key

    def get(self, key: str) -> bytes:
        from botocore.exceptions import ClientError

        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return response["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                raise FileNotFoundError(
                    f"Key '{key}' not found in S3 bucket {self.bucket_name}."
                ) from e
            raise

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return False
            raise

    def list_keys(self) -> list[str]:
        paginator = self.s3_client.get_paginator("list_objects_v2")
        keys = []
        for page in paginator.paginate(Bucket=self.bucket_name):
            if "Contents" in page:
                for obj in page["Contents"]:
                    keys.append(obj["Key"])
        return sorted(keys)


def get_storage_provider(
    provider_type: str | None = None, **kwargs: Any
) -> ImmutableBucketProvider:
    """
    Factory to construct a storage provider based on type.

    If provider_type is None, checks environment variables:
      - GCP_STORAGE_BUCKET: returns GCSImmutableBucketProvider
      - S3_STORAGE_BUCKET: returns S3ImmutableBucketProvider
      - Default: returns LocalImmutableBucketProvider

    Args:
        provider_type: 'local', 'gcs', or 's3'.
        kwargs: Provider-specific configuration.
    """
    p_type = (provider_type or os.environ.get("PHANTOM_STORAGE_TYPE", "")).lower()

    if p_type == "gcs" or (not p_type and "GCP_STORAGE_BUCKET" in os.environ):
        bucket_name = kwargs.get("bucket_name") or os.environ.get("GCP_STORAGE_BUCKET")
        if not bucket_name:
            raise ValueError(
                "GCP_STORAGE_BUCKET env var or bucket_name parameter is required for GCS provider"
            )
        project_id = kwargs.get("project_id") or os.environ.get("GCP_PROJECT_ID")
        return GCSImmutableBucketProvider(bucket_name=bucket_name, project_id=project_id)

    if p_type == "s3" or (not p_type and "S3_STORAGE_BUCKET" in os.environ):
        bucket_name = kwargs.get("bucket_name") or os.environ.get("S3_STORAGE_BUCKET")
        if not bucket_name:
            raise ValueError(
                "S3_STORAGE_BUCKET env var or bucket_name parameter is required for S3 provider"
            )
        return S3ImmutableBucketProvider(
            bucket_name=bucket_name,
            endpoint_url=kwargs.get("endpoint_url") or os.environ.get("S3_ENDPOINT_URL"),
            aws_access_key_id=kwargs.get("aws_access_key_id")
            or os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=kwargs.get("aws_secret_access_key")
            or os.environ.get("AWS_SECRET_ACCESS_KEY"),
            region_name=kwargs.get("region_name") or os.environ.get("AWS_REGION"),
        )

    # Default/Local
    base_dir = kwargs.get("base_dir") or os.environ.get("PHANTOM_STORAGE_DIR")
    return LocalImmutableBucketProvider(base_dir=base_dir)
