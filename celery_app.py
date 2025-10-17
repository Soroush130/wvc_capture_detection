# celery_app.py
from celery import Celery
from celery.schedules import crontab
import os
from dotenv import load_dotenv

load_dotenv()

app = Celery(
    'camera_capture',
    broker=f'redis://{os.getenv("REDIS_HOST", "localhost")}:6379/0',
    backend=f'redis://{os.getenv("REDIS_HOST", "localhost")}:6379/0',
    include=['tasks']
)

CELERY_TIMEZONE = os.getenv('CELERY_TIMEZONE', 'America/New_York')

app.conf.update(
    # ==================== Serialization ====================
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',

    # ==================== Timezone ====================
    timezone=CELERY_TIMEZONE,
    enable_utc=False,

    # ==================== Task Limits ====================
    task_time_limit=1800,
    task_soft_time_limit=1680,

    # ==================== Memory & Performance ====================
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=10,
    worker_disable_rate_limits=True,

    # ==================== Task Reliability ====================
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,

    # ==================== Result Settings ====================
    result_expires=3600,
    result_persistent=False,

    # ==================== Broker Settings ====================
    broker_connection_retry_on_startup=True,

    # ==================== Queue Configuration ====================
    task_default_queue='capture',
    task_routes={
        'tasks.capture_single_camera': {'queue': 'capture'},
        'tasks.summarize_capture_results': {'queue': 'capture'},
        'tasks.schedule_camera_captures': {'queue': 'capture'},
        'tasks.detect_single_photo': {'queue': 'detection'},
        'tasks.schedule_photo_detection': {'queue': 'detection'},
        'tasks.run_scheduled_tests': {'queue': 'capture'},
    },
)

# ==================== BEAT SCHEDULE ====================
app.conf.beat_schedule = {
    'capture-every-5-minutes': {
        'task': 'tasks.schedule_camera_captures',
        'schedule': crontab(minute='*/5'),
        'options': {
            'expires': 300,  # 5 minutes
            'queue': 'capture',
        }
    },
    'detect-photos-every-3-minute': {
        'task': 'tasks.schedule_photo_detection',
        'schedule': crontab(minute='*/3'),
        'options': {
            'expires': 180,  # 3 minutes
            'queue': 'detection',
        }
    },
    'run-tests-daily-midnight': {
        'task': 'tasks.run_scheduled_tests',
        'schedule': crontab(minute=0, hour=0),
        'options': {
            'expires': 21600,
            'queue': 'capture',
        }
    },
}