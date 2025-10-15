# telegram_bot/telegram_reporter.py
import os
import asyncio
from datetime import datetime
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()


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
        lines.append("🤖 WVC System Test Report")
        lines.append("=" * 40)
        lines.append(f"📅 Date: {results.get('timestamp', 'N/A')}")
        lines.append(f"⏱️  Duration: {results.get('duration', 0):.2f}s")
        lines.append("")

        # Test Results
        lines.append("🧪 Test Results:")
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
            lines.append(f"   📹 Total Cameras:   {db_stats.get('total_cameras', 0):,}")

            # Show active/inactive cameras
            if 'active_cameras' in db_stats:
                lines.append(f"   🟢 Active Cameras:   {db_stats.get('active_cameras', 0):,}")
                lines.append(f"   🔴 Inactive Cameras: {db_stats.get('inactive_cameras', 0):,}")

            lines.append(f"   🔍 Total Objects:   {db_stats.get('total_objects', 0):,}")

            # Detection rate
            if db_stats.get('total_photos', 0) > 0:
                detection_rate = (db_stats.get('detected_photos', 0) / db_stats.get('total_photos', 0)) * 100
                lines.append(f"   📈 Detection Rate:  {detection_rate:.1f}%")

            lines.append("")

        # Today's Activity
        today = results.get('today_activity', {})
        if today:
            lines.append(f"📊 Today's Activity ({today.get('date', 'N/A')}):")
            lines.append(f"   📸 Photos:      {today.get('photos_today', 0):,}")
            lines.append(f"   🔍 Detections:  {today.get('detections_today', 0):,}")

            # Active states
            active_states = today.get('active_states', [])
            if active_states:
                lines.append(f"   🟢 Active States ({today.get('active_states_count', 0)}):")
                # Show first 5 states in Telegram
                for state in active_states[:5]:
                    lines.append(f"      • {state}")
                if len(active_states) > 5:
                    lines.append(f"      ... and {len(active_states) - 5} more")

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
                print(f"✅ Report sent to {chat_id}")
                success_count += 1

            except Exception as e:
                print(f"❌ Failed to send to {chat_id}: {e}")
                fail_count += 1

        return success_count, fail_count

    def send_sync(self, results):
        """Synchronous wrapper for sending reports"""
        return asyncio.run(self.send_report(results))