# redis_stats_local.py
import redis
from collections import defaultdict

# Direct connection to localhost
r = redis.Redis(
    host='localhost',  # Changed to localhost
    port=6379,
    db=0,
    decode_responses=False
)

try:
    # Get all keys
    keys = r.keys('photos:*')

    print(f"📊 Redis Statistics")
    print("=" * 50)
    print(f"Total photos: {len(keys)}")

    # Grouping by state
    state_counts = defaultdict(int)
    city_counts = defaultdict(int)
    total_size = 0

    for key in keys:
        key_str = key.decode('utf-8')
        parts = key_str.split(':')

        if len(parts) >= 3:
            state = parts[1]
            city = parts[2]
            state_counts[state] += 1
            city_counts[f"{state}/{city}"] += 1

        size = len(r.get(key))
        total_size += size

    print(f"\nTotal size: {total_size / (1024 * 1024):.2f} MB")

    print(f"\n📍 Number of photos by State:")
    for state, count in sorted(state_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {state}: {count} photos")

    print(f"\n🏙️ Number of photos by City (top 10):")
    for city, count in sorted(city_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {city}: {count} photos")

    # Latest photos
    print(f"\n🕒 Last 10 photos:")
    sorted_keys = sorted(keys, key=lambda x: x.decode('utf-8'), reverse=True)[:10]
    for i, key in enumerate(sorted_keys):
        print(f"  {i + 1}. {key.decode('utf-8')}")

except redis.ConnectionError as e:
    print(f"❌ Error connecting to Redis: {e}")
    print("Make sure Redis is running on localhost:6379")
finally:
    r.close()