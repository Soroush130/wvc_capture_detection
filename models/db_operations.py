# models/db_operations.py
"""
Database operations using Peewee ORM
Compatible with existing tasks.py and actual database models
"""
from datetime import datetime
from typing import List, Dict, Optional
from logger_config import get_logger
from models.models import (
    db,
    Photo,
    DetectedObject,
    Camera,
    State,
    City,
    Road
)

logger = get_logger(__name__)


# ==================== CONNECTION MANAGEMENT ====================
def ensure_connection():
    """Ensure database is connected"""
    if db.is_closed():
        try:
            db.connect()
            logger.debug("✅ Database connected")
        except Exception as e:
            logger.error(f"❌ Failed to connect to database: {e}")
            raise


def safe_close_connection():
    """Safely close database connection"""
    if not db.is_closed():
        db.close()
        logger.debug("✅ Database connection closed")


# ==================== CAMERA OPERATIONS ====================
def get_active_cameras_for_capture(limit: int = None) -> List[int]:
    """
    Get IDs of all cameras in active states for capture

    Args:
        limit: Maximum number of camera IDs to return (None = all)

    Returns:
        List of camera IDs
    """
    try:
        ensure_connection()

        query = (Camera
                 .select(Camera.id)
                 .join(City)
                 .join(State)
                 .where(State.is_active == True)
                 .order_by(Camera.id))

        if limit:
            query = query.limit(limit)

        camera_ids = [camera.id for camera in query]

        logger.info(f"📊 Found {len(camera_ids)} cameras in active states")
        return camera_ids

    except Exception as e:
        logger.error(f"❌ Error fetching active cameras: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []


def get_camera_by_id(camera_id: int) -> Optional[Camera]:
    """
    Get camera instance by ID

    Args:
        camera_id: Camera ID

    Returns:
        Camera instance or None
    """
    try:
        ensure_connection()
        return Camera.get_by_id(camera_id)
    except Camera.DoesNotExist:
        logger.error(f"❌ Camera {camera_id} not found")
        return None
    except Exception as e:
        logger.error(f"❌ Error fetching camera {camera_id}: {e}")
        return None


def get_all_cameras(limit: int = None) -> List[Dict]:
    """
    Get all cameras

    Args:
        limit: Maximum number of cameras to return (None = all)

    Returns:
        List of camera dictionaries
    """
    try:
        ensure_connection()

        query = (Camera
                 .select()
                 .order_by(Camera.id))

        if limit:
            query = query.limit(limit)

        cameras = []
        for camera in query:
            cameras.append({
                'id': camera.id,
                'name': camera.name,
                'slug': camera.slug,
                'url': camera.url,
                'latitude': camera.latitude,
                'longitude': camera.longitude,
                'road_id': camera.road_id,
                'city_id': camera.city_id,
            })

        logger.info(f"📊 Found {len(cameras)} cameras")
        return cameras

    except Exception as e:
        logger.error(f"❌ Error fetching cameras: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []


# ==================== PHOTO OPERATIONS ====================
def get_undetected_photos(limit: int = 100) -> list:
    """
    Get photos that haven't been processed for object detection yet

    Args:
        limit: Maximum number of photos to return

    Returns:
        List of photo dictionaries with id and s3_key (file field)
    """
    try:
        ensure_connection()

        photos = (Photo
                  .select(Photo.id, Photo.file)
                  .where(
            (Photo.detected_at.is_null()) &
            (Photo.file.is_null(False))
        )
                  .order_by(Photo.created_at.asc())
                  .limit(limit))

        photo_list = [
            {
                'id': photo.id,
                's3_key': photo.file  # file field as s3_key for compatibility
            }
            for photo in photos
        ]

        logger.info(f"📊 Found {len(photo_list)} undetected photos")
        return photo_list

    except Exception as e:
        logger.error(f"❌ Error fetching undetected photos: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []


def update_photo_detection(photo_id: int, counts: dict, has_detected_objects: bool = False) -> bool:
    """
    Update photo detection results in database

    Args:
        photo_id: ID of the photo
        counts: Dictionary with detection counts
            {
                'car_above': int,
                'car_below': int,
                'truck_above': int,
                'truck_below': int,
                'person_above': int,
                'person_below': int,
                'deer_above': int,
                'deer_below': int,
            }
        has_detected_objects: Whether photo has any detected objects

    Returns:
        True if update successful, False otherwise
    """
    try:
        ensure_connection()

        # Update photo using Peewee
        query = (Photo
                 .update(
            car_count_above_system_confidence=counts['car_above'],
            car_count_below_system_confidence=counts['car_below'],
            truck_count_above_system_confidence=counts['truck_above'],
            truck_count_below_system_confidence=counts['truck_below'],
            person_count_above_system_confidence=counts['person_above'],
            person_count_below_system_confidence=counts['person_below'],
            deer_count_above_system_confidence=counts['deer_above'],
            deer_count_below_system_confidence=counts['deer_below'],
            has_detected_objects=has_detected_objects,
            detected_at=datetime.now()
        )
                 .where(Photo.id == photo_id))

        rows_updated = query.execute()

        if rows_updated > 0:
            logger.info(
                f"✅ Updated photo {photo_id} detection results "
                f"(has_objects: {has_detected_objects})"
            )
            return True
        else:
            logger.warning(f"⚠️ Photo {photo_id} not found for update")
            return False

    except Exception as e:
        logger.error(f"❌ Error updating photo {photo_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def save_detected_objects(photo_id: int, detected_objects: list) -> bool:
    """
    Save detected objects to database

    Args:
        photo_id: ID of the photo
        detected_objects: List of detected object dictionaries
            [
                {
                    'name': str,  # car, truck, person, deer
                    'original_name': str,  # (optional - for mapping)
                    'confidence': float,
                    'x': float,
                    'y': float,
                    'width': float,
                    'height': float,
                    's3_key': str or None  # path to cropped image
                },
                ...
            ]

    Returns:
        True if save successful, False otherwise
    """
    if not detected_objects:
        logger.debug(f"ℹ️ No objects to save for photo {photo_id}")
        return True

    try:
        ensure_connection()

        # Get photo to inherit timezone info
        try:
            photo = Photo.get_by_id(photo_id)
        except Photo.DoesNotExist:
            logger.error(f"❌ Photo {photo_id} not found")
            return False

        # Prepare objects for batch insert
        objects_to_create = []
        for obj in detected_objects:
            # Convert s3_key to image field
            image_path = obj.get('s3_key') or 'objects/not-saved.jpg'

            objects_to_create.append({
                'photo': photo,
                'name': obj['name'],  # car, truck, person, deer
                'image': image_path,  # s3_key converted to image
                'conf': obj['confidence'],  # confidence converted to conf
                'x': obj['x'],
                'y': obj['y'],
                'width': obj['width'],
                'height': obj['height'],
                'timezone': photo.timezone,
                'captured_at': photo.captured_at,
                'created_at': datetime.now()
            })

        # Batch insert using atomic transaction
        with db.atomic():
            # Insert in batches of 100 for better performance
            batch_size = 100
            for i in range(0, len(objects_to_create), batch_size):
                batch = objects_to_create[i:i + batch_size]
                DetectedObject.insert_many(batch).execute()

        logger.info(f"✅ Saved {len(detected_objects)} objects for photo {photo_id}")
        return True

    except Exception as e:
        logger.error(f"❌ Error saving objects for photo {photo_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def create_photo(camera_id: int, file_path: str, captured_at: datetime = None) -> Optional[int]:
    """
    Create a new photo record

    Args:
        camera_id: Camera ID
        file_path: Path to photo file (S3 key)
        captured_at: When photo was captured (default: now)

    Returns:
        Photo ID or None if failed
    """
    try:
        ensure_connection()

        # Get camera to inherit location info
        camera = Camera.get_by_id(camera_id)

        photo = Photo.create(
            camera=camera,
            file=file_path,
            state=camera.city.state,
            city=camera.city,
            road=camera.road,
            timezone=camera.city.timezone,
            captured_at=captured_at or datetime.now(),
            created_at=datetime.now()
        )

        logger.info(f"✅ Created photo {photo.id} for camera {camera_id}")
        return photo.id

    except Camera.DoesNotExist:
        logger.error(f"❌ Camera {camera_id} not found")
        return None
    except Exception as e:
        logger.error(f"❌ Error creating photo: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


# ==================== STATISTICS ====================
def get_photo_stats(camera_id: int = None, days: int = 7) -> Dict:
    """
    Get photo statistics

    Args:
        camera_id: Filter by camera ID (None = all cameras)
        days: Number of days to look back

    Returns:
        Dictionary with statistics
    """
    try:
        ensure_connection()

        from datetime import timedelta
        since = datetime.now() - timedelta(days=days)

        query = Photo.select()

        if camera_id:
            query = query.where(Photo.camera == camera_id)

        query = query.where(Photo.created_at >= since)

        total_photos = query.count()
        detected_photos = query.where(Photo.detected_at.is_null(False)).count()
        photos_with_objects = query.where(Photo.has_detected_objects == True).count()

        return {
            'total_photos': total_photos,
            'detected_photos': detected_photos,
            'undetected_photos': total_photos - detected_photos,
            'photos_with_objects': photos_with_objects,
            'photos_without_objects': detected_photos - photos_with_objects,
        }

    except Exception as e:
        logger.error(f"❌ Error getting photo stats: {e}")
        return {}


def get_object_stats(camera_id: int = None, days: int = 7) -> Dict:
    """
    Get object detection statistics

    Args:
        camera_id: Filter by camera ID (None = all cameras)
        days: Number of days to look back

    Returns:
        Dictionary with statistics
    """
    try:
        ensure_connection()

        from datetime import timedelta
        since = datetime.now() - timedelta(days=days)

        query = DetectedObject.select()

        if camera_id:
            query = query.join(Photo).where(Photo.camera == camera_id)

        query = query.where(DetectedObject.created_at >= since)

        # Count by object type
        stats = {}
        for obj_name in [
            DetectedObject.NAME_CAR,
            DetectedObject.NAME_TRUCK,
            DetectedObject.NAME_PERSON,
            DetectedObject.NAME_DEER
        ]:
            count = query.where(DetectedObject.name == obj_name).count()
            stats[f'{obj_name}_count'] = count

        stats['total_objects'] = query.count()

        return stats

    except Exception as e:
        logger.error(f"❌ Error getting object stats: {e}")
        return {}


def get_detected_objects_by_photo(photo_id: int) -> List[Dict]:
    """
    Get all detected objects for a photo

    Args:
        photo_id: Photo ID

    Returns:
        List of detected object dictionaries
    """
    try:
        ensure_connection()

        objects = (DetectedObject
                   .select()
                   .where(DetectedObject.photo == photo_id)
                   .order_by(DetectedObject.conf.desc()))

        object_list = []
        for obj in objects:
            object_list.append({
                'id': obj.id,
                'name': obj.name,
                'confidence': float(obj.conf),
                'x': float(obj.x),
                'y': float(obj.y),
                'width': float(obj.width),
                'height': float(obj.height),
                'image': obj.image,
            })

        return object_list

    except Exception as e:
        logger.error(f"❌ Error fetching objects for photo {photo_id}: {e}")
        return []


# ==================== UTILITY FUNCTIONS ====================
def test_connection() -> bool:
    """
    Test database connection

    Returns:
        True if connection successful, False otherwise
    """
    try:
        ensure_connection()

        # Simple query to test connection
        Photo.select().limit(1).execute()

        logger.info("✅ Database connection test successful")
        return True

    except Exception as e:
        logger.error(f"❌ Database connection test failed: {e}")
        return False


def get_database_info() -> Dict:
    """
    Get database information

    Returns:
        Dictionary with database info
    """
    try:
        ensure_connection()

        return {
            'database': db.database,
            'host': db.host,
            'port': db.port,
            'user': db.user,
            'is_connected': not db.is_closed(),
        }

    except Exception as e:
        logger.error(f"❌ Error getting database info: {e}")
        return {}