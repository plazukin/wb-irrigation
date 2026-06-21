# Примеры

После установки проверьте конфигурацию и запустите службу:

```bash
sudo editor /etc/wb-irrigation/config.yaml
sudo systemctl enable --now wb-irrigationd
sudo systemctl status wb-irrigationd
journalctl -u wb-irrigationd -f
```

База `/var/lib/wb-irrigation/irrigation.db` создаётся при первом успешном запуске. Не изменяйте её вручную.

Готовые команды API:

```bash
/usr/share/doc/wb-irrigationd/examples/api-examples.sh
```

Сначала укажите устройство и канал в `create-relay.json` и создайте реле. Затем добавьте его идентификатор в `relay_ids` файла `create-zone.json`. Глобальный насос настраивается запросом из `pump.json`. Проверка MQTT-топиков не включает реле.
