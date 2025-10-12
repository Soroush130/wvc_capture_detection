# tests/test_s3_utils.py
import pytest
from unittest.mock import patch, MagicMock
from aws_s3.s3_utils import upload_to_s3, delete_from_s3, get_s3_client, _with_allowed_prefix  # ✅ اصلاح شد


class TestS3Utils:
    """Test suite for S3 utilities"""

    def test_with_allowed_prefix_adds_prefix(self):
        """Test that prefix is added to key without prefix"""
        result = _with_allowed_prefix("photos/test.jpg")
        assert result == "uploads/photos/test.jpg"

    def test_with_allowed_prefix_no_duplicate(self):
        """Test that prefix is not duplicated if already present"""
        result = _with_allowed_prefix("uploads/photos/test.jpg")
        assert result == "uploads/photos/test.jpg"

    def test_with_allowed_prefix_removes_leading_slash(self):
        """Test that leading slash is removed"""
        result = _with_allowed_prefix("/photos/test.jpg")
        assert result == "uploads/photos/test.jpg"

    @patch('aws_s3.s3_utils.boto3.client')  # ✅ اصلاح شد
    def test_get_s3_client_success(self, mock_boto_client):
        """Test S3 client creation"""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        client = get_s3_client()

        assert client is not None
        mock_boto_client.assert_called_once()

    @patch('aws_s3.s3_utils.boto3.client')  # ✅ اصلاح شد
    def test_upload_to_s3_success(self, mock_boto_client):
        """Test successful file upload to S3"""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        file_data = b"test image data"
        s3_key = "photos/test.jpg"

        success, url = upload_to_s3(file_data, s3_key)

        assert success is True
        assert url.startswith("https://")
        mock_s3.put_object.assert_called_once()

    @patch('aws_s3.s3_utils.boto3.client')  # ✅ اصلاح شد
    def test_upload_to_s3_with_content_type(self, mock_boto_client):
        """Test upload with custom content type"""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        file_data = b"test data"
        s3_key = "photos/test.jpg"

        success, url = upload_to_s3(file_data, s3_key, content_type="image/png")

        assert success is True
        call_kwargs = mock_s3.put_object.call_args[1]
        assert call_kwargs['ContentType'] == "image/png"

    @patch('aws_s3.s3_utils.boto3.client')  # ✅ اصلاح شد
    def test_upload_to_s3_failure(self, mock_boto_client):
        """Test upload failure handling"""
        mock_s3 = MagicMock()
        mock_s3.put_object.side_effect = Exception("Upload failed")
        mock_boto_client.return_value = mock_s3

        file_data = b"test data"
        s3_key = "photos/test.jpg"

        success, url = upload_to_s3(file_data, s3_key)

        assert success is False
        assert url == ""

    @patch('aws_s3.s3_utils.boto3.client')  # ✅ اصلاح شد
    def test_delete_from_s3_success(self, mock_boto_client):
        """Test successful file deletion from S3"""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        s3_key = "photos/test.jpg"

        result = delete_from_s3(s3_key)

        assert result is True
        mock_s3.delete_object.assert_called_once()

    @patch('aws_s3.s3_utils.boto3.client')  # ✅ اصلاح شد
    def test_delete_from_s3_failure(self, mock_boto_client):
        """Test deletion failure handling"""
        mock_s3 = MagicMock()
        mock_s3.delete_object.side_effect = Exception("Delete failed")
        mock_boto_client.return_value = mock_s3

        s3_key = "photos/test.jpg"

        result = delete_from_s3(s3_key)

        assert result is False