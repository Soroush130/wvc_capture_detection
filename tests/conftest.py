# tests/conftest.py
import pytest
import os
from unittest.mock import MagicMock, patch, Mock
from dotenv import load_dotenv
from datetime import datetime

# Load environment
load_dotenv()


@pytest.fixture
def mock_db():
    """Mock database connection"""
    with patch('models.models.db') as mock:
        mock.is_closed.return_value = False
        mock.connect.return_value = None
        mock.close.return_value = None
        yield mock


@pytest.fixture
def mock_redis():
    """Mock Redis connection"""
    with patch('redis.Redis') as mock:
        redis_instance = MagicMock()
        redis_instance.keys.return_value = []
        redis_instance.get.return_value = None
        redis_instance.set.return_value = True
        redis_instance.delete.return_value = True
        mock.return_value = redis_instance
        yield redis_instance


@pytest.fixture
def mock_s3_client():
    """Mock S3 client"""
    with patch('boto3.client') as mock:
        s3_instance = MagicMock()
        s3_instance.put_object.return_value = {}
        s3_instance.delete_object.return_value = {}
        s3_instance.download_file.return_value = None
        s3_instance.generate_presigned_url.return_value = "https://example.com/presigned"
        mock.return_value = s3_instance
        yield s3_instance


@pytest.fixture
def mock_yolo_model():
    """Mock YOLO model"""
    with patch('ultralytics.YOLO') as mock:
        model_instance = MagicMock()

        # Mock box
        mock_box = MagicMock()
        mock_box.conf = 0.85
        mock_box.cls = 2  # car
        mock_box.xyxy.squeeze().tolist.return_value = [100, 100, 200, 200]

        # Mock result
        mock_result = MagicMock()
        mock_result.boxes = [mock_box]
        mock_result.orig_img = MagicMock()

        model_instance.predict.return_value = [mock_result]
        model_instance.to.return_value = model_instance

        mock.return_value = model_instance
        yield model_instance


@pytest.fixture
def sample_camera():
    """Sample camera object"""
    camera = MagicMock()
    camera.id = 1
    camera.name = "Test Camera"
    camera.url = "http://example.com/image.jpg"
    camera.state.name = "maryland"
    camera.city.name = "baltimore"
    camera.road = "I-95"
    return camera


@pytest.fixture
def sample_photo():
    """Sample photo object"""
    photo = MagicMock()
    photo.id = 1
    photo.file = "photos/maryland/baltimore/test.jpg"
    photo.camera_id = 1
    photo.captured_at = datetime.now()
    photo.detected_at = None
    photo.has_detected_objects = False
    return photo


@pytest.fixture
def mock_requests_get():
    """Mock requests.get for capturing images"""
    with patch('requests.get') as mock:
        response = MagicMock()
        response.status_code = 200
        response.content = b"fake image data"
        response.raise_for_status.return_value = None
        mock.return_value = response
        yield mock