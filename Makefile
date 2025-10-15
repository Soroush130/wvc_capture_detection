# Makefile
.PHONY: help local-build local-up local-down local-logs server-build server-up server-down server-logs

help:
	@echo "Available commands:"
	@echo "  make local-build    - Build for local (CPU)"
	@echo "  make local-up       - Start local services"
	@echo "  make local-down     - Stop local services"
	@echo "  make local-logs     - View local logs"
	@echo ""
	@echo "  make server-build   - Build for server (GPU)"
	@echo "  make server-up      - Start server services"
	@echo "  make server-down    - Stop server services"
	@echo "  make server-logs    - View server logs"
	@echo ""
	@echo "  make bot-logs       - View telegram bot logs"
	@echo "  make bot-restart    - Restart telegram bot"

# ==================== LOCAL (CPU) ====================
local-build:
	docker-compose build --no-cache

local-up:
	docker-compose up -d

local-down:
	docker-compose down

local-logs:
	docker-compose logs -f celery-worker-detection-1

local-restart:
	docker-compose restart celery-worker-detection-1 celery-worker-detection-2

# ==================== SERVER (GPU) ====================
server-build:
	docker-compose -f docker-compose.yml -f docker-compose.gpu.yml build --no-cache

server-up:
	docker-compose -f docker-compose.yml -f docker-compose.gpu.yml up -d

server-down:
	docker-compose -f docker-compose.yml -f docker-compose.gpu.yml down

server-logs-capture:
	docker-compose -f docker-compose.yml -f docker-compose.gpu.yml logs -f celery-worker-capture-1 celery-worker-capture-2

server-logs-detection:
	docker-compose -f docker-compose.yml -f docker-compose.gpu.yml logs -f celery-worker-detection-1 celery-worker-detection-2

server-restart-capture:
	docker-compose -f docker-compose.yml -f docker-compose.gpu.yml restart celery-worker-capture-1 celery-worker-capture-2

server-restart-detection:
	docker-compose -f docker-compose.yml -f docker-compose.gpu.yml restart celery-worker-detection-1 celery-worker-detection-2

server-gpu-test:
	docker-compose exec celery-worker-detection-1 nvidia-smi

# ==================== TELEGRAM BOT ====================
bot-logs:
	docker-compose logs -f telegram-bot

bot-restart:
	docker-compose restart telegram-bot

bot-stop:
	docker-compose stop telegram-bot

bot-start:
	docker-compose start telegram-bot

bot-rebuild:
	docker-compose build --no-cache telegram-bot
	docker-compose up -d telegram-bot

# ==================== BOTH ====================
clean:
	docker-compose down -v
	docker system prune -af

# ==================== USEFUL SHORTCUTS ====================
logs-all:
	docker-compose logs -f

ps:
	docker-compose ps

restart-all:
	docker-compose restart