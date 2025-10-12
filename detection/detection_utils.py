# detection/detection_utils.py
import os
from typing import List, Dict, Optional
from ultralytics import YOLO
from ultralytics.engine.results import Results
from logger_config import get_logger
from aws_s3.s3_download import download_from_s3
from aws_s3.s3_utils import upload_to_s3

logger = get_logger(__name__)

YOLO_MODEL_PATH = os.getenv('YOLO_MODEL_PATH', 'yolo_models/yolov8n.pt')
YOLO_DEVICE = os.getenv('YOLO_DEVICE', 'cpu')
YOLO_MIN_CONFIDENCE = float(os.getenv('YOLO_MIN_CONFIDENCE', 0.25))
YOLO_SYSTEM_CONFIDENCE = float(os.getenv('YOLO_SYSTEM_CONFIDENCE', 0.5))
SAVE_DETECTED_OBJECTS = os.getenv('SAVE_DETECTED_OBJECTS', 'True').lower() == 'true'

# ==================== CLASS MAPPING CONFIGURATION ====================
CLASS_CONFIG = {
    # ==================== VEHICLES ====================
    'car': {
        'map_to': 'car',
        'min_confidence': 0.25,
        'save_image': True,
    },
    'truck': {
        'map_to': 'truck',
        'min_confidence': 0.25,
        'save_image': True,
    },
    'bus': {
        'map_to': 'truck',  # Bus → Truck
        'min_confidence': 0.25,
        'save_image': True,
    },

    # ==================== PERSON ====================
    'person': {
        'map_to': 'person',
        'min_confidence': 0.25,
        'save_image': True,
    },

    # ==================== ANIMALS → DEER ====================
    'dog': {
        'map_to': 'deer',
        'min_confidence': 0.30,
        'save_image': True,
    },
    'cat': {
        'map_to': 'deer',
        'min_confidence': 0.35,
        'save_image': True,
    },
    'horse': {
        'map_to': 'deer',
        'min_confidence': 0.30,
        'save_image': True,
    },
    'sheep': {
        'map_to': 'deer',
        'min_confidence': 0.30,
        'save_image': True,
    },
    'cow': {
        'map_to': 'deer',
        'min_confidence': 0.30,
        'save_image': True,
    },
    'elephant': {
        'map_to': 'deer',
        'min_confidence': 0.30,
        'save_image': True,
    },
    'bear': {
        'map_to': 'deer',
        'min_confidence': 0.35,
        'save_image': True,
    },
    'zebra': {
        'map_to': 'deer',
        'min_confidence': 0.30,
        'save_image': True,
    },
    'giraffe': {
        'map_to': 'deer',
        'min_confidence': 0.30,
        'save_image': True,
    },
}

# Global model (load once)
_model = None


def get_yolo_model():
    """Get cached YOLO model to avoid reloading"""
    global _model
    if _model is None:
        logger.info(f"🔄 Loading YOLO model: {YOLO_MODEL_PATH}")
        _model = YOLO(YOLO_MODEL_PATH)
        _model.to(YOLO_DEVICE)
        logger.info(f"✅ Model loaded on {YOLO_DEVICE}")
    return _model


def detect_objects(photo_id: int, s3_key: str) -> Optional[Dict]:
    """
    Detect objects in photo

    Returns:
        {
            'photo_id': int,
            'counts': {
                'car_above': int,
                'car_below': int,
                'truck_above': int,
                'truck_below': int,
                'person_above': int,
                'person_below': int,
                'deer_above': int,
                'deer_below': int,
            },
            'detected_objects': [
                {
                    'name': 'car'|'truck'|'person'|'deer',
                    'original_name': 'dog'|'horse'|...,
                    'confidence': float,
                    'x': float,
                    'y': float,
                    'width': float,
                    'height': float,
                    's3_key': str|None,
                    'is_above_system_confidence': bool
                },
                ...
            ],
            'has_detected_objects': bool,
            'total_objects_detected': int,
            'total_raw_detections': int,
            'classes_detected': ['car', 'person', ...]
        }
    """
    local_path = None
    try:
        # Download from S3
        local_path = download_from_s3(s3_key)
        if not local_path:
            logger.error(f"❌ Failed to download photo {photo_id} from S3")
            return None

        # Get model
        model = get_yolo_model()

        # Detection with low threshold to catch everything
        logger.info(f"🔍 Detecting objects in photo {photo_id}")
        results: List[Results] = model.predict(
            local_path,
            device=YOLO_DEVICE,
            conf=0.20,  # Low threshold - we'll filter per-class later
            verbose=False
        )

        if not results:
            logger.warning(f"⚠️ No results from YOLO for photo {photo_id}")
            return None

        result = results[0]

        # Initialize counts
        counts = {
            'car_above': 0,
            'car_below': 0,
            'truck_above': 0,
            'truck_below': 0,
            'person_above': 0,
            'person_below': 0,
            'deer_above': 0,
            'deer_below': 0,
        }

        detected_objects = []
        classes_detected = set()
        total_raw_detections = len(result.boxes)

        logger.debug(f"====>>> Raw detections for photo {photo_id}: {total_raw_detections}")

        # Process each detection
        for i, box in enumerate(result.boxes, 1):
            confidence = float(box.conf)
            class_id = int(box.cls)

            # Get original class name from YOLO
            original_class_name = result.names[class_id]

            # Check if this class is in our config
            if original_class_name not in CLASS_CONFIG:
                logger.debug(f"⏭️ Skipping {original_class_name} - not in CLASS_CONFIG")
                continue

            class_config = CLASS_CONFIG[original_class_name]

            # Check per-class confidence threshold
            min_confidence = class_config.get('min_confidence', YOLO_MIN_CONFIDENCE)
            if confidence < min_confidence:
                logger.debug(f"⏭️ Skipping {original_class_name} - confidence {confidence:.2f} < {min_confidence}")
                continue

            # Map to final class (e.g., dog → deer)
            mapped_class_name = class_config.get('map_to', original_class_name)

            logger.info(f"✅ Detected: {original_class_name} → {mapped_class_name} (conf: {confidence:.2f})")

            classes_detected.add(mapped_class_name)

            # Get bounding box
            x1, y1, x2, y2 = box.xyxy.squeeze().tolist()
            width = x2 - x1
            height = y2 - y1

            # Update counts based on system confidence
            if confidence >= YOLO_SYSTEM_CONFIDENCE:
                counts[f'{mapped_class_name}_above'] += 1
                is_above = True
            else:
                counts[f'{mapped_class_name}_below'] += 1
                is_above = False

            # Save cropped object image to S3
            object_s3_key = None
            should_save_image = class_config.get('save_image', SAVE_DETECTED_OBJECTS)

            if should_save_image:
                try:
                    # Crop image
                    crop_img = result.orig_img[int(y1):int(y2), int(x1):int(x2)]

                    # Encode to JPEG
                    import cv2
                    _, buffer = cv2.imencode('.jpg', crop_img)

                    # Upload to S3
                    object_s3_key = f"objects/{mapped_class_name}/{photo_id}_{i}.jpg"
                    success, _ = upload_to_s3(
                        file_data=buffer.tobytes(),
                        s3_key=object_s3_key,
                        content_type='image/jpeg'
                    )

                    if not success:
                        object_s3_key = None

                except Exception as e:
                    logger.warning(f"⚠️ Failed to save object crop: {e}")
                    object_s3_key = None

            # Add to detected objects list
            detected_objects.append({
                'name': mapped_class_name,  # Final class: car, truck, person, deer
                'original_name': original_class_name,  # Original YOLO class: dog, horse, etc.
                'confidence': confidence,
                'x': x1,
                'y': y1,
                'width': width,
                'height': height,
                's3_key': object_s3_key,
                'is_above_system_confidence': is_above
            })

        # Clean up temp file
        if os.path.exists(local_path):
            os.remove(local_path)

        total_objects = len(detected_objects)
        has_detected_objects = total_objects > 0

        # Log summary
        if total_objects > 0:
            summary = []
            for key in ['car', 'truck', 'person', 'deer']:
                total = counts[f'{key}_above'] + counts[f'{key}_below']
                if total > 0:
                    summary.append(f"{key}={total}")
            logger.info(
                f"✅ Photo {photo_id}: {total_objects} objects detected "
                f"({', '.join(summary)}) | Raw: {total_raw_detections} | "
                f"Classes: {sorted(classes_detected)}"
            )
        else:
            logger.info(
                f"ℹ️ Photo {photo_id}: No objects detected "
                f"(after filtering {total_raw_detections} raw detections)"
            )

        return {
            'photo_id': photo_id,
            'counts': counts,
            'detected_objects': detected_objects,
            'has_detected_objects': has_detected_objects,
            'total_objects_detected': total_objects,
            'total_raw_detections': total_raw_detections,
            'classes_detected': sorted(list(classes_detected)),
        }

    except Exception as e:
        logger.error(f"❌ Detection error for photo {photo_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

    finally:
        if local_path and os.path.exists(local_path):
            try:
                os.remove(local_path)
            except Exception as e:
                logger.warning(f"⚠️ Failed to remove temp file: {e}")