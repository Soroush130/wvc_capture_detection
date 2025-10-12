# models/models.py
from peewee import *
import os
from dotenv import load_dotenv
from datetime import datetime
import pytz

load_dotenv()

db = PostgresqlDatabase(
    os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", 5432)),
    autorollback=True,
    autoconnect=False
)


class BaseModel(Model):
    class Meta:
        database = db


# ============= Base Models =============

class State(BaseModel):
    """
    Represents a state entity with name, slug, abbreviation, latitude, and longitude.
    """
    id = SmallIntegerField(primary_key=True)
    name = CharField(max_length=32, unique=True)
    slug = CharField(max_length=32, unique=True)
    abbreviation = CharField(max_length=2, unique=True)
    is_active = BooleanField(default=True)
    latitude = FloatField(default=0.0)
    longitude = FloatField(default=0.0)
    zoom = SmallIntegerField(default=8)

    class Meta:
        table_name = 'states_state'

    def __str__(self):
        return self.name


class Road(BaseModel):
    """
    Represents a road entity associated with a state.
    """
    id = AutoField(primary_key=True)
    name = CharField(max_length=128, unique=True)
    slug = CharField(max_length=128, unique=True)
    is_interstate = BooleanField(default=False)

    class Meta:
        table_name = 'states_road'

    def __str__(self):
        return self.name


class City(BaseModel):
    """
    Represents a city entity associated with a state.
    """
    id = SmallIntegerField(primary_key=True)
    name = CharField(max_length=32)
    slug = CharField(max_length=32)
    abbreviation = CharField(max_length=6)
    timezone = CharField(
        max_length=17,
        default='UTC',
        choices=[(tz, tz) for tz in filter(lambda t: t.startswith("US/"), pytz.all_timezones)]
    )
    state = ForeignKeyField(State, backref='cities', on_delete='CASCADE', column_name='state_id')
    latitude = FloatField(default=0.0)
    longitude = FloatField(default=0.0)
    zoom = SmallIntegerField(default=8)

    class Meta:
        table_name = 'states_city'
        indexes = (
            (('state', 'name'), True),
            (('state', 'slug'), True),
            (('state', 'abbreviation'), True),
        )

    def __str__(self):
        return self.name


class StateRoad(BaseModel):
    """
    Through table for State and Road many-to-many relationship.
    """
    id = AutoField(primary_key=True)
    state = ForeignKeyField(State, backref='state_roads', on_delete='CASCADE', column_name='state_id')
    road = ForeignKeyField(Road, backref='road_states', on_delete='CASCADE', column_name='road_id')

    class Meta:
        table_name = 'states_stateroad'
        indexes = (
            (('state', 'road'), True),
        )

    def __str__(self):
        return f"{self.state.name}, {self.road.name}"


class CityRoad(BaseModel):
    """
    Through table for City and Road many-to-many relationship.
    """
    id = AutoField(primary_key=True)
    city = ForeignKeyField(City, backref='city_roads', on_delete='CASCADE', column_name='city_id')
    road = ForeignKeyField(Road, backref='road_cities', on_delete='CASCADE', column_name='road_id')

    class Meta:
        table_name = 'states_cityroad'
        indexes = (
            (('city', 'road'), True),
        )

    def __str__(self):
        return f"{self.city.name}, {self.road.name}"


class Camera(BaseModel):
    """
    Represents a camera entity associated with a road.
    """
    id = AutoField(primary_key=True)
    name = CharField(max_length=128, unique=True)
    slug = CharField(max_length=128, unique=True)
    url = CharField(max_length=200)
    latitude = FloatField(default=0.0)
    longitude = FloatField(default=0.0)
    last_connection_status = BooleanField(default=False)
    road = ForeignKeyField(Road, backref='cameras', on_delete='CASCADE', column_name='road_id')
    city = ForeignKeyField(City, backref='cameras', on_delete='CASCADE', column_name='city_id')

    class Meta:
        table_name = 'cameras_camera'

    def __str__(self):
        return self.name


class Photo(BaseModel):
    """
    Represents a photo entity associated with a camera.
    """
    id = BigAutoField(primary_key=True)
    camera = ForeignKeyField(Camera, backref='photos', on_delete='CASCADE', column_name='camera_id')
    file = CharField(max_length=255, null=True)
    state = ForeignKeyField(State, backref='photos', on_delete='RESTRICT', column_name='state_id')
    city = ForeignKeyField(City, backref='photos', on_delete='RESTRICT', column_name='city_id')
    timezone = CharField(
        max_length=17,
        choices=[(tz, tz) for tz in filter(lambda t: t.startswith("US/"), pytz.all_timezones)]
    )
    road = ForeignKeyField(Road, backref='photos', on_delete='RESTRICT', column_name='road_id')
    system_confidence = FloatField(default=0.0)
    connection_start_date = DateTimeField(default=datetime.now)
    captured_at = DateTimeField(default=datetime.now)
    detected_at = DateTimeField(null=True)
    created_at = DateTimeField(default=datetime.now)
    deleted_at = DateTimeField(null=True)
    car_count_above_system_confidence = SmallIntegerField(default=0)
    car_count_below_system_confidence = SmallIntegerField(default=0)
    truck_count_above_system_confidence = SmallIntegerField(default=0)
    truck_count_below_system_confidence = SmallIntegerField(default=0)
    person_count_above_system_confidence = SmallIntegerField(default=0)
    person_count_below_system_confidence = SmallIntegerField(default=0)
    deer_count_above_system_confidence = SmallIntegerField(default=0)
    deer_count_below_system_confidence = SmallIntegerField(default=0)
    has_detected_objects = BooleanField(default=False)

    class Meta:
        table_name = 'cameras_photo'
        indexes = (
            (('created_at',), False),
        )

    def __str__(self):
        return self.file if self.file else ""


class DetectedObject(BaseModel):
    """
    Represents an object detected within a photo captured by a camera.
    """
    NAME_DEER = 'deer'
    NAME_CAR = 'car'
    NAME_TRUCK = 'truck'
    NAME_PERSON = 'person'

    NAME_CHOICES = (
        (NAME_DEER, 'Deer'),
        (NAME_CAR, 'Car'),
        (NAME_TRUCK, 'Truck'),
        (NAME_PERSON, 'Person'),
    )

    id = BigAutoField(primary_key=True)
    photo = ForeignKeyField(Photo, backref='detected_objects', on_delete='CASCADE', column_name='photo_id')
    name = CharField(max_length=10, choices=NAME_CHOICES)
    image = CharField(max_length=255)
    conf = FloatField()
    x = FloatField()
    y = FloatField()
    width = FloatField()
    height = FloatField()
    timezone = CharField(
        max_length=17,
        choices=[(tz, tz) for tz in filter(lambda t: t.startswith("US/"), pytz.all_timezones)]
    )
    captured_at = DateTimeField(default=datetime.now)
    created_at = DateTimeField(default=datetime.now)
    deleted_at = DateTimeField(null=True)

    class Meta:
        table_name = 'cameras_detectedobject'
        indexes = (
            (('created_at',), False),
            (('name', 'conf'), False),
        )

    def __str__(self):
        return f"{self.name.title()} {self.id}"
