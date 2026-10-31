#!/bin/sh
# SPDX-License-Identifier: CERN-OHL-W-2.0
# Toolchain for a fresh Ubuntu 24.04 container (Claude Code cloud sessions), as root:
#   sh tools/setup_env.sh
# KiCad 9 natively from the official PPA (kicad-cli, plus pcbnew for the system
# python3.12, wrapped as `kicad-py`), ngspice, Freerouting 1.9 and the project .venv.
# Afterwards: export KICAD9_SYMBOL_DIR=/usr/share/kicad/symbols; sh tools/check_all.sh
set -e
export DEBIAN_FRONTEND=noninteractive
cd "$(dirname "$0")/.."

if ! command -v kicad-cli >/dev/null; then
    apt-get update -q
    apt-get install -y -q software-properties-common gpg-agent
    # add-apt-repository needs apt_pkg, which only the distro python3.12 has
    /usr/bin/python3.12 /usr/bin/add-apt-repository -y ppa:kicad/kicad-9.0-releases
    apt-get update -q
    apt-get install -y -q --no-install-recommends kicad kicad-symbols kicad-footprints \
        kicad-packages3d ngspice poppler-utils librsvg2-bin xvfb default-jre-headless
fi

printf '#!/bin/sh\n# KiCad 9 python (pcbnew), native install\nexec /usr/bin/python3.12 "$@"\n' \
    > /usr/local/bin/kicad-py
chmod +x /usr/local/bin/kicad-py

mkdir -p /root/tools
[ -f /root/tools/fr19.jar ] || curl -sSL -o /root/tools/fr19.jar \
    https://github.com/freerouting/freerouting/releases/download/v1.9.0/freerouting-1.9.0.jar

if [ ! -x .venv/bin/python ]; then
    python3.11 -m venv .venv
    .venv/bin/pip install -q --upgrade pip
    # matplotlib pinned so regenerated plots match the committed SVGs
    .venv/bin/pip install -q "matplotlib==3.10.8" numpy scipy Pillow pytest ezdxf cadquery soundfile h5py
fi

# Freerouting 1.9 needs an X display
pgrep -x Xvfb >/dev/null || (Xvfb :99 >/dev/null 2>&1 &)

kicad-cli --version
kicad-py -c "import pcbnew; print('pcbnew', pcbnew.Version())"
.venv/bin/python -c "import matplotlib, cadquery; print('venv ok', matplotlib.__version__)"
echo "export KICAD9_SYMBOL_DIR=/usr/share/kicad/symbols DISPLAY=:99"
