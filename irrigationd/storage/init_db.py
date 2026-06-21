from sqlalchemy import text
from sqlalchemy.engine import Engine

from .models import Base


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    additions = {
        "zones": {
            "area_m2": "FLOAT NOT NULL DEFAULT 1",
        },
        "schedules": {
            "watering_mode": "VARCHAR(10) NOT NULL DEFAULT 'timer'",
            "liters_per_m2": "FLOAT",
        },
        "watering_runs": {
            "target_liters": "FLOAT",
            "delivered_liters": "FLOAT",
        },
    }
    with engine.begin() as connection:
        for table, columns in additions.items():
            existing = {
                row[1]
                for row in connection.execute(text(f"PRAGMA table_info({table})"))
            }
            for column, definition in columns.items():
                if column not in existing:
                    connection.execute(text(
                        f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
                    ))
