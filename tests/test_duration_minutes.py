from irrigationd.domain.duration import minutes_to_seconds, seconds_to_minutes
from irrigationd.config import Config, StorageConfig
from irrigationd.web.app import create_app


def test_duration_conversion_supports_fractional_minutes() -> None:
    assert minutes_to_seconds(1.5) == 90
    assert minutes_to_seconds(0, allow_zero=True) == 0
    assert seconds_to_minutes(90) == 1.5


def test_public_api_uses_minutes(tmp_path) -> None:
    app = create_app(Config(storage=StorageConfig(path=str(tmp_path / "db.sqlite"))))
    schemas = app.openapi()["components"]["schemas"]

    assert "duration_min" in schemas["StartRequest"]["properties"]
    assert "duration_sec" not in schemas["StartRequest"]["properties"]
    assert "max_duration_min" in schemas["ZoneRequest"]["properties"]
    assert "max_duration_sec" not in schemas["ZoneRequest"]["properties"]
    assert "relay_ids" in schemas["ZoneRequest"]["properties"]
    assert "duration_min" in schemas["ScheduleRequest"]["properties"]
