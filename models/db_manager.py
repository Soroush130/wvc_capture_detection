from peewee import *
import threading


class DatabaseManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(DatabaseManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_name, user, password, host='localhost', port=5432, engine='postgres'):
        if self._initialized:
            return

        if engine == 'postgres':
            self.db = PostgresqlDatabase(
                db_name,
                user=user,
                password=password,
                host=host,
                port=port
            )
        elif engine == 'mysql':
            self.db = MySQLDatabase(
                db_name,
                user=user,
                password=password,
                host=host,
                port=port
            )
        elif engine == 'sqlite':
            self.db = SqliteDatabase(db_name)
        else:
            raise ValueError("Unsupported engine!")

        self.db.connect()
        self._initialized = True

    def get_db(self):
        return self.db
