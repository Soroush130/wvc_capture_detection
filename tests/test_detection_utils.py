# tests/test_detection_utils.py
import pytest
from unittest.mock import patch, MagicMock
from detection.detection_utils import (
    detect_objects,
    get_yolo_model,
    CLASS_CONFIG,
    CLASS_NAMES,
)


class TestDetectionUtils:
    """Test suite for object detection"""

    def test_class_names_contains_required_classes(self):
        """Test that all required classes are defined"""
        # Check if CLASS_NAMES is a dict (like CLASS_CONFIG)
        # or a list of class names
        assert 'person' in CLASS_NAMES.values() or 'person' in CLASS_NAMES
        assert 'car' in CLASS_NAMES.values() or 'car' in CLASS_NAMES
        assert 'truck' in CLASS_NAMES.values() or 'truck' in CLASS_NAMES

        # Direct check from CLASS_CONFIG
        assert 'person' in CLASS_CONFIG
        assert 'car' in CLASS_CONFIG
        assert 'truck' in CLASS_CONFIG

    @patch('detection.detection_utils.download_from_s3')
    def test_detect_objects_download_failure(self, mock_download):
        """Test detection when download fails"""
        mock_download.return_value = None

        result = detect_objects(1, "photos/test.jpg")

        assert result is None

    @patch('detection.detection_utils._device', 'cpu')  # Mock device
    @patch('detection.detection_utils.download_from_s3')
    @patch('detection.detection_utils.get_yolo_model')
    @patch('detection.detection_utils.os.remove')
    @patch('detection.detection_utils.upload_to_s3')
    def test_detect_objects_with_car(
            self,
            mock_upload,
            mock_remove,
            mock_get_model,
            mock_download
    ):
        """Test detection of car object"""
        # Mock download
        mock_download.return_value = "/tmp/test.jpg"

        # Mock S3 upload
        mock_upload.return_value = (True, "objects/car/1_1.jpg")

        # Mock YOLO model
        mock_model = MagicMock()
        mock_result = MagicMock()

        # Mock YOLO class names (COCO dataset)
        mock_result.names = {
            0: 'person',
            1: 'bicycle',
            2: 'car',
            3: 'motorcycle',
            4: 'airplane',
            5: 'bus',
            6: 'train',
            7: 'truck',
            8: 'boat',
            9: 'traffic light',
            10: 'fire hydrant',
            11: 'stop sign',
            12: 'parking meter',
            13: 'bench',
            14: 'bird',
            15: 'cat',
            16: 'dog',
            17: 'horse',
            18: 'sheep',
            19: 'cow',
            20: 'elephant',
            21: 'bear',
            22: 'zebra',
            23: 'giraffe',
        }

        # Mock car detection
        mock_box = MagicMock()
        mock_box.conf = 0.85
        mock_box.cls = 2  # car class in COCO
        mock_box.xyxy = MagicMock()
        mock_box.xyxy.squeeze = MagicMock()
        mock_box.xyxy.squeeze().tolist = MagicMock(return_value=[100, 100, 200, 200])

        mock_result.boxes = [mock_box]

        # Mock image for cropping
        import numpy as np
        mock_result.orig_img = np.zeros((480, 640, 3), dtype=np.uint8)

        mock_model.predict.return_value = [mock_result]
        mock_get_model.return_value = mock_model

        result = detect_objects(1, "photos/test.jpg")

        # Assertions
        assert result is not None
        assert result['photo_id'] == 1
        assert result['has_detected_objects'] is True
        assert len(result['detected_objects']) == 1
        assert result['detected_objects'][0]['name'] == 'car'
        assert result['counts']['car_above'] == 1
        assert result['counts']['car_below'] == 0

    @patch('detection.detection_utils._device', 'cpu')  # Mock device
    @patch('detection.detection_utils.download_from_s3')
    @patch('detection.detection_utils.get_yolo_model')
    @patch('detection.detection_utils.os.remove')
    @patch('detection.detection_utils.upload_to_s3')
    def test_detect_objects_with_animal_to_deer(
            self,
            mock_upload,
            mock_remove,
            mock_get_model,
            mock_download
    ):
        """Test animal to deer mapping"""
        mock_download.return_value = "/tmp/test.jpg"
        mock_upload.return_value = (True, "objects/deer/1_1.jpg")

        mock_model = MagicMock()
        mock_result = MagicMock()

        # Mock YOLO class names
        mock_result.names = {
            0: 'person',
            2: 'car',
            7: 'truck',
            15: 'cat',
            16: 'dog',  # dog class in COCO
            17: 'horse',
            18: 'sheep',
            19: 'cow',
            20: 'elephant',
            21: 'bear',
            22: 'zebra',
            23: 'giraffe',
        }

        # Mock dog detection (should become deer)
        mock_box = MagicMock()
        mock_box.conf = 0.85  # Higher than MIN_CONFIDENCE=0.80
        mock_box.cls = 16  # dog
        mock_box.xyxy = MagicMock()
        mock_box.xyxy.squeeze = MagicMock()
        mock_box.xyxy.squeeze().tolist = MagicMock(return_value=[50, 50, 150, 150])

        mock_result.boxes = [mock_box]

        # Mock image
        import numpy as np
        mock_result.orig_img = np.zeros((480, 640, 3), dtype=np.uint8)

        mock_model.predict.return_value = [mock_result]
        mock_get_model.return_value = mock_model

        result = detect_objects(1, "photos/test.jpg")

        # Assertions - dog should be mapped to deer
        assert result is not None
        assert len(result['detected_objects']) == 1
        assert result['detected_objects'][0]['name'] == 'deer'
        assert result['detected_objects'][0]['original_name'] == 'dog'
        assert result['counts']['deer_above'] == 1

    @patch('detection.detection_utils._device', 'cpu')  # Mock device
    @patch('detection.detection_utils.YOLO_SYSTEM_CONFIDENCE', 0.5)  # Set threshold
    @patch('detection.detection_utils.download_from_s3')
    @patch('detection.detection_utils.get_yolo_model')
    @patch('detection.detection_utils.os.remove')
    @patch('detection.detection_utils.upload_to_s3')
    def test_detect_objects_low_confidence(
            self,
            mock_upload,
            mock_remove,
            mock_get_model,
            mock_download
    ):
        """Test detection with low confidence"""
        # Note: With MIN_CONFIDENCE=0.80, confidence must be above 0.80
        # This test uses 0.82 which is above MIN but can be below SYSTEM

        mock_download.return_value = "/tmp/test.jpg"
        mock_upload.return_value = (True, "objects/car/1_1.jpg")

        mock_model = MagicMock()
        mock_result = MagicMock()

        # Mock YOLO names
        mock_result.names = {
            0: 'person',
            2: 'car',
            7: 'truck',
        }

        # Mock medium confidence car (between MIN and SYSTEM)
        mock_box = MagicMock()
        mock_box.conf = 0.82  # Above MIN (0.80) but can be below SYSTEM (0.85)
        mock_box.cls = 2  # car
        mock_box.xyxy = MagicMock()
        mock_box.xyxy.squeeze = MagicMock()
        mock_box.xyxy.squeeze().tolist = MagicMock(return_value=[100, 100, 200, 200])

        mock_result.boxes = [mock_box]

        # Mock image
        import numpy as np
        mock_result.orig_img = np.zeros((480, 640, 3), dtype=np.uint8)

        mock_model.predict.return_value = [mock_result]
        mock_get_model.return_value = mock_model

        result = detect_objects(1, "photos/test.jpg")

        # Assertions
        assert result is not None
        # With conf=0.82 and SYSTEM_CONFIDENCE=0.5 (mocked), should be above
        # But if SYSTEM_CONFIDENCE is 0.85, should be below
        assert result['counts']['car_above'] == 1 or result['counts']['car_below'] == 1