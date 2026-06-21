import pytest

from irrigationd.mqtt.topics import (
    build_set_topic, build_state_topic, relay_topics, validate_concrete_topic,
)


def test_topic_builder() -> None:
    assert build_state_topic("wb-mr6c_42", "K1") == "/devices/wb-mr6c_42/controls/K1"
    assert build_set_topic("wb-mr6c_42", "K1") == "/devices/wb-mr6c_42/controls/K1/on"


def test_topic_builder_rejects_wildcards() -> None:
    with pytest.raises(ValueError):
        build_state_topic("device", "#")
    with pytest.raises(ValueError):
        validate_concrete_topic("/devices/+/controls/K1")


def test_advanced_topics_require_both_values() -> None:
    with pytest.raises(ValueError):
        relay_topics(None, None, "/devices/a/controls/K1", None)


def test_basic_relay_device_must_be_wiren_board() -> None:
    with pytest.raises(ValueError, match="wb-"):
        relay_topics("relay", "K1", None, None)
