# run_tests.py
import subprocess
import json
import time
import sys
import psutil
from datetime import datetime, timedelta
from telegram_bot.telegram_reporter import TelegramReporter


def get_system_info():
    """Get system information"""
    try:
        system_info = {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'memory_available_gb': round(psutil.virtual_memory().available / (1024 ** 3), 2),
            'memory_total_gb': round(psutil.virtual_memory().total / (1024 ** 3), 2),
            'disk_percent': psutil.disk_usage('/').percent,
            'disk_free_gb': round(psutil.disk_usage('/').free / (1024 ** 3), 2),
        }

        # GPU info if available
        try:
            import torch
            if torch.cuda.is_available():
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
                gpu_used = torch.cuda.memory_allocated(0) / (1024 ** 3)
                gpu_name = torch.cuda.get_device_name(0)

                system_info['gpu_available'] = True
                system_info['gpu_name'] = gpu_name
                system_info['gpu_memory_total_gb'] = round(gpu_memory, 2)
                system_info['gpu_memory_used_gb'] = round(gpu_used, 2)
                system_info['gpu_memory_free_gb'] = round(gpu_memory - gpu_used, 2)
            else:
                system_info['gpu_available'] = False
        except Exception as e:
            system_info['gpu_available'] = False
            system_info['gpu_error'] = str(e)

        return system_info

    except Exception as e:
        print(f"⚠️  Could not get system info: {e}")
        return {}


def get_database_stats():
    """Get database statistics"""
    try:
        from models.db_operations import ensure_connection
        from models.models import Photo, Camera, DetectedObject

        ensure_connection()

        db_stats = {
            'total_photos': Photo.select().count(),
            'detected_photos': Photo.select().where(Photo.has_detected_objects == True).count(),
            'undetected_photos': Photo.select().where(Photo.has_detected_objects == False).count(),
            'total_cameras': Camera.select().count(),
            'active_cameras': Camera.select().where(Camera.is_active == True).count(),
            'inactive_cameras': Camera.select().where(Camera.is_active == False).count(),
            'total_objects': DetectedObject.select().count(),
        }

        # Calculate detection rate
        if db_stats['total_photos'] > 0:
            db_stats['detection_rate'] = round(
                (db_stats['detected_photos'] / db_stats['total_photos']) * 100, 2
            )
        else:
            db_stats['detection_rate'] = 0.0

        return db_stats

    except Exception as e:
        print(f"⚠️  Could not get database stats: {e}")
        return {'error': str(e)}


def get_recent_activity():
    """Get recent activity (last hour)"""
    try:
        from models.models import Photo

        one_hour_ago = datetime.now() - timedelta(hours=1)

        recent_photos = Photo.select().where(Photo.created_at >= one_hour_ago).count()
        recent_detections = Photo.select().where(
            (Photo.created_at >= one_hour_ago) &
            (Photo.has_detected_objects == True)
        ).count()

        # Last 24 hours for comparison
        twenty_four_hours_ago = datetime.now() - timedelta(hours=24)
        photos_24h = Photo.select().where(Photo.created_at >= twenty_four_hours_ago).count()
        detections_24h = Photo.select().where(
            (Photo.created_at >= twenty_four_hours_ago) &
            (Photo.has_detected_objects == True)
        ).count()

        return {
            'photos_last_hour': recent_photos,
            'detections_last_hour': recent_detections,
            'photos_last_24h': photos_24h,
            'detections_last_24h': detections_24h,
        }

    except Exception as e:
        print(f"⚠️  Could not get recent activity: {e}")
        return {}


def run_tests():
    """Run pytest and collect results"""
    print("=" * 60)
    print("🧪 WVC Test Runner")
    print("=" * 60)
    print(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    start_time = time.time()

    # Run pytest - همه config از pytest.ini می‌آید
    result = subprocess.run(
        [
            sys.executable, '-m', 'pytest',
            'tests/',  # فقط مسیر tests را می‌دهیم
        ],
        capture_output=True,
        text=True
    )

    duration = time.time() - start_time

    # Print pytest output
    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    # Parse results
    try:
        # Read test report
        with open('test_report.json', 'r', encoding='utf-8') as f:
            report = json.load(f)

        # Read coverage
        coverage = 0
        try:
            with open('coverage.json', 'r', encoding='utf-8') as f:
                coverage_data = json.load(f)
                coverage = coverage_data['totals']['percent_covered']
        except:
            pass

        # Build results
        results = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'duration': duration,
            'total': report['summary']['total'],
            'passed': report['summary'].get('passed', 0),
            'failed': report['summary'].get('failed', 0),
            'skipped': report['summary'].get('skipped', 0),
            'coverage': round(coverage, 2),
            'success': report['summary'].get('failed', 0) == 0 and report['summary']['total'] > 0,
            'status': 'SUCCESS ✅' if (
                        report['summary'].get('failed', 0) == 0 and report['summary']['total'] > 0) else 'FAILED ❌',
            'errors': [],
            'error_details': [],
            'failed_tests': []
        }

        # Collect failed test names and details
        if 'tests' in report:
            for test in report['tests']:
                if test.get('outcome') == 'failed':
                    test_name = test['nodeid']
                    results['errors'].append(test_name)

                    # Extract error details
                    error_detail = {
                        'name': test_name,
                        'outcome': 'failed',
                        'message': ''
                    }

                    # Get error message
                    if 'call' in test and 'longrepr' in test['call']:
                        longrepr = test['call']['longrepr']
                        if isinstance(longrepr, str):
                            # Extract just the assertion error
                            lines = longrepr.split('\n')
                            for i, line in enumerate(lines):
                                if 'AssertionError' in line or 'Error:' in line:
                                    error_detail['message'] = line.strip()
                                    break
                                elif line.startswith('E   '):
                                    error_detail['message'] = line.replace('E   ', '').strip()
                                    break

                        # If no specific message found, use first error line
                        if not error_detail['message'] and isinstance(longrepr, str):
                            for line in longrepr.split('\n'):
                                if line.strip() and ('assert' in line.lower() or 'error' in line.lower()):
                                    error_detail['message'] = line.strip()[:300]
                                    break

                    # Fallback to short representation
                    if not error_detail['message']:
                        error_detail['message'] = test.get('call', {}).get('crash', {}).get('message', 'Test failed')

                    results['error_details'].append(error_detail)
                    results['failed_tests'].append(error_detail)

        # Add system information
        print("\n📊 Collecting system information...")
        results['system_info'] = get_system_info()

        # Add database statistics
        print("📊 Collecting database statistics...")
        results['database_stats'] = get_database_stats()

        # Add recent activity
        print("📊 Collecting recent activity...")
        results['recent_activity'] = get_recent_activity()

        return results

    except Exception as e:
        print(f"\n❌ Error parsing test results: {e}")
        import traceback
        print(traceback.format_exc())

        return {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'duration': duration,
            'total': 0,
            'passed': 0,
            'failed': 1,
            'skipped': 0,
            'coverage': 0,
            'success': False,
            'status': 'ERROR ❌',
            'errors': [str(e)],
            'error_details': [{'name': 'Parser', 'message': str(e)}],
            'failed_tests': [{'name': 'Parser', 'outcome': 'failed', 'message': str(e)}]
        }


def print_summary(results):
    """Print comprehensive test summary"""
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    print(f"⏱️  Duration:  {results['duration']:.2f}s")
    print(f"📊 Total:     {results['total']}")
    print(f"✅ Passed:    {results['passed']}")
    print(f"❌ Failed:    {results['failed']}")
    print(f"⚠️  Skipped:   {results['skipped']}")
    print(f"📈 Coverage:  {results['coverage']}%")

    # Success rate
    if results['total'] > 0:
        success_rate = (results['passed'] / results['total']) * 100
        print(f"📊 Success:   {success_rate:.1f}%")

    print(f"🎯 Status:    {results['status']}")

    # System Information
    system_info = results.get('system_info', {})
    if system_info:
        print("\n" + "=" * 60)
        print("💻 System Status")
        print("=" * 60)
        print(f"🔲 CPU:       {system_info.get('cpu_percent', 0):.1f}%")
        print(f"🧠 Memory:    {system_info.get('memory_percent', 0):.1f}% "
              f"({system_info.get('memory_available_gb', 0):.1f}/{system_info.get('memory_total_gb', 0):.1f} GB free)")
        print(f"💾 Disk:      {system_info.get('disk_percent', 0):.1f}% "
              f"({system_info.get('disk_free_gb', 0):.1f} GB free)")

        if system_info.get('gpu_available'):
            gpu_used = system_info.get('gpu_memory_used_gb', 0)
            gpu_total = system_info.get('gpu_memory_total_gb', 0)
            gpu_percent = (gpu_used / gpu_total * 100) if gpu_total > 0 else 0
            print(f"🎮 GPU:       {gpu_percent:.1f}% - {system_info.get('gpu_name', 'Unknown')}")
            print(f"              {gpu_used:.1f}/{gpu_total:.1f} GB used")
        else:
            print(f"🎮 GPU:       Not available")

    # Database Statistics
    db_stats = results.get('database_stats', {})
    if db_stats and 'error' not in db_stats:
        print("\n" + "=" * 60)
        print("🗄️  Database Statistics")
        print("=" * 60)
        print(f"📷 Total Photos:      {db_stats.get('total_photos', 0):,}")
        print(f"   ✅ With Objects:   {db_stats.get('detected_photos', 0):,}")
        print(f"   ❌ Without:        {db_stats.get('undetected_photos', 0):,}")
        print(f"   📈 Detection Rate: {db_stats.get('detection_rate', 0):.1f}%")
        print(f"\n📹 Cameras:")
        print(f"   Total:             {db_stats.get('total_cameras', 0)}")
        print(f"   🟢 Active:         {db_stats.get('active_cameras', 0)}")
        print(f"   🔴 Inactive:       {db_stats.get('inactive_cameras', 0)}")
        print(f"\n🔍 Total Objects:     {db_stats.get('total_objects', 0):,}")

    # Recent Activity
    recent = results.get('recent_activity', {})
    if recent:
        print("\n" + "=" * 60)
        print("📊 Recent Activity")
        print("=" * 60)
        print(f"Last Hour:")
        print(f"   📸 Photos:         {recent.get('photos_last_hour', 0)}")
        print(f"   🔍 Detections:     {recent.get('detections_last_hour', 0)}")
        print(f"\nLast 24 Hours:")
        print(f"   📸 Photos:         {recent.get('photos_last_24h', 0)}")
        print(f"   🔍 Detections:     {recent.get('detections_last_24h', 0)}")

    # Failed Tests
    if results['failed'] > 0 and results['errors']:
        print("\n" + "=" * 60)
        print("💥 Failed Tests")
        print("=" * 60)

        failed_tests = results.get('failed_tests', [])

        for i, test in enumerate(failed_tests[:5], 1):
            test_name = test.get('name', 'Unknown').split("::")[-1]
            print(f"\n{i}. {test_name}")

            error_msg = test.get('message', '').strip()
            if error_msg:
                # Show first 200 chars of error
                if len(error_msg) > 200:
                    error_msg = error_msg[:197] + "..."
                print(f"   ⚠️  {error_msg}")

        if len(failed_tests) > 5:
            print(f"\n...and {len(failed_tests) - 5} more failures")

        print("\n💡 Tip: Check test_report.json for full details")

    print("=" * 60)


def main():
    """Main function"""
    # Run tests
    results = run_tests()

    # Print summary
    print_summary(results)

    # Send to Telegram
    print("\n📤 Sending report to Telegram...")
    try:
        reporter = TelegramReporter()
        success_count, fail_count = reporter.send_sync(results)

        if success_count > 0:
            print(f"✅ Report sent to {success_count} recipient(s)")
        if fail_count > 0:
            print(f"❌ Failed to send to {fail_count} recipient(s)")
    except ValueError as e:
        print(f"⚠️  Telegram not configured: {e}")
    except Exception as e:
        print(f"❌ Failed to send report: {e}")
        import traceback
        print(traceback.format_exc())

    print("\n" + "=" * 60)
    print(f"📅 Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60 + "\n")

    # Exit with appropriate code
    sys.exit(0 if results['success'] else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)