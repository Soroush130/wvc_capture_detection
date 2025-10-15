# telegram_bot/telegram_reporter.py
import os
import asyncio
from telegram import Bot
from dotenv import load_dotenv
from logger_config import get_logger

load_dotenv()

logger = get_logger(__name__)


class TelegramReporter:
    """Send comprehensive test results to Telegram"""

    def __init__(self):
        self.token = os.getenv('TELEGRAM_API_KEY')
        self.chat_ids = os.getenv('TELEGRAM_CHAT_IDS', '').split(',')

        if not self.token:
            raise ValueError("TELEGRAM_API_KEY not found in environment")

        if not self.chat_ids or self.chat_ids == ['']:
            raise ValueError("TELEGRAM_CHAT_IDS not found in environment")

        self.bot = Bot(token=self.token)

    def format_message(self, results):
        """Format test results as comprehensive text report"""
        emoji_status = "✅" if results.get('success') else "❌"

        lines = []

        # Header
        lines.append(" WVC System Test Report")
        lines.append("=" * 40)
        lines.append(f"📅 Date: {results.get('timestamp', 'N/A')}")
        lines.append(f"⏱️  Duration: {results.get('duration', 0):.2f}s")
        lines.append("")

        # Test Results
        lines.append(" Test Results:")
        lines.append(f"   ✅ Passed:  {results.get('passed', 0)}")
        lines.append(f"   ❌ Failed:  {results.get('failed', 0)}")
        lines.append(f"   ⏭️  Skipped: {results.get('skipped', 0)}")
        lines.append(f"   📊 Total:   {results.get('total', 0)}")

        # Success rate
        if results.get('total', 0) > 0:
            success_rate = (results.get('passed', 0) / results.get('total', 0)) * 100
            lines.append(f"   📈 Success: {success_rate:.1f}%")

        lines.append("")

        # System Information
        system_info = results.get('system_info', {})
        if system_info:
            lines.append("💻 System Status:")
            lines.append(f"   🔲 CPU:    {system_info.get('cpu_percent', 0):.1f}%")
            lines.append(f"   🧠 Memory: {system_info.get('memory_percent', 0):.1f}%")
            lines.append(f"   💾 Disk:   {system_info.get('disk_percent', 0):.1f}%")

            if system_info.get('gpu_available'):
                gpu_used = system_info.get('gpu_memory_used_gb', 0)
                gpu_total = system_info.get('gpu_memory_total_gb', 0)
                gpu_percent = (gpu_used / gpu_total * 100) if gpu_total > 0 else 0
                lines.append(f"   🎮 GPU:    {gpu_percent:.1f}% ({gpu_used:.1f}/{gpu_total:.1f} GB)")
            else:
                lines.append(f"   🎮 GPU:    Not available")

            lines.append("")

        # Database Statistics
        db_stats = results.get('database_stats', {})
        if db_stats and 'error' not in db_stats:
            lines.append("🗄️  Database Stats:")
            lines.append(f"   📷 Total Photos:    {db_stats.get('total_photos', 0):,}")
            lines.append(f"   ✅ With Detections: {db_stats.get('detected_photos', 0):,}")
            lines.append(f"   📹 Total Cameras:   {db_stats.get('total_cameras', 0)}")

            # ✅ Only show if available
            if 'active_cameras' in db_stats:
                lines.append(f"   🟢 Active States:   {db_stats.get('active_cameras', 0)}")
                lines.append(f"   🔴 Inactive States: {db_stats.get('inactive_cameras', 0)}")

            lines.append(f"   🔍 Total Objects:   {db_stats.get('total_objects', 0):,}")

            # Detection rate
            if db_stats.get('total_photos', 0) > 0:
                detection_rate = (db_stats.get('detected_photos', 0) / db_stats.get('total_photos', 0)) * 100
                lines.append(f"   📈 Detection Rate:  {detection_rate:.1f}%")

            lines.append("")

        # Recent Activity
        recent = results.get('recent_activity', {})
        if recent:
            lines.append("📊 Last Hour Activity:")
            lines.append(f"   📸 New Photos:      {recent.get('photos_last_hour', 0)}")
            lines.append(f"   🔍 New Detections:  {recent.get('detections_last_hour', 0)}")
            lines.append("")

        # Overall Status
        status_emoji = "🎉" if results.get('success') else "💥"
        status_text = "ALL TESTS PASSED" if results.get('success') else "TESTS FAILED"
        lines.append(f"{status_emoji} Status: {status_text}")
        lines.append("=" * 40)

        # Failed Tests Details
        if results.get('failed', 0) > 0:
            lines.append("")
            lines.append("💥 Failed Tests:")
            lines.append("-" * 40)

            failed_tests = results.get('failed_tests', [])

            # Show up to 3 failed tests with details
            for i, test in enumerate(failed_tests[:3], 1):
                # Get short test name
                test_name = test.get('name', 'Unknown').split("::")[-1]
                if len(test_name) > 35:
                    test_name = test_name[:32] + "..."

                lines.append(f"\n{i}. {test_name}")

                # Add error message
                error_msg = test.get('message', '').strip()
                if error_msg:
                    # Extract key error info
                    error_lines = error_msg.split('\n')
                    key_error = None

                    # Look for assertion errors or key phrases
                    for line in error_lines:
                        if 'AssertionError' in line or 'Error' in line or 'assert' in line:
                            key_error = line.strip()
                            break

                    if not key_error and error_lines:
                        key_error = error_lines[0].strip()

                    if key_error:
                        if len(key_error) > 120:
                            key_error = key_error[:117] + "..."
                        lines.append(f"   ⚠️  {key_error}")

            # Show count of remaining failures
            if len(failed_tests) > 3:
                lines.append(f"\n...and {len(failed_tests) - 3} more test failures")

            lines.append("")
            lines.append("💡 Tip: Check logs for full details")

        # Success message
        elif results.get('success'):
            lines.append("")
            lines.append("✨ All systems operational!")
            lines.append("🚀 Ready for production")

        return "\n".join(lines)

    async def send_report(self, results):
        """Send report to all chat IDs"""
        message = self.format_message(results)

        success_count = 0
        fail_count = 0

        for chat_id in self.chat_ids:
            chat_id = chat_id.strip()
            if not chat_id:
                continue

            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=None  # Use plain text for better emoji support
                )
                logger.info(f"✅ Report sent to {chat_id}")
                success_count += 1

            except Exception as e:
                logger.info(f"❌ Failed to send to {chat_id}: {e}")
                fail_count += 1

        return success_count, fail_count

    def send_sync(self, results):
        """Synchronous wrapper for sending reports"""
        return asyncio.run(self.send_report(results))