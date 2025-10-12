from celery import group, chord
from celery_app import app
from capture.capture_utils import capture
from detection.detection_utils import detect_objects
from models.models import Camera, City, State, db, Photo, DetectedObject
from logger_config import get_logger
from datetime import datetime
import redis
import os

logger = get_logger(__name__)


@app.task(bind=True, max_retries=2, queue='capture')
def capture_single_camera(self, camera_id):
    try:
        if db.is_closed():
            db.connect()
        camera = Camera.get_by_id(camera_id)
        result = capture(camera)
        if result and result.get('success'):
            logger.info(f"✅ Success: {camera.name}")
            return {
                'camera_id': camera_id,
                'camera_name': camera.name,
                'status': 'success'
            }
        else:
            logger.warning(f"⚠️ Failed: {camera.name}, retrying...")
            raise self.retry(countdown=5)
    except Camera.DoesNotExist:
        logger.error(f"❌ Camera {camera_id} not found")
        return {'camera_id': camera_id, 'status': 'not_found'}
    except self.MaxRetriesExceededError:
        logger.error(f"❌ Max retries for camera {camera_id}")
        return {'camera_id': camera_id, 'status': 'failed_after_retries'}
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return {'camera_id': camera_id, 'status': 'error'}
    finally:
        if not db.is_closed():
            db.close()


@app.task(queue='capture')
def summarize_capture_results(results):
    try:
        total = len(results)
        success = sum(1 for r in results if r.get('status') == 'success')
        failed = total - success

        success_rate = (success / total * 100) if total > 0 else 0

        logger.info("=" * 80)
        logger.info("📊 CAPTURE SUMMARY REPORT")
        logger.info("=" * 80)
        logger.info(f"📷 Total Cameras: {total}")
        logger.info(f"✅ Successful: {success} ({success_rate:.1f}%)")
        logger.info(f"❌ Failed: {failed} ({100 - success_rate:.1f}%)")
        logger.info("=" * 80)

        not_found = sum(1 for r in results if r.get('status') == 'not_found')
        max_retries = sum(1 for r in results if r.get('status') == 'failed_after_retries')
        errors = sum(1 for r in results if r.get('status') == 'error')

        if failed > 0:
            logger.warning(f"⚠️ Failure breakdown:")
            if not_found > 0:
                logger.warning(f"   • Not found: {not_found}")
            if max_retries > 0:
                logger.warning(f"   • Max retries: {max_retries}")
            if errors > 0:
                logger.warning(f"   • Other errors: {errors}")

        return {
            'total': total,
            'success': success,
            'failed': failed,
            'success_rate': success_rate,
            'breakdown': {
                'not_found': not_found,
                'max_retries': max_retries,
                'errors': errors
            }
        }

    except Exception as e:
        logger.error(f"❌ Error summarizing results: {e}")
        return {'error': str(e)}


@app.task(queue='capture')
def schedule_camera_captures():
    try:
        if db.is_closed():
            db.connect()

        cameras = list(
            Camera
            .select(Camera.id)
            .join(City)
            .join(State)
            .where(State.is_active == True)
        )

        camera_ids = [c.id for c in cameras]

        logger.info("=" * 80)
        logger.info(f"🚀 Starting capture cycle for {len(camera_ids)} cameras")
        logger.info("=" * 80)

        if not camera_ids:
            logger.warning("⚠️ No active cameras found")
            return {'scheduled': 0, 'error': 'No cameras'}

        job = chord(
            (capture_single_camera.s(camera_id) for camera_id in camera_ids),
            summarize_capture_results.s()
        )

        job.apply_async()

        logger.info(f"✅ Scheduled {len(camera_ids)} capture tasks")

        return {'scheduled': len(camera_ids)}

    except Exception as e:
        logger.error(f"❌ Error scheduling captures: {e}")
        return {'error': str(e)}
    finally:
        if not db.is_closed():
            db.close()


@app.task(bind=True, max_retries=2, queue='detection')
def detect_single_photo(self, photo_id: int, s3_key: str):
    try:
        if db.is_closed():
            db.connect()

        photo = Photo.get_by_id(photo_id)

        result = detect_objects(photo_id, s3_key)

        if result:
            photo.has_detected_objects = result['has_detected_objects']
            photo.car_count_above_system_confidence = result['counts']['car_above']
            photo.car_count_below_system_confidence = result['counts']['car_below']
            photo.truck_count_above_system_confidence = result['counts']['truck_above']
            photo.truck_count_below_system_confidence = result['counts']['truck_below']
            photo.person_count_above_system_confidence = result['counts']['person_above']
            photo.person_count_below_system_confidence = result['counts']['person_below']
            photo.deer_count_above_system_confidence = result['counts']['deer_above']
            photo.deer_count_below_system_confidence = result['counts']['deer_below']
            photo.detected_at = datetime.now()
            photo.save()

            for obj in result['detected_objects']:
                DetectedObject.create(
                    photo=photo,
                    camera=photo.camera,
                    state=photo.state,
                    city=photo.city,
                    road=photo.road,
                    timezone=photo.timezone,
                    name=obj['name'],
                    image=obj['s3_key'] or 'objects/not-saved.jpg',
                    conf=obj['confidence'],
                    x=obj['x'],
                    y=obj['y'],
                    width=obj['width'],
                    height=obj['height'],
                    captured_at=photo.captured_at
                )

            logger.info(f"✅ Detected {len(result['detected_objects'])} objects in photo {photo_id}")
            return {
                'photo_id': photo_id,
                'status': 'success',
                'objects_count': len(result['detected_objects'])
            }
        else:
            logger.warning(f"⚠️ Detection failed for photo {photo_id}")
            raise self.retry(countdown=10)

    except Photo.DoesNotExist:
        logger.error(f"❌ Photo {photo_id} not found")
        return {'photo_id': photo_id, 'status': 'not_found'}
    except self.MaxRetriesExceededError:
        logger.error(f"❌ Max retries for photo {photo_id}")
        return {'photo_id': photo_id, 'status': 'failed_after_retries'}
    except Exception as e:
        logger.error(f"❌ Error detecting photo {photo_id}: {e}")
        return {'photo_id': photo_id, 'status': 'error'}
    finally:
        if not db.is_closed():
            db.close()


@app.task(queue='detection')
def schedule_photo_detection():
    try:
        r = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=int(os.getenv('REDIS_DB', 0)),
            decode_responses=False
        )

        keys = r.keys(b'photos:*')
        logger.info(f"📋 Found {len(keys)} photos in Redis")

        if not keys:
            return {'detected': 0}

        if db.is_closed():
            db.connect()

        tasks_list = []
        processed = 0
        skipped_binary = 0
        skipped_invalid = 0
        skipped_not_found = 0
        skipped_already_detected = 0

        for key in keys:
            try:
                processed += 1
                value = r.get(key)

                if not value:
                    continue

                try:
                    s3_url = value.decode('utf-8')
                except UnicodeDecodeError:
                    logger.warning(f"⚠️ Skipping binary data in key: {key.decode('utf-8')}")
                    r.delete(key)
                    skipped_binary += 1
                    continue

                if not s3_url.startswith('http'):
                    logger.warning(f"⚠️ Invalid URL in key: {key.decode('utf-8')}")
                    r.delete(key)
                    skipped_invalid += 1
                    continue

                # ✅ حذف query parameters از URL
                from urllib.parse import urlparse

                parsed_url = urlparse(s3_url)
                # فقط path بدون query parameters
                clean_path = parsed_url.path

                # حذف leading slash
                if clean_path.startswith('/'):
                    clean_path = clean_path[1:]

                # حذف 'uploads/' اگر وجود داشت
                if clean_path.startswith('uploads/'):
                    s3_key = clean_path.replace('uploads/', '', 1)
                else:
                    s3_key = clean_path

                if processed <= 5:
                    logger.info(f"🔍 DEBUG: s3_url = {s3_url}")
                    logger.info(f"🔍 DEBUG: clean s3_key = {s3_key}")

                filename = key.decode('utf-8').split(':')[-1]

                # جستجوی Photo
                photo = Photo.select().where(
                    Photo.file == s3_key
                ).first()

                if not photo:
                    if processed <= 5:
                        logger.warning(f"⚠️ Photo not found in DB: {s3_key}")
                    skipped_not_found += 1
                    continue

                # چک detected_at
                if photo.detected_at is not None:
                    skipped_already_detected += 1
                    continue

                tasks_list.append(detect_single_photo.s(photo.id, s3_key))

            except Exception as e:
                logger.error(f"❌ Error processing key {key}: {e}")
                continue

        logger.info("=" * 80)
        logger.info(f"📊 Detection Scheduling Summary:")
        logger.info(f"  Total in Redis: {len(keys)}")
        logger.info(f"  Processed: {processed}")
        logger.info(f"  Skipped (binary): {skipped_binary}")
        logger.info(f"  Skipped (invalid URL): {skipped_invalid}")
        logger.info(f"  Skipped (not found in DB): {skipped_not_found}")
        logger.info(f"  Skipped (already detected): {skipped_already_detected}")
        logger.info(f"  ✅ Scheduled for detection: {len(tasks_list)}")
        logger.info("=" * 80)

        if tasks_list:
            job = group(tasks_list)
            job.apply_async()
            logger.info(f"✅ Scheduled {len(tasks_list)} photos for detection")

        return {
            'detected': len(tasks_list),
            'skipped_not_found': skipped_not_found,
            'skipped_already_detected': skipped_already_detected
        }

    except Exception as e:
        logger.error(f"❌ Error scheduling detection: {e}")
        return {'error': str(e)}
    finally:
        if not db.is_closed():
            db.close()
        if 'r' in locals():
            r.close()


@app.task(queue='capture')
def run_scheduled_tests():
    """
    Run pytest tests and send report to Telegram
    Scheduled to run daily at midnight NY time
    """
    import subprocess
    import sys
    import json
    from pathlib import Path

    try:
        logger.info("=" * 80)
        logger.info("🧪 Starting scheduled test run")
        logger.info("=" * 80)

        # Get project root directory
        project_root = Path(__file__).parent

        # Run tests
        result = subprocess.run(
            [sys.executable, 'run_tests.py'],
            capture_output=True,
            text=True,
            cwd=str(project_root),
            timeout=600
        )

        # Parse results
        test_results = {
            'return_code': result.returncode,
            'success': result.returncode == 0,
            'stdout_preview': result.stdout[:500] if result.stdout else '',
            'stderr_preview': result.stderr[:500] if result.stderr else ''
        }

        # Try to read test report JSON
        try:
            report_file = project_root / 'test_report.json'
            if report_file.exists():
                with open(report_file, 'r', encoding='utf-8') as f:
                    report = json.load(f)
                    test_results['total'] = report['summary']['total']
                    test_results['passed'] = report['summary'].get('passed', 0)
                    test_results['failed'] = report['summary'].get('failed', 0)
                    test_results['skipped'] = report['summary'].get('skipped', 0)
        except Exception as e:
            logger.warning(f"⚠️ Could not parse test report: {e}")

        # Log summary
        if test_results['success']:
            logger.info(f"✅ Tests PASSED - {test_results.get('passed', 0)}/{test_results.get('total', 0)}")
        else:
            logger.error(f"❌ Tests FAILED - {test_results.get('failed', 0)} failures")

        logger.info("=" * 80)
        logger.info("📊 TEST RUN SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Status: {'✅ SUCCESS' if test_results['success'] else '❌ FAILED'}")
        if 'total' in test_results:
            logger.info(f"Total: {test_results['total']}")
            logger.info(f"Passed: {test_results['passed']}")
            logger.info(f"Failed: {test_results['failed']}")
            logger.info(f"Skipped: {test_results['skipped']}")
        logger.info("=" * 80)

        return test_results

    except subprocess.TimeoutExpired:
        logger.error("❌ Test run timed out after 10 minutes")
        return {'error': 'timeout', 'success': False}
    except Exception as e:
        logger.error(f"❌ Error running tests: {e}")
        return {'error': str(e), 'success': False}


@app.task(queue='capture')
def run_tests_with_summary():
    """
    Run tests and return detailed summary
    """
    try:
        result = run_scheduled_tests()

        summary = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'success' if result.get('success') else 'failed',
            'results': result
        }

        return summary

    except Exception as e:
        logger.error(f"❌ Error in test summary: {e}")
        return {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'error',
            'error': str(e)
        }