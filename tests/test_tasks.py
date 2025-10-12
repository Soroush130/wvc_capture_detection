# tests/test_tasks.py
import pytest
from unittest.mock import patch, MagicMock
from tasks import schedule_camera_captures, schedule_photo_detection


class TestTasks:
    """Test suite for Celery tasks"""

    @patch('tasks.db')
    @patch('tasks.Camera')
    @patch('tasks.chord')
    def test_schedule_camera_captures(self, mock_chord, mock_camera, mock_db):
        """Test camera capture scheduling"""
        # Mock database
        mock_db.is_closed.return_value = False

        # Mock cameras
        camera1 = MagicMock()
        camera1.id = 1
        camera2 = MagicMock()
        camera2.id = 2

        mock_camera.select.return_value.join.return_value.join.return_value.where.return_value = [
            camera1, camera2
        ]

        result = schedule_camera_captures()

        assert result['scheduled'] == 2
        # ✅ حذف assertion برای timestamp (چون تابع واقعی timestamp برنمی‌گرداند)

    @patch('tasks.redis.Redis')
    @patch('tasks.db')
    @patch('tasks.Photo')
    @patch('tasks.group')
    def test_schedule_photo_detection(self, mock_group, mock_photo, mock_db, mock_redis):
        """Test photo detection scheduling"""
        # Mock Redis
        redis_instance = MagicMock()
        redis_instance.keys.return_value = [
            b'photos:maryland:baltimore:test1.jpg',
            b'photos:maryland:baltimore:test2.jpg'
        ]
        redis_instance.get.return_value = b'https://s3.amazonaws.com/image.jpg'
        mock_redis.return_value = redis_instance

        # Mock database
        mock_db.is_closed.return_value = False

        # Mock photos
        photo1 = MagicMock()
        photo1.id = 1
        photo1.detected_at = None

        photo2 = MagicMock()
        photo2.id = 2
        photo2.detected_at = None

        mock_photo.select.return_value.where.return_value.first.side_effect = [photo1, photo2]

        result = schedule_photo_detection()

        assert 'detected' in result