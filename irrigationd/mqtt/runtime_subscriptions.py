from __future__ import annotations

from dataclasses import dataclass

from irrigationd.storage.models import (
    FlowMeterModel, PumpModel, RainSensorModel, ZoneModel,
)

from .client import MqttClient


@dataclass
class RuntimeSubscriptionManager:
    client: MqttClient
    _topics: set[str]

    def __init__(self, client: MqttClient) -> None:
        self.client = client
        self._topics = set()

    async def reconcile(
        self, zones: list[ZoneModel], rain_sensor: RainSensorModel,
        pump: PumpModel, flow_meter: FlowMeterModel,
    ) -> None:
        desired = {
            relay.relay_state_topic
            for zone in zones
            for relay in zone.relays
        }
        if rain_sensor.enabled and rain_sensor.topic:
            desired.add(rain_sensor.topic)
        if pump.enabled and pump.relay_state_topic:
            desired.add(pump.relay_state_topic)
        if flow_meter.enabled and flow_meter.topic:
            desired.add(flow_meter.topic)
        for topic in desired - self._topics:
            await self.client.subscribe(topic)
        for topic in self._topics - desired:
            await self.client.unsubscribe(topic)
        self._topics = desired

    @property
    def topics(self) -> frozenset[str]:
        return frozenset(self._topics)
