#!/bin/sh
set -eu

BASE_URL=${BASE_URL:-http://127.0.0.1:8088}
EXAMPLES=/usr/share/doc/wb-irrigationd/examples

echo "API службы: $BASE_URL"
curl --fail --show-error --silent "$BASE_URL/api/zones"
echo

echo "Настройка датчика дождя:"
echo "curl --fail -X PUT '$BASE_URL/api/settings/rain-sensor' -H 'Content-Type: application/json' --data-binary '@$EXAMPLES/rain-sensor.json'"

echo "Настройка насоса:"
echo "curl --fail -X PUT '$BASE_URL/api/settings/pump' -H 'Content-Type: application/json' --data-binary '@$EXAMPLES/pump.json'"

echo "Настройка расходомера:"
echo "curl --fail -X PUT '$BASE_URL/api/settings/flow-meter' -H 'Content-Type: application/json' --data-binary '@$EXAMPLES/flow-meter.json'"

echo "Создание зоны:"
echo "curl --fail -X POST '$BASE_URL/api/relays' -H 'Content-Type: application/json' --data-binary '@$EXAMPLES/create-relay.json'"
echo "curl --fail -X POST '$BASE_URL/api/zones' -H 'Content-Type: application/json' --data-binary '@$EXAMPLES/create-zone.json'"

echo "Создание расписания после проверки zone_id:"
echo "curl --fail -X POST '$BASE_URL/api/schedules' -H 'Content-Type: application/json' --data-binary '@$EXAMPLES/create-schedule.json'"
