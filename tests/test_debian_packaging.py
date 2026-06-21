import json
import os
from pathlib import Path


PACKAGING = Path(__file__).parents[1] / "packaging"


def test_packaging_is_separate_from_python_package() -> None:
    root = Path(__file__).parents[1]
    assert PACKAGING.is_dir()
    assert not (root / "irrigationd" / "packaging").exists()


def test_service_and_console_command_use_wb_name() -> None:
    root = Path(__file__).parents[1]
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert 'wb-irrigationd = "irrigationd.main:run"' in pyproject
    assert (PACKAGING / "wb-irrigationd.service").is_file()
    assert (PACKAGING / "bin" / "wb-irrigationd").is_file()


def test_conffiles_contains_only_absolute_nonempty_paths() -> None:
    lines = (PACKAGING / "deb" / "conffiles").read_text(encoding="utf-8").splitlines()
    assert lines
    assert all(line and line.startswith("/") for line in lines)
    assert lines == ["/etc/wb-irrigation/config.yaml"]


def test_debian_control_has_required_placeholders() -> None:
    control = (PACKAGING / "deb" / "control.in").read_text(encoding="utf-8")
    assert "Version: @VERSION@" in control
    assert "Architecture: @ARCH@" in control
    assert "Depends: python3 (>= 3.9), systemd, nginx" in control


def test_runtime_directories_and_launcher_are_packaged() -> None:
    tmpfiles = (PACKAGING / "wb-irrigationd.tmpfiles").read_text(encoding="utf-8")
    assert "d /var/lib/wb-irrigation" in tmpfiles
    assert "d /etc/wb-irrigation" in tmpfiles

    launcher = PACKAGING / "bin" / "wb-irrigationd"
    assert os.access(launcher, os.X_OK)
    service = (PACKAGING / "wb-irrigationd.service").read_text(encoding="utf-8")
    assert "ExecStart=/usr/bin/wb-irrigationd --config" in service


def test_installed_examples_are_valid() -> None:
    examples = PACKAGING / "examples"
    zone = json.loads((examples / "create-zone.json").read_text(encoding="utf-8"))
    relay = json.loads((examples / "create-relay.json").read_text(encoding="utf-8"))
    schedule = json.loads(
        (examples / "create-schedule.json").read_text(encoding="utf-8")
    )
    rain = json.loads((examples / "rain-sensor.json").read_text(encoding="utf-8"))
    pump = json.loads((examples / "pump.json").read_text(encoding="utf-8"))
    flow_meter = json.loads(
        (examples / "flow-meter.json").read_text(encoding="utf-8")
    )
    assert zone["relay_ids"] == [1]
    assert relay["relay_device_id"] and relay["relay_control_id"]
    assert schedule["zone_id"] == 1
    assert rain["active_value"] in {"0", "1"}
    assert pump["relay_device_id"] and pump["relay_control_id"]
    assert pump["start_delay_sec"] >= 0
    assert flow_meter["min_flow_l_min"] > 0
    assert os.access(examples / "api-examples.sh", os.X_OK)


def test_nginx_proxy_uses_wiren_board_include_directory() -> None:
    nginx = (PACKAGING / "nginx" / "watering.conf").read_text(encoding="utf-8")
    assert "location ^~ /watering/" in nginx
    assert "proxy_pass http://127.0.0.1:8088;" in nginx
    assert "auth_request /auth/check;" in nginx

    postinst = (PACKAGING / "deb" / "postinst").read_text(encoding="utf-8")
    assert "/etc/nginx/includes/default.wb.d/watering.conf" in postinst
    assert "nginx -t" in postinst
