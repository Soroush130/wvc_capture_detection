from datetime import datetime
import pytz
from models.models import Camera, City, State
from logger_config import get_logger

logger = get_logger(__name__)


def time_now_in_timezone(tz_name: str = "UTC") -> datetime:
    try:
        tz = pytz.timezone(tz_name)
        return datetime.now(tz)
    except Exception as e:
        logger.warning(f"⚠️ Invalid timezone {tz_name}, using UTC. Error: {e}")
        return datetime.now(pytz.UTC)

def time_now_in_timezone(tz_name: str = "UTC") -> datetime:
    try:
        tz = pytz.timezone(tz_name)
        return datetime.now(tz)
    except Exception as e:
        logger.warning(f"Invalid timezone {tz_name}, using UTC. Error: {e}")
        return datetime.now(pytz.UTC)


def load_cameras_data():
    try:
        cameras = (Camera
                   .select()
                   .join(City)
                   .join(State)
                   .where(State.is_active == True))

        camera_list = list(cameras)

        total_cameras = Camera.select().count()

        logger.info(
            f"Loaded {len(camera_list)} cameras from {Camera.select().join(City).join(State).where(State.is_active == True).select(State.name).distinct().count()} active states")
        logger.info(f"Total cameras in database: {total_cameras}")
        logger.info(f"Filtered cameras: {len(camera_list)}")

        if camera_list:
            for camera in camera_list[:10]:  # نمایش 10 تای اول
                logger.info(f"  - ID: {camera.id}, Name: {camera.name}, URL: {camera.url}")

            if len(camera_list) > 10:
                logger.info(f"  ... and {len(camera_list) - 10} more cameras")
        else:
            logger.warning("No cameras found with active states!")

        return camera_list

    except Exception as e:
        logger.error(f"Error loading cameras: {e}")
        import traceback
        traceback.print_exc()
        return []
