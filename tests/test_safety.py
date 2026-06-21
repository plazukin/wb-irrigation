from types import SimpleNamespace

import pytest

from irrigationd.domain.safety import SafetyError, validate_start


def zone(**changes):
    values = {"id": 1, "enabled": True, "max_duration_sec": 100}
    values.update(changes)
    return SimpleNamespace(**values)


def test_safety_accepts_valid_start() -> None:
    assert validate_start(zone(), 30, ["0", "0"], [], False) == 30


@pytest.mark.parametrize("duration", [None, 0, 101])
def test_safety_rejects_invalid_duration(duration) -> None:
    with pytest.raises(SafetyError):
        validate_start(zone(), duration, ["0"], [], False)


def test_safety_rejects_parallel_run() -> None:
    with pytest.raises(SafetyError):
        validate_start(zone(), 30, ["0"], [SimpleNamespace(zone_id=2)], False)


def test_safety_rejects_any_active_relay() -> None:
    with pytest.raises(SafetyError, match="Одно из реле"):
        validate_start(zone(), 30, ["0", "1"], [], False)
