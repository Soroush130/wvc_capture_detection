# tasks.py
from celery import group, chord
from celery_app import app
from capture.capture_utils import capture
from detection.detection_utils import detect_objects
from models.db_operations import (
    ensure_connection,
    safe_close_connection,
    get_camera_by_id,
    get_active_cameras_for_capture,
    get_undetected_photos,
    update_photo_detection,
    save_detected_objects
)
from logger_config import get_logger
from datetime import datetime

logger = get_logger(__name__)


# ==================== CAPTURE TASKS ====================
@app.task(bind=True, max_retries=2, queue='capture')
def capture_single_camera(self, camera_id):
    """
    Capture a single photo from a camera

    Args:
        camera_id: ID of the camera

    Returns:
        Dictionary with capture result
    """
    try:
        # Get camera from database
        camera = get_camera_by_id(camera_id)

        if not camera:
            logger.error(f"❌ Camera {camera_id} not found")
            return {
                'camera_id': camera_id,
                'status': 'not_found'
            }

        # Capture photo
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

    except self.MaxRetriesExceededError:
        logger.error(f"❌ Max retries exceeded for camera {camera_id}")
        return {
            'camera_id': camera_id,
            'status': 'failed_after_retries'
        }
    except Exception as e:
        logger.error(f"❌ Error capturing camera {camera_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'camera_id': camera_id,
            'status': 'error',
            'error': str(e)
        }


@app.task(queue='capture')
def summarize_capture_results(results):
    """
    Summarize capture results and log statistics

    Args:
        results: List of capture result dictionaries

    Returns:
        Summary dictionary
    """
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

        # Failure breakdown
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
        import traceback
        logger.error(traceback.format_exc())
        return {'error': str(e)}


@app.task(queue='capture')
def schedule_camera_captures():
    """
    Schedule capture tasks for all active cameras
    Uses chord to run captures in parallel and summarize results

    Returns:
        Dictionary with scheduling result
    """
    try:
        # Get active camera IDs
        camera_ids = get_active_cameras_for_capture()

        logger.info("=" * 80)
        logger.info(f"🚀 Starting capture cycle for {len(camera_ids)} cameras")
        logger.info("=" * 80)

        if not camera_ids:
            logger.warning("⚠️ No active cameras found")
            return {
                'scheduled': 0,
                'error': 'No active cameras'
            }

        # Create chord: parallel captures + summary callback
        job = chord(
            (capture_single_camera.s(camera_id) for camera_id in camera_ids),
            summarize_capture_results.s()
        )

        # Execute asynchronously
        job.apply_async()

        logger.info(f"✅ Scheduled {len(camera_ids)} capture tasks")

        return {
            'scheduled': len(camera_ids),
            'timestamp': datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Error scheduling captures: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'error': str(e),
            'scheduled': 0
        }


# ==================== DETECTION TASKS ====================
@app.task(bind=True, max_retries=2, queue='detection')
def detect_single_photo(self, photo_id: int, s3_key: str):
    """
    Detect objects in a single photo

    Args:
        photo_id: ID of the photo in database
        s3_key: S3 key of the photo

    Returns:
        Dictionary with detection results
    """
    try:
        logger.info(f"🔍 Starting detection for photo {photo_id}")

        # Detect objects
        result = detect_objects(photo_id, s3_key)

        if result is None:
            logger.error(f"❌ Detection failed for photo {photo_id}")
            return {
                'photo_id': photo_id,
                'status': 'error',
                'message': 'Detection failed'
            }

        # Update photo detection results in database
        update_success = update_photo_detection(
            photo_id=photo_id,
            counts=result['counts'],
            has_detected_objects=result['has_detected_objects']
        )

        if not update_success:
            logger.error(f"❌ Failed to update database for photo {photo_id}")
            return {
                'photo_id': photo_id,
                'status': 'error',
                'message': 'Database update failed'
            }

        # Save detected objects to database
        if result['detected_objects']:
            save_success = save_detected_objects(
                photo_id=photo_id,
                detected_objects=result['detected_objects']
            )

            if not save_success:
                logger.warning(f"⚠️ Failed to save detected objects for photo {photo_id}")

        # Log completion
        logger.info(
            f"✅ Detection complete for photo {photo_id}: "
            f"{result['total_objects_detected']} objects | "
            f"Raw: {result['total_raw_detections']} | "
            f"Classes: {result['classes_detected']} | "
            f"has_objects: {result['has_detected_objects']}"
        )

        return {
            'photo_id': photo_id,
            'status': 'success',
            'detected_objects': result['total_objects_detected'],
            'raw_detections': result['total_raw_detections'],
            'classes': result['classes_detected'],
            'has_detected_objects': result['has_detected_objects'],
            'counts': result['counts']
        }

    except Exception as e:
        logger.error(f"❌ Error detecting photo {photo_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())

        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60)


@app.task(queue='detection')
def schedule_photo_detection():
    """
    Schedule detection tasks for undetected photos
    This task runs every minute via Celery Beat

    Returns:
        Dictionary with scheduling result
    """
    try:
        logger.info("📸 Checking for undetected photos...")

        # Get undetected photos
        photos = get_undetected_photos(limit=100)

        if not photos:
            logger.info("✅ No undetected photos found")
            return {
                'status': 'success',
                'photos_scheduled': 0,
                'message': 'No undetected photos'
            }

        logger.info(f"📊 Found {len(photos)} undetected photos, scheduling detection tasks...")

        # Schedule detection task for each photo
        scheduled_count = 0
        for photo in photos:
            try:
                detect_single_photo.apply_async(
                    args=[photo['id'], photo['s3_key']],
                    queue='detection'
                )
                scheduled_count += 1
            except Exception as e:
                logger.error(f"❌ Failed to schedule detection for photo {photo['id']}: {e}")

        logger.info(f"✅ Scheduled {scheduled_count} detection tasks")

        return {
            'status': 'success',
            'photos_scheduled': scheduled_count,
            'total_found': len(photos),
            'timestamp': datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Error in schedule_photo_detection: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'status': 'error',
            'message': str(e)
        }


# ==================== TEST TASKS ====================
@app.task(queue='capture')
def run_scheduled_tests():
    """
    Run pytest tests and send report to Telegram
    Scheduled to run daily at midnight NY time

    Returns:
        Dictionary with test results
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

        # Run tests with timeout
        result = subprocess.run(
            [sys.executable, 'run_tests.py'],
            capture_output=True,
            text=True,
            cwd=str(project_root),
            timeout=600  # 10 minutes timeout
        )

        # Parse results
        test_results = {
            'return_code': result.returncode,
            'success': result.returncode == 0,
            'stdout_preview': result.stdout[:500] if result.stdout else '',
            'stderr_preview': result.stderr[:500] if result.stderr else '',
            'timestamp': datetime.now().isoformat()
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
        return {
            'error': 'timeout',
            'success': False,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"❌ Error running tests: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'error': str(e),
            'success': False,
            'timestamp': datetime.now().isoformat()
        }


@app.task(queue='capture')
def run_tests_with_summary():
    """
    Run tests and return detailed summary
    Wrapper around run_scheduled_tests

    Returns:
        Dictionary with test summary
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
        import traceback
        logger.error(traceback.format_exc())
        return {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'error',
            'error': str(e)
        }