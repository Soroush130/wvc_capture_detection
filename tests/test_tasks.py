# tests/test_tasks.py
import pytest
from unittest.mock import patch, MagicMock


class TestTasks:
    """Test suite for Celery tasks"""

    @patch('tasks.chord')  # Mock chord to avoid Redis connection
    @patch('tasks.get_active_cameras_for_capture')
    @patch('tasks.capture_single_camera')
    def test_schedule_camera_captures(
            self,
            mock_capture,
            mock_get_cameras,
            mock_chord
    ):
        """Test scheduling camera captures"""
        from tasks import schedule_camera_captures

        # Mock get_active_cameras_for_capture to return list of camera IDs
        mock_get_cameras.return_value = [1, 2, 3]

        # Mock chord instance
        mock_chord_instance = MagicMock()
        mock_chord.return_value = mock_chord_instance

        # Run the schedule function
        result = schedule_camera_captures()

        # Assertions
        mock_get_cameras.assert_called_once()
        mock_chord.assert_called_once()
        mock_chord_instance.apply_async.assert_called_once()

        # Check result
        assert result['scheduled'] == 3
        assert 'timestamp' in result

    @patch('tasks.get_undetected_photos')
    @patch('tasks.detect_single_photo')
    def test_schedule_photo_detection(self, mock_detect, mock_get_photos):
        """Test scheduling photo detection"""
        from tasks import schedule_photo_detection

        # Mock get_undetected_photos to return list of photos
        mock_get_photos.return_value = [
            {'id': 1, 's3_key': 'photos/test1.jpg'},
            {'id': 2, 's3_key': 'photos/test2.jpg'},
            {'id': 3, 's3_key': 'photos/test3.jpg'},
        ]

        # Mock the detect task's apply_async method
        mock_detect.apply_async = MagicMock()

        # Run the schedule function
        result = schedule_photo_detection()

        # Assertions
        mock_get_photos.assert_called_once_with(limit=100)
        assert mock_detect.apply_async.call_count == 3
        assert result['status'] == 'success'
        assert result['photos_scheduled'] == 3
        assert result['total_found'] == 3