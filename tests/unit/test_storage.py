# ruff: noqa: E402
"""
Unit tests for the storage providers module.
"""

import os
import stat
import sys
from unittest.mock import MagicMock, patch


# Define custom MockClientError to simulate S3 ClientError in tests
class MockClientError(Exception):
    def __init__(self, response, operation_name):
        self.response = response
        self.operation_name = operation_name
        super().__init__(f"ClientError: {response}")


# Setup mocks in sys.modules BEFORE importing the storage module
mock_storage = MagicMock()
mock_storage.Client = MagicMock()

mock_boto3 = MagicMock()
mock_boto3.client = MagicMock()

mock_botocore_exceptions = MagicMock()
mock_botocore_exceptions.ClientError = MockClientError

mock_google_cloud = MagicMock()
mock_google_cloud.storage = mock_storage

sys.modules["google"] = MagicMock()
sys.modules["google.cloud"] = mock_google_cloud
sys.modules["google.cloud.storage"] = mock_storage
sys.modules["boto3"] = mock_boto3
sys.modules["botocore"] = MagicMock()
sys.modules["botocore.exceptions"] = mock_botocore_exceptions

import pytest

from phantom.providers.storage import (
    GCSImmutableBucketProvider,
    LocalImmutableBucketProvider,
    S3ImmutableBucketProvider,
    get_storage_provider,
)

pytestmark = pytest.mark.unit


class TestLocalImmutableBucketProvider:
    """Tests for LocalImmutableBucketProvider."""

    def test_init_creates_dir(self, tmp_path):
        base_dir = tmp_path / "test-bucket"
        assert not base_dir.exists()

        provider = LocalImmutableBucketProvider(base_dir=base_dir)
        assert base_dir.exists()
        assert provider.base_dir == base_dir.resolve()

    def test_put_and_get_with_explicit_key(self, tmp_path):
        provider = LocalImmutableBucketProvider(base_dir=tmp_path)
        content = b"hello world"
        key = "test_key.txt"

        saved_key = provider.put(content, key=key)
        assert saved_key == key
        assert provider.exists(key)

        retrieved = provider.get(key)
        assert retrieved == content

    def test_put_and_get_string_content(self, tmp_path):
        provider = LocalImmutableBucketProvider(base_dir=tmp_path)
        content = "hello world string"
        key = "string_key.txt"

        saved_key = provider.put(content, key=key)
        assert saved_key == key
        assert provider.get(key) == b"hello world string"

    def test_content_addressable_storage(self, tmp_path):
        provider = LocalImmutableBucketProvider(base_dir=tmp_path)
        content = b"content addressed text"

        # SHA-256 of b"content addressed text"
        expected_hash = "f8c25a4a1b84a7bf33d5907cec736a56cea934bf8cd36d5e88075853779e7a5a"

        saved_key = provider.put(content)
        assert saved_key == expected_hash
        assert provider.get(saved_key) == content

    def test_immutability_duplicate_key_raises(self, tmp_path):
        provider = LocalImmutableBucketProvider(base_dir=tmp_path)
        provider.put(b"first content", key="duplicate")

        with pytest.raises(FileExistsError, match="already exists"):
            provider.put(b"second content", key="duplicate")

    def test_path_traversal_protection(self, tmp_path):
        provider = LocalImmutableBucketProvider(base_dir=tmp_path)

        with pytest.raises(ValueError, match="Path traversal attempt detected"):
            provider.put(b"evil content", key="../evil.txt")

        with pytest.raises(ValueError, match="Path traversal attempt detected"):
            provider.get("../evil.txt")

        assert not provider.exists("../evil.txt")

    def test_file_permission_hardening(self, tmp_path):
        provider = LocalImmutableBucketProvider(base_dir=tmp_path)
        key = "secure.bin"
        provider.put(b"protected payload", key=key)

        file_path = provider._safe_path(key)
        mode = file_path.stat().st_mode
        # Check that owner, group, and others do not have write permissions
        # (mode & stat.S_IWRITE) should be 0
        assert (mode & stat.S_IWRITE) == 0

    def test_get_nonexistent_raises(self, tmp_path):
        provider = LocalImmutableBucketProvider(base_dir=tmp_path)
        with pytest.raises(FileNotFoundError):
            provider.get("missing.bin")

    def test_list_keys(self, tmp_path):
        provider = LocalImmutableBucketProvider(base_dir=tmp_path)
        provider.put(b"1", key="a.txt")
        provider.put(b"2", key="sub/b.txt")

        keys = provider.list_keys()
        assert keys == ["a.txt", "sub/b.txt"]


class TestGCSImmutableBucketProvider:
    """Tests for GCSImmutableBucketProvider using mocks."""

    def test_gcs_operations(self):
        mock_client = MagicMock()
        mock_storage.Client.return_value = mock_client
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        # Mock existence check for check-before-write
        mock_blob.exists.return_value = False

        provider = GCSImmutableBucketProvider(bucket_name="my-bucket")

        # Test put
        provider.put(b"data", key="k")
        mock_bucket.blob.assert_called_with("k")
        mock_blob.upload_from_string.assert_called_with(b"data")

        # Test put duplicate raises
        mock_blob.exists.return_value = True
        with pytest.raises(FileExistsError):
            provider.put(b"data", key="k")

        # Test get
        mock_blob.exists.return_value = True
        mock_blob.download_as_bytes.return_value = b"retrieved"
        assert provider.get("k") == b"retrieved"

        # Test get missing raises
        mock_blob.exists.return_value = False
        with pytest.raises(FileNotFoundError):
            provider.get("missing")


class TestS3ImmutableBucketProvider:
    """Tests for S3ImmutableBucketProvider using mocks."""

    def test_s3_operations(self):
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3

        # Mock head_object to simulate existence
        # First call to exists() (during put) returns False (key does not exist)
        err_response = {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}
        mock_s3.head_object.side_effect = MockClientError(err_response, "HeadObject")

        provider = S3ImmutableBucketProvider(bucket_name="my-s3-bucket")

        # Test put
        provider.put(b"s3data", key="s3k")
        mock_s3.put_object.assert_called_with(
            Bucket="my-s3-bucket",
            Key="s3k",
            Body=b"s3data",
        )

        # Test put duplicate raises
        mock_s3.head_object.side_effect = None  # means exists returns True
        with pytest.raises(FileExistsError):
            provider.put(b"s3data", key="s3k")

        # Test get
        mock_body = MagicMock()
        mock_body.read.return_value = b"s3retrieved"
        mock_s3.get_object.return_value = {"Body": mock_body}
        assert provider.get("s3k") == b"s3retrieved"

        # Test get missing raises
        mock_s3.get_object.side_effect = MockClientError(err_response, "GetObject")
        with pytest.raises(FileNotFoundError):
            provider.get("missing")


class TestGetStorageProviderFactory:
    """Tests for get_storage_provider factory."""

    @patch.dict(
        os.environ, {"PHANTOM_STORAGE_TYPE": "local", "PHANTOM_STORAGE_DIR": "/tmp/factory-test"}
    )
    def test_factory_local_env(self):
        provider = get_storage_provider()
        assert isinstance(provider, LocalImmutableBucketProvider)
        assert str(provider.base_dir) == "/tmp/factory-test"

    @patch.dict(
        os.environ,
        {"GCP_STORAGE_BUCKET": "gcs-env-bucket", "GCP_PROJECT_ID": "gcs-proj"},
        clear=True,
    )
    def test_factory_gcs_env(self):
        provider = get_storage_provider()
        assert isinstance(provider, GCSImmutableBucketProvider)
        assert provider.bucket_name == "gcs-env-bucket"

    @patch.dict(
        os.environ,
        {
            "S3_STORAGE_BUCKET": "s3-env-bucket",
            "AWS_ACCESS_KEY_ID": "key",
            "AWS_SECRET_ACCESS_KEY": "secret",
        },
        clear=True,
    )
    def test_factory_s3_env(self):
        provider = get_storage_provider()
        assert isinstance(provider, S3ImmutableBucketProvider)
        assert provider.bucket_name == "s3-env-bucket"
