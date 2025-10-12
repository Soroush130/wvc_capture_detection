# tests/test_detection_utils.py
import pytest
from unittest.mock import patch, MagicMock
from detection.detection_utils import (
    detect_objects,
    get_yolo_model,
    CLASS_NAMES,
    ANIMAL_TO_DEER_MAP
)


class TestDetectionUtils:
    """Test suite for object detection"""

    def test_class_names_contains_required_classes(self):
        """Test that all required classes are defined"""
        assert 'person' in CLASS_NAMES.values()
        assert 'car' in CLASS_NAMES.values()
        assert 'truck' in CLASS_NAMES.values()

    def test_animal_to_deer_mapping(self):
        """Test animal to deer conversion"""
        assert ANIMAL_TO_DEER_MAP['dog'] == 'deer'
        assert ANIMAL_TO_DEER_MAP['horse'] == 'deer'
        assert ANIMAL_TO_DEER_MAP['cow'] == 'deer'
        assert ANIMAL_TO_DEER_MAP['bear'] == 'deer'

    @patch('detection.detection_utils.download_from_s3')
    def test_detect_objects_download_failure(self, mock_download):
        """Test detection when download fails"""
        mock_download.return_value = None

        result = detect_objects(1, "photos/test.jpg")

        assert result is None

    @patch('detection.detection_utils.download_from_s3')
    @patch('detection.detection_utils.get_yolo_model')
    @patch('detection.detection_utils.os.remove')
    def test_detect_objects_with_car(self, mock_remove, mock_get_model, mock_download):
        """Test detection of car object"""
        # Mock download
        mock_download.return_value = "/tmp/test.jpg"

        # Mock YOLO model
        mock_model = MagicMock()
        mock_result = MagicMock()

        # Mock car detection
        mock_box = MagicMock()
        mock_box.conf = 0.85
        mock_box.cls = 2  # car
        mock_box.xyxy.squeeze().tolist.return_value = [100, 100, 200, 200]

        mock_result.boxes = [mock_box]
        mock_result.orig_img = MagicMock()

        mock_model.predict.return_value = [mock_result]
        mock_get_model.return_value = mock_model

        result = detect_objects(1, "photos/test.jpg")

        assert result is not None
        assert result['photo_id'] == 1
        assert result['has_detected_objects'] is True
        assert len(result['detected_objects']) == 1
        assert result['detected_objects'][0]['name'] == 'car'
        assert result['counts']['car_above'] == 1
        assert result['counts']['car_below'] == 0

    @patch('detection.detection_utils.download_from_s3')
    @patch('detection.detection_utils.get_yolo_model')
    @patch('detection.detection_utils.os.remove')
    def test_detect_objects_with_animal_to_deer(self, mock_remove, mock_get_model, mock_download):
        """Test animal to deer mapping"""
        mock_download.return_value = "/tmp/test.jpg"

        mock_model = MagicMock()
        mock_result = MagicMock()

        # Mock dog detection (should become deer)
        mock_box = MagicMock()
        mock_box.conf = 0.75
        mock_box.cls = 16  # dog
        mock_box.xyxy.squeeze().tolist.return_value = [50, 50, 150, 150]

        mock_result.boxes = [mock_box]
        mock_result.orig_img = MagicMock()

        mock_model.predict.return_value = [mock_result]
        mock_get_model.return_value = mock_model

        result = detect_objects(1, "photos/test.jpg")

        assert result is not None
        assert result['detected_objects'][0]['name'] == 'deer'
        assert result['detected_objects'][0]['original_name'] == 'dog'
        assert result['counts']['deer_above'] == 1

    @patch('detection.detection_utils.download_from_s3')
    @patch('detection.detection_utils.get_yolo_model')
    @patch('detection.detection_utils.os.remove')
    def test_detect_objects_low_confidence(self, mock_remove, mock_get_model, mock_download):
        """Test detection with low confidence"""
        mock_download.return_value = "/tmp/test.jpg"

        mock_model = MagicMock()
        mock_result = MagicMock()

        # Mock low confidence car
        mock_box = MagicMock()
        mock_box.conf = 0.35  # below YOLO_SYSTEM_CONFIDENCE (0.5)
        mock_box.cls = 2  # car
        mock_box.xyxy.squeeze().tolist.return_value = [100, 100, 200, 200]

        mock_result.boxes = [mock_box]
        mock_result.orig_img = MagicMock()

        mock_model.predict.return_value = [mock_result]
        mock_get_model.return_value = mock_model

        result = detect_objects(1, "photos/test.jpg")

        assert result is not None
        assert result['counts']['car_above'] == 0
        assert result['counts']['car_below'] == 1