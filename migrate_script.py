# migrate_script.py
import os
import redis
from datetime import datetime
from models.models import db, Photo, Camera, City, State
from logger_config import get_logger

logger = get_logger(__name__)


def migrate():
    r = redis.Redis(
        host=os.getenv('REDIS_HOST', 'localhost'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        db=int(os.getenv('REDIS_DB', 0)),
        decode_responses=False
    )

    if db.is_closed():
        db.connect()

    keys = r.keys(b'photos:*')
    migrated = 0

    for key in keys:
        try:
            key_str = key.decode('utf-8')
            value = r.get(key)
            s3_url = value.decode('utf-8')

            parts = key_str.split(':')
            state_slug, city_slug, camera_slug, filename = parts[1], parts[2], parts[3], parts[4]

            s3_key = f"photos/{state_slug}/{city_slug}/{camera_slug}/{filename}"

            if Photo.select().where(Photo.file == s3_key).exists():
                continue

            camera = Camera.select().join(City).join(State).where(
                Camera.slug == camera_slug,
                City.slug == city_slug,
                State.slug == state_slug
            ).first()

            if camera:
                Photo.create(
                    camera=camera,
                    state=camera.city.state,
                    city=camera.city,
                    road=camera.road,
                    timezone=camera.city.timezone,
                    file=s3_key,
                    captured_at=datetime.now(),
                    has_detected_objects=False,
                )
                migrated += 1
                print(f"✅ Migrated: {s3_key}")
        except Exception as e:
            print(f"❌ Error: {e}")
            continue

    print(f"\n✅ Total migrated: {migrated}")
    db.close()
    r.close()


if __name__ == '__main__':
    migrate()