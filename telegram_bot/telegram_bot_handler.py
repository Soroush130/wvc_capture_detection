# telegram_bot/telegram_bot_handler.py
import os
import asyncio
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# Import functions from existing modules
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from run_tests import get_system_info, get_database_stats, get_today_activity

load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class WVCTelegramBot:
    """WVC Telegram Bot for on-demand reports"""

    def __init__(self):
        self.token = os.getenv('TELEGRAM_API_KEY')
        if not self.token:
            raise ValueError("TELEGRAM_API_KEY not found in environment")

        # Create application
        self.app = Application.builder().token(self.token).build()

        # Register handlers
        self.register_handlers()

    def register_handlers(self):
        """Register all command and message handlers"""
        # Command handlers
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("report", self.cmd_report))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("disk", self.cmd_disk))
        self.app.add_handler(CommandHandler("tests", self.cmd_run_tests))

        # Message handler for text (e.g., "Reports")
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handle_message
        ))

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /start command"""
        welcome_text = (
            "🤖 *WVC System Bot*\n\n"
            "Hello! I'm the WVC System monitoring bot.\n\n"
            "Available commands:\n"
            "/report - Get full system report\n"
            "/status - System and database status\n"
            "/disk - Check disk space\n"
            "/tests - Run tests\n"
            "/help - Help guide\n\n"
            "Or you can send text 'Reports' to get full report."
        )
        await update.message.reply_text(welcome_text, parse_mode='Markdown')

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /help command"""
        help_text = (
            "📚 *Command Guide:*\n\n"
            "*Main Commands:*\n"
            "• /report - Full system report\n"
            "• /status - System status\n"
            "• /disk - Disk space\n"
            "• /tests - Run tests\n\n"
            "*Text Messages:*\n"
            "• Reports - Full report\n"
            "• Status - Quick status\n"
            "• Disk - Disk usage\n\n"
            "Use /report command to get full system report."
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def cmd_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /report command - Send full report"""
        await update.message.reply_text("⏳ Preparing report...")

        try:
            # Collect data
            system_info = get_system_info()
            db_stats = get_database_stats()
            today_activity = get_today_activity()

            # Format report
            report = self.format_full_report(system_info, db_stats, today_activity)

            await update.message.reply_text(report, parse_mode=None)
            logger.info(f"Report sent to {update.effective_user.id}")

        except Exception as e:
            error_msg = f"❌ Error generating report:\n{str(e)}"
            await update.message.reply_text(error_msg)
            logger.error(f"Error generating report: {e}")

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /status command - Quick system status"""
        await update.message.reply_text("⏳ Checking status...")

        try:
            db_stats = get_database_stats()
            today_activity = get_today_activity()

            status = self.format_status_report(db_stats, today_activity)

            await update.message.reply_text(status, parse_mode=None)
            logger.info(f"Status sent to {update.effective_user.id}")

        except Exception as e:
            error_msg = f"❌ Error checking status:\n{str(e)}"
            await update.message.reply_text(error_msg)
            logger.error(f"Error getting status: {e}")

    async def cmd_disk(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /disk command - Disk usage"""
        await update.message.reply_text("⏳ Checking disk space...")

        try:
            import subprocess

            # Get disk usage
            df_output = subprocess.run(
                ['df', '-h', '/'],
                capture_output=True,
                text=True
            ).stdout

            # Get docker usage
            docker_output = subprocess.run(
                ['docker', 'system', 'df'],
                capture_output=True,
                text=True
            ).stdout

            disk_report = (
                    "💾 *Disk Usage Report*\n"
                    "=" * 40 + "\n\n"
                               "📊 System Disk:\n"
                               f"```\n{df_output}\n```\n"
                               "🐳 Docker Usage:\n"
                               f"```\n{docker_output}\n```"
            )

            await update.message.reply_text(disk_report, parse_mode='Markdown')
            logger.info(f"Disk report sent to {update.effective_user.id}")

        except Exception as e:
            error_msg = f"❌ Error checking disk:\n{str(e)}"
            await update.message.reply_text(error_msg)
            logger.error(f"Error checking disk: {e}")

    async def cmd_run_tests(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /tests command - Run tests and send report"""
        await update.message.reply_text(
            "🧪 Starting tests...\n"
            "This may take a few minutes."
        )

        try:
            import subprocess

            # Run tests
            result = subprocess.run(
                ['python', 'run_tests.py'],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                timeout=600
            )

            if result.returncode == 0:
                await update.message.reply_text("✅ Tests completed successfully!")
                # Send full report
                await self.cmd_report(update, context)
            else:
                await update.message.reply_text(
                    f"⚠️ Tests failed with errors.\n"
                    f"Return code: {result.returncode}"
                )

            logger.info(f"Tests executed by {update.effective_user.id}")

        except subprocess.TimeoutExpired:
            await update.message.reply_text("❌ Test execution timed out!")
            logger.error("Test execution timeout")
        except Exception as e:
            error_msg = f"❌ Error running tests:\n{str(e)}"
            await update.message.reply_text(error_msg)
            logger.error(f"Error running tests: {e}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages (non-commands)"""
        text = update.message.text.strip().lower()

        # Map text to commands
        if text in ['report', 'reports']:
            await self.cmd_report(update, context)
        elif text in ['status']:
            await self.cmd_status(update, context)
        elif text in ['disk']:
            await self.cmd_disk(update, context)
        elif text in ['help']:
            await self.cmd_help(update, context)
        else:
            # Unknown message
            await update.message.reply_text(
                "❓ Command not recognized.\n"
                "Use /help to see available commands."
            )

    def format_full_report(self, system_info, db_stats, today_activity):
        """Format full system report"""
        lines = []

        lines.append("====>>>> WVC System Report")
        lines.append("=" * 40)
        lines.append(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # System Status
        if system_info:
            lines.append("💻 System Status:")
            lines.append(f"   🔲 CPU:    {system_info.get('cpu_percent', 0):.1f}%")
            lines.append(f"   🧠 Memory: {system_info.get('memory_percent', 0):.1f}%")
            lines.append(f"   💾 Disk:   {system_info.get('disk_percent', 0):.1f}%")

            if system_info.get('gpu_available'):
                gpu_used = system_info.get('gpu_memory_used_gb', 0)
                gpu_total = system_info.get('gpu_memory_total_gb', 0)
                gpu_percent = (gpu_used / gpu_total * 100) if gpu_total > 0 else 0
                lines.append(f"    GPU:    {gpu_percent:.1f}% ({gpu_used:.1f}/{gpu_total:.1f} GB)")
            else:
                lines.append("    GPU:    Not available")

            lines.append("")

        # Database Stats
        if db_stats and 'error' not in db_stats:
            lines.append("🗄️  Database Stats:")
            lines.append(f"   📷 Total Photos:     {db_stats.get('total_photos', 0):,}")
            lines.append(f"   📸 With Objects:     {db_stats.get('photos_with_detections', 0):,}")
            lines.append(f"   📹 Total Cameras:    {db_stats.get('total_cameras', 0):,}")

            if 'active_cameras' in db_stats:
                lines.append(f"   🟢 Active Cameras:   {db_stats.get('active_cameras', 0):,}")
                lines.append(f"   🔴 Inactive Cameras: {db_stats.get('inactive_cameras', 0):,}")

            lines.append(f"   🔍 Total Detections: {db_stats.get('total_detections', 0):,}")
            lines.append(f"   📈 Detection Rate:   {db_stats.get('detection_rate', 0):.1f}%")
            lines.append("")

        # Today's Activity
        if today_activity:
            lines.append(f"📊 Today's Activity ({today_activity.get('date', 'N/A')}):")
            lines.append(f"   📸 Photos:      {today_activity.get('photos_today', 0):,}")
            lines.append(f"   🔍 Detections:  {today_activity.get('detections_today', 0):,}")

            active_states = today_activity.get('active_states', [])
            if active_states:
                lines.append(f"   🟢 Active States ({today_activity.get('active_states_count', 0)}):")
                for state in active_states[:5]:
                    lines.append(f"      • {state}")
                if len(active_states) > 5:
                    lines.append(f"      ... and {len(active_states) - 5} more")

            lines.append("")

        lines.append("=" * 40)

        return "\n".join(lines)

    def format_status_report(self, db_stats, today_activity):
        """Format quick status report"""
        lines = []

        lines.append("⚡ Quick Status")
        lines.append("=" * 40)

        if db_stats and 'error' not in db_stats:
            lines.append(f"📷 Photos: {db_stats.get('total_photos', 0):,}")
            lines.append(f"🔍 Detections: {db_stats.get('total_detections', 0):,}")
            lines.append(f"📹 Cameras: {db_stats.get('active_cameras', 0):,} active")

        if today_activity:
            lines.append(f"\n📊 Today ({today_activity.get('date', 'N/A')}):")
            lines.append(f"   📸 {today_activity.get('photos_today', 0):,} photos")
            lines.append(f"   🔍 {today_activity.get('detections_today', 0):,} detections")

        lines.append("=" * 40)

        return "\n".join(lines)

    def run(self):
        """Start the bot"""
        logger.info("=====>>>>> Starting WVC Telegram Bot...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """Main entry point"""
    try:
        bot = WVCTelegramBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot error: {e}")
        raise


if __name__ == "__main__":
    main()