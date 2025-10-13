# run_tests.py
import subprocess
import json
import time
import sys
from datetime import datetime
from telegram_bot.telegram_reporter import TelegramReporter


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
            'success': result.returncode == 0,
            'status': 'SUCCESS ✅' if result.returncode == 0 else 'FAILED ❌',
            'errors': [],
            'error_details': []
        }

        # Collect failed test names and details
        if 'tests' in report:
            for test in report['tests']:
                if test.get('outcome') == 'failed':
                    test_name = test['nodeid']
                    results['errors'].append(test_name)

                    # Extract error details
                    error_detail = {
                        'test': test_name,
                        'message': '',
                        'traceback': ''
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
                                    error_detail['message'] = line.strip()[:200]
                                    break

                    # Fallback to short representation
                    if not error_detail['message']:
                        error_detail['message'] = test.get('call', {}).get('crash', {}).get('message', 'Test failed')

                    results['error_details'].append(error_detail)

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
            'error_details': [{'test': 'Parser', 'message': str(e), 'traceback': ''}]
        }


def print_summary(results):
    """Print test summary"""
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    print(f"⏱️  Duration:  {results['duration']:.2f}s")
    print(f"📊 Total:     {results['total']}")
    print(f"✅ Passed:    {results['passed']}")
    print(f"❌ Failed:    {results['failed']}")
    print(f"⚠️  Skipped:   {results['skipped']}")
    print(f"📈 Coverage:  {results['coverage']}%")
    print(f"🎯 Status:    {results['status']}")

    if results['failed'] > 0 and results['errors']:
        print(f"\n💥 Failed Tests:")
        for i, error in enumerate(results['errors'][:5], 1):
            print(f"  {i}. {error}")
        if len(results['errors']) > 5:
            print(f"  ...and {len(results['errors']) - 5} more")

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