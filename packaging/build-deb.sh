#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=${PYTHON:-python3}
PACKAGE=wb-irrigationd
BUILD_ROOT=${BUILD_ROOT:-"$ROOT/.build/deb"}
OUTPUT_DIR=${OUTPUT_DIR:-"$ROOT/dist"}
PIP_ARGS=${PIP_ARGS:-}

command -v dpkg-deb >/dev/null 2>&1 || {
    echo "Ошибка: для сборки в Debian требуется dpkg-deb" >&2
    exit 1
}

"$PYTHON" -c 'import sys; assert sys.version_info >= (3, 9), "Требуется Python 3.9 или новее"'
VERSION=$(sed -n 's/^[[:space:]]*version[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' "$ROOT/pyproject.toml" | head -n 1)
[ -n "$VERSION" ] || {
    echo "Ошибка: не удалось прочитать версию из pyproject.toml" >&2
    exit 1
}
ARCH=${DEB_ARCH:-$(dpkg --print-architecture)}
STAGE="$BUILD_ROOT/${PACKAGE}_${VERSION}_${ARCH}"
VENV="$STAGE/opt/wb-irrigation/.venv"
OUTPUT="$OUTPUT_DIR/${PACKAGE}_${VERSION}_${ARCH}.deb"

dpkg --validate-version "$VERSION"

rm -rf "$STAGE"
mkdir -p "$VENV" "$STAGE/DEBIAN" "$STAGE/etc/wb-irrigation"
mkdir -p "$STAGE/lib/systemd/system" "$STAGE/usr/bin"
mkdir -p "$STAGE/usr/lib/tmpfiles.d" "$STAGE/var/lib/wb-irrigation"
mkdir -p "$STAGE/usr/share/wb-irrigationd/nginx"
mkdir -p "$STAGE/usr/share/doc/$PACKAGE/examples" "$OUTPUT_DIR"
chmod 0750 "$STAGE/var/lib/wb-irrigation"

"$PYTHON" -m venv --copies "$VENV"
# PIP_ARGS передаёт pip параметры --no-index и --find-links.
# shellcheck disable=SC2086
"$VENV/bin/python" -m pip install --disable-pip-version-check --no-compile --no-cache-dir $PIP_ARGS "$ROOT"

find "$VENV" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$VENV" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete

install -m 0644 "$ROOT/packaging/default-config.yaml" \
    "$STAGE/etc/wb-irrigation/config.yaml"
install -m 0644 "$ROOT/packaging/wb-irrigationd.service" \
    "$STAGE/lib/systemd/system/wb-irrigationd.service"
install -m 0755 "$ROOT/packaging/bin/wb-irrigationd" \
    "$STAGE/usr/bin/wb-irrigationd"
install -m 0644 "$ROOT/packaging/wb-irrigationd.tmpfiles" \
    "$STAGE/usr/lib/tmpfiles.d/wb-irrigationd.conf"
install -m 0644 "$ROOT/packaging/nginx/watering.conf" \
    "$STAGE/usr/share/wb-irrigationd/nginx/watering.conf"
install -m 0644 "$ROOT/README.md" "$STAGE/usr/share/doc/$PACKAGE/README.md"
install -m 0644 "$ROOT/packaging/deb/copyright" \
    "$STAGE/usr/share/doc/$PACKAGE/copyright"
install -m 0644 "$ROOT/packaging/default-config.yaml" \
    "$STAGE/usr/share/doc/$PACKAGE/examples/config.yaml"
install -m 0644 "$ROOT/packaging/examples/README.md" \
    "$STAGE/usr/share/doc/$PACKAGE/examples/README.md"
install -m 0644 "$ROOT/packaging/examples/create-zone.json" \
    "$STAGE/usr/share/doc/$PACKAGE/examples/create-zone.json"
install -m 0644 "$ROOT/packaging/examples/create-relay.json" \
    "$STAGE/usr/share/doc/$PACKAGE/examples/create-relay.json"
install -m 0644 "$ROOT/packaging/examples/create-schedule.json" \
    "$STAGE/usr/share/doc/$PACKAGE/examples/create-schedule.json"
install -m 0644 "$ROOT/packaging/examples/rain-sensor.json" \
    "$STAGE/usr/share/doc/$PACKAGE/examples/rain-sensor.json"
install -m 0644 "$ROOT/packaging/examples/pump.json" \
    "$STAGE/usr/share/doc/$PACKAGE/examples/pump.json"
install -m 0644 "$ROOT/packaging/examples/flow-meter.json" \
    "$STAGE/usr/share/doc/$PACKAGE/examples/flow-meter.json"
install -m 0755 "$ROOT/packaging/examples/api-examples.sh" \
    "$STAGE/usr/share/doc/$PACKAGE/examples/api-examples.sh"

install -m 0644 "$ROOT/packaging/deb/control.in" "$STAGE/DEBIAN/control"
sed -i "s/@VERSION@/$VERSION/g; s/@ARCH@/$ARCH/g" "$STAGE/DEBIAN/control"
INSTALLED_SIZE=$(du -sk "$STAGE" | awk '{print $1}')
printf 'Installed-Size: %s\n' "$INSTALLED_SIZE" >> "$STAGE/DEBIAN/control"

awk '
    NF {
        if (substr($0, 1, 1) != "/") {
            print "Ошибка: путь conffile должен быть абсолютным: " $0 > "/dev/stderr"
            exit 1
        }
        print
    }
' "$ROOT/packaging/deb/conffiles" > "$STAGE/DEBIAN/conffiles"
[ -s "$STAGE/DEBIAN/conffiles" ] || {
    echo "Ошибка: DEBIAN/conffiles пуст" >&2
    exit 1
}
chmod 0644 "$STAGE/DEBIAN/conffiles"
for script in postinst prerm postrm; do
    install -m 0755 "$ROOT/packaging/deb/$script" "$STAGE/DEBIAN/$script"
done

dpkg-deb --build --root-owner-group "$STAGE" "$OUTPUT"
echo "Пакет собран: $OUTPUT"
