from typing import Tuple, Union, Optional
import os
import cv2
import redis
import requests

from utility import time_now_in_timezone
from settings import MONITOR_CAPTURE_TIMEOUT
from models.models import Camera, Photo
from logger_config import get_logger
from aws_s3.s3_utils import upload_to_s3

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

logger = get_logger(__name__)


def capture(camera: Camera) -> Optional[dict]:
    r = None
    try:
        r = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True
        )

        connection_start_date = time_now_in_timezone(tz_name=camera.city.timezone)
        logger.info(f"📷 Capturing from camera: {camera.name}")
        success, frame = get_frame_from_m3u8(url=camera.url)
        connection_end_date = time_now_in_timezone(tz_name=camera.city.timezone)
        filename = connection_end_date.strftime("%Y%m%d-%H%M%S.jpg")
        s3_key = f"photos/{camera.city.state.slug}/{camera.city.slug}/{camera.slug}/{filename}"

        if success and frame is not None:
            resized_frame = cv2.resize(frame, (640, 640))
            ok, buffer = cv2.imencode(".jpg", resized_frame)

            if ok:
                upload_success, s3_url = upload_to_s3(
                    file_data=buffer.tobytes(),
                    s3_key=s3_key,
                    content_type='image/jpeg'
                )

                if upload_success:
                    redis_key = f"photos:{camera.city.state.slug}:{camera.city.slug}:{camera.slug}:{filename}"
                    r.set(redis_key, s3_url)
                    r.expire(redis_key, 86400)
                    logger.info(f"✅ Photo URL saved in Redis: {redis_key} -> {s3_url}")

                    try:
                        from models.models import Photo

                        photo = Photo.create(
                            camera=camera,
                            state=camera.city.state,
                            city=camera.city,
                            road=camera.road,
                            timezone=camera.city.timezone,
                            file=s3_key,
                            url=s3_url,
                            captured_at=connection_end_date,
                            has_detected_objects=False,
                            detected_at=None
                        )

                        logger.info(f"✅ Photo record created in DB: ID={photo.id}")

                    except Exception as e:
                        logger.error(f"❌ Error creating Photo record: {e}")

                    camera.last_connection_status = True
                    camera.save()

                    return {
                        "camera_id": camera.id,
                        "file": s3_key,
                        "url": s3_url,
                        "state_id": camera.city.state_id,
                        "city_id": camera.city_id,
                        "road_id": camera.road_id,
                        "timezone": camera.city.timezone,
                        "connection_start_date": connection_start_date,
                        "captured_at": connection_end_date,
                        "success": True
                    }
                else:
                    logger.error(f"❌ Failed to upload to S3 for camera: {camera.name}")
            else:
                logger.error(f"❌ Failed to encode frame for camera: {camera.name}")
        else:
            logger.warning(f"⚠️ Failed to capture frame from camera: {camera.name}")

        camera.last_connection_status = False
        camera.save()

        return {
            "camera_id": camera.id,
            "file": "",
            "url": "",
            "state_id": camera.city.state_id,
            "city_id": camera.city_id,
            "road_id": camera.road_id,
            "timezone": camera.city.timezone,
            "connection_start_date": connection_start_date,
            "captured_at": connection_end_date,
            "success": False
        }

    except redis.RedisError as e:
        logger.error(f"❌ Redis error for camera {camera.name}: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Error capturing from camera {camera.name}: {e}")
        return None
    finally:
        if r is not None:
            r.close()


def get_frame_from_m3u8(url: str) -> Tuple[bool, Union[cv2.typing.MatLike, None]]:
    cap = cv2.VideoCapture()
    try:
        cap.open(
            url,
            apiPreference=cv2.CAP_FFMPEG,
            params=[cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, MONITOR_CAPTURE_TIMEOUT]
        )
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                return True, frame
    except cv2.error as exc:
        logger.error(f"OpenCV Error: {exc}")
    except Exception as exc:
        logger.error(f"Unexpected Error: {exc}")
    finally:
        cap.release()

    return False, None

# def download_video_from_m3u8(url: str, filename: str, path: Path = None) -> None:
#     warnings.filterwarnings("ignore", category=requests.packages.urllib3.exceptions.InsecureRequestWarning)
#
#     # Fetch the m3u8 playlist
#     playlist_content = requests.get(url, verify=False).text
#     if "#EXTM3U" not in playlist_content:
#         logging.error("Invalid m3u8 file")
#         return
#
#     # Extract the video segments URLs
#     base_url = url.rsplit("/", 1)[0] + "/"
#     segments = [
#         urljoin(base_url, line.strip()) for line in playlist_content.split("\n") if line.strip().endswith(".ts")
#     ]
#
#     # Download each segment and save to temporary folder
#     temp_folder = path / "temp"
#     if not os.path.exists(temp_folder):
#         os.makedirs(temp_folder)
#
#     total_duration = 0  # Initialize total duration counter
#     for i, segment_url in enumerate(segments):
#         segment_filename = os.path.join(temp_folder, f"segment_{i}.ts")
#         response = requests.get(segment_url, stream=True, verify=False)
#         with open(segment_filename, "wb") as f:
#             for chunk in response.iter_content(chunk_size=1024):
#                 if chunk:
#                     f.write(chunk)
#
#         # Use ffmpeg to get the duration of the downloaded segment
#         command = [
#             "ffprobe",
#             "-v",
#             "error",
#             "-show_entries",
#             "format=duration",
#             "-of",
#             "default=noprint_wrappers=1:nokey=1",
#             segment_filename,
#         ]
#         try:
#             duration = float(subprocess.check_output(command).decode("utf-8").strip())
#         except Exception as e:
#             logging.error(e)
#             return
#         total_duration += duration
#
#         if total_duration >= settings.MAX_DURATION_SECONDS:
#             break  # Stop downloading if total duration exceeds the maximum
#
#     # Concatenate segments into a single video file
#     segment_files = os.listdir(temp_folder)
#     segment_files.sort()
#     segments_paths = [os.path.join(temp_folder, filename) for filename in segment_files]
#     with open(path / filename, "wb") as f:
#         for segment_path in segments_paths:
#             with open(segment_path, "rb") as segment_file:
#                 f.write(segment_file.read())
#
#     logging.info("Video downloaded successfully.")
#
#     # Clean up temporary folder
#     for segment_path in segments_paths:
#         os.remove(segment_path)
#     os.rmdir(temp_folder)
#
#
# def download_image_from_m3u8(url: str, filename: str, path: Path) -> None:
#     cap = cv2.VideoCapture(url)
#     if not cap.isOpened():
#         logging.error(f"Failed to open stream URL: {url}")
#         return
#     ret, frame = cap.read()
#     if not ret:
#         logging.error(f"Failed to get frame from {url}")
#         return
#     path.mkdir(parents=True, exist_ok=True)
#     filepath = str(path / filename)
#     logging.info(f"Downloading image from {url}")
#     if cv2.imwrite(filepath, frame):
#         logging.info(f"Saved image: {filepath}")
#     else:
#         logging.error(f"Failed to save image: {filepath}")
#     cap.release()
#
#
# def download_image_from_url(url: str, filename: str, path: Path) -> None:
#     try:
#         response = requests.get(url)
#         if response.status_code == 200:
#             with open(path / filename, "wb") as f:
#                 f.write(response.content)
#             logging.info(f"Image downloaded successfully: {path / filename}")
#         else:
#             logging.error(f"Failed to download image from {url} ({response.status_code})")
#     except Exception as e:
#         logging.error(e)
