#!/bin/sh
# SPDX-License-Identifier: CERN-OHL-W-2.0
# Toolchain for a fresh Ubuntu 24.04 machine (Claude Code cloud sessions, GitHub Actions):
#   sh tools/setup_env.sh                 (as root, or as a user with sudo)
# KiCad 9 natively from the official PPA (kicad-cli, plus pcbnew for the system
# python3.12, wrapped as `kicad-py`), ngspice, Freerouting 1.9 and the project .venv.
# Options (environment): SKIP_FREEROUTING=1 (CI), SKIP_3D=1 (no kicad-packages3d, several GB:
# only the fab STEP/render needs it), PYTHON=python3.11 (venv interpreter).
# Afterwards: export KICAD9_SYMBOL_DIR=/usr/share/kicad/symbols; sh tools/check_all.sh
set -e
export DEBIAN_FRONTEND=noninteractive
cd "$(dirname "$0")/.."
SUDO=; [ "$(id -u)" -eq 0 ] || SUDO=sudo

if ! command -v kicad-cli >/dev/null; then
    $SUDO apt-get update -q
    $SUDO apt-get install -y -q software-properties-common gpg-agent
    # add-apt-repository needs apt_pkg, which only the distro python3.12 has
    $SUDO /usr/bin/python3.12 /usr/bin/add-apt-repository -y ppa:kicad/kicad-9.0-releases
    $SUDO apt-get update -q
    PK3D=kicad-packages3d; [ -n "$SKIP_3D" ] && PK3D=
    $SUDO apt-get install -y -q --no-install-recommends kicad kicad-symbols kicad-footprints $PK3D
fi
# the rest separately, so a machine that already has KiCad still gets them
NEED=
for c in ngspice:ngspice pdftotext:poppler-utils rsvg-convert:librsvg2-bin Xvfb:xvfb java:default-jre-headless; do
    command -v "${c%%:*}" >/dev/null || NEED="$NEED ${c#*:}"
done
if [ -n "$NEED" ]; then
    $SUDO apt-get update -q
    $SUDO apt-get install -y -q --no-install-recommends $NEED
fi

printf '#!/bin/sh\n# KiCad 9 python (pcbnew), native install\nexec /usr/bin/python3.12 "$@"\n' \
    | $SUDO tee /usr/local/bin/kicad-py >/dev/null
$SUDO chmod +x /usr/local/bin/kicad-py

if [ -z "$SKIP_FREEROUTING" ]; then
    # tools/kicadgen/route.py looks for /root/tools/fr19.jar by default (--jar to change)
    $SUDO mkdir -p /root/tools
    [ -f /root/tools/fr19.jar ] || $SUDO curl -sSL -o /root/tools/fr19.jar \
        https://github.com/freerouting/freerouting/releases/download/v1.9.0/freerouting-1.9.0.jar
fi

PY=${PYTHON:-python3.11}
command -v "$PY" >/dev/null || PY=python3
if [ ! -x .venv/bin/python ]; then
    "$PY" -m venv .venv
    .venv/bin/pip install -q --upgrade pip
fi
# idempotent: pip skips what is already there (requirements.txt pins matplotlib)
.venv/bin/pip install -q -r requirements.txt

# Freerouting 1.9 needs an X display
if [ -z "$SKIP_FREEROUTING" ]; then
    pgrep -x Xvfb >/dev/null || (Xvfb :99 >/dev/null 2>&1 &)
fi

kicad-cli --version
kicad-py -c "import pcbnew; print('pcbnew', pcbnew.Version())"
.venv/bin/python -c "import matplotlib, cadquery; print('venv ok', matplotlib.__version__)"
echo "export KICAD9_SYMBOL_DIR=/usr/share/kicad/symbols DISPLAY=:99"
