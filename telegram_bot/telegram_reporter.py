# telegram_bot/telegram_reporter.py
import os
import asyncio
from datetime import datetime
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()


class TelegramReporter:
    """Send test results to Telegram"""

    def __init__(self):
        self.token = os.getenv('TELEGRAM_API_KEY')
        self.chat_ids = os.getenv('TELEGRAM_CHAT_IDS', '').split(',')

        if not self.token:
            raise ValueError("TELEGRAM_API_KEY not found in environment")

        if not self.chat_ids or self.chat_ids == ['']:
            raise ValueError("TELEGRAM_CHAT_IDS not found in environment")

        self.bot = Bot(token=self.token)

    def format_message(self, results):
        """Format test results as simple text with error details"""
        emoji_status = "✅" if results['success'] else "❌"

        lines = []
        lines.append(f"{emoji_status} WVC Test Report")
        lines.append("=" * 30)
        lines.append(f"Date: {results['timestamp']}")
        lines.append(f"Duration: {results['duration']:.2f}s")
        lines.append("")
        lines.append("Test Results:")
        lines.append(f"  Passed: {results['passed']}")
        lines.append(f"  Failed: {results['failed']}")
        lines.append(f"  Skipped: {results['skipped']}")
        lines.append(f"  Total: {results['total']}")
        lines.append("")
        lines.append(f"Coverage: {results['coverage']}%")
        lines.append("")

        status_emoji = "🎉" if results['success'] else "💥"
        lines.append(f"Status: {status_emoji} {results['status']}")
        lines.append("=" * 30)

        # Failed tests with details
        if results['failed'] > 0:
            lines.append("")
            lines.append("Failed Tests:")

            error_details = results.get('error_details', [])
            errors = results.get('errors', [])

            # Show up to 3 failed tests with details
            for i, error in enumerate(errors[:3], 1):
                # Get test name (short version)
                test_name = error.split("::")[-1]
                if len(test_name) > 40:
                    test_name = test_name[:37] + "..."

                lines.append(f"\n{i}. {test_name}")

                # Add error message if available
                if i - 1 < len(error_details):
                    error_msg = error_details[i - 1].get('message', '')
                    if error_msg:
                        # Clean and truncate error message
                        error_msg = error_msg.strip()
                        if len(error_msg) > 150:
                            error_msg = error_msg[:147] + "..."
                        lines.append(f"   Error: {error_msg}")

            # Show count of remaining failures
            if len(errors) > 3:
                lines.append(f"\n...and {len(errors) - 3} more failures")

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
                    text=message
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