from types import SimpleNamespace

import pytest

from irrigationd.domain.zone import ZoneInput
from irrigationd.domain.zone_validation import (
    ZoneValidationError, normalize_zone, validate_zone_relays,
)
from irrigationd.mqtt.probe import RelayValidationResult


def test_zone_creation_normalizes_basic_topics() -> None:
    values = normalize_zone(ZoneInput(name="Lawn", relay_ids=[1, 2]))
    assert values["relay_ids"] == [1, 2]


def test_zone_creation_requires_positive_duration() -> None:
    with pytest.raises(ZoneValidationError):
        normalize_zone(ZoneInput(name="Lawn", relay_ids=[1], max_duration_sec=0))


class RejectingProbe:
    async def validate_relay(self, state_topic: str, set_topic: str):
        return RelayValidationResult(False, "relay unavailable")


@pytest.mark.asyncio
async def test_zone_creation_rejects_failed_mqtt_validation() -> None:
    relays = [SimpleNamespace(
        relay_state_topic="/relay", relay_set_topic="/relay/on"
    )]
    with pytest.raises(ZoneValidationError, match="relay unavailable"):
        await validate_zone_relays(relays, RejectingProbe())
