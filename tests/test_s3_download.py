# tests/test_s3_download.py
import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock
from aws_s3.s3_download import download_from_s3, get_s3_url, _with_allowed_prefix


class TestS3Download:
    """Test suite for S3 download utilities"""

    def test_with_allowed_prefix_adds_uploads(self):
        """Test prefix addition"""
        result = _with_allowed_prefix("photos/test.jpg")
        assert result == "uploads/photos/test.jpg"

    @patch('aws_s3.s3_download.boto3.client')
    @patch('aws_s3.s3_download.tempfile.NamedTemporaryFile')
    def test_download_from_s3_success(self, mock_tempfile, mock_boto_client):
        """Test successful download from S3"""
        # Mock temp file
        mock_file = MagicMock()
        mock_file.name = "/tmp/test.jpg"
        mock_tempfile.return_value = mock_file

        # Mock S3 client
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        s3_key = "photos/test.jpg"

        result = download_from_s3(s3_key)

        assert result == "/tmp/test.jpg"
        mock_s3.download_file.assert_called_once()

    @patch('aws_s3.s3_download.boto3.client')
    def test_download_from_s3_failure(self, mock_boto_client):
        """Test download failure"""
        mock_s3 = MagicMock()
        mock_s3.download_file.side_effect = Exception("Download failed")
        mock_boto_client.return_value = mock_s3

        s3_key = "photos/test.jpg"

        result = download_from_s3(s3_key)

        assert result is None

    def test_get_s3_url_correct_format(self):
        """Test S3 URL generation"""
        s3_key = "photos/test.jpg"

        url = get_s3_url(s3_key)

        assert "wvcbucket" in url
        assert "s3" in url
        assert "us-east-1" in url
        assert "uploads/photos/test.jpg" in url