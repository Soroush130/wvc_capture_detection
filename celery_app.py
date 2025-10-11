# celery_app.py
from celery import Celery
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
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',

    timezone=CELERY_TIMEZONE,
    enable_utc=True,

    task_time_limit=600,
    task_soft_time_limit=570,
    task_acks_late=True,

    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,

    result_expires=3600,
)

app.conf.beat_schedule = {
    'capture-every-5-minutes': {
        'task': 'tasks.schedule_camera_captures',
        'schedule': 300.0,
    },
    'detect-every-2-minute': {
        'task': 'tasks.schedule_photo_detection',
        'schedule': 120.0,
    },
}