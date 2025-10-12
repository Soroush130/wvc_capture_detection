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

server-logs:
	docker-compose -f docker-compose.yml -f docker-compose.gpu.yml logs -f celery-worker-detection-1

server-restart:
	docker-compose -f docker-compose.yml -f docker-compose.gpu.yml restart celery-worker-detection-1 celery-worker-detection-2

server-gpu-test:
	docker-compose exec celery-worker-detection-1 nvidia-smi

# ==================== BOTH ====================
clean:
	docker-compose down -v
	docker system prune -af