#!/bin/sh
# SPDX-License-Identifier: CERN-OHL-W-2.0
# Place, route and finish the PSU board in one go (from the repository root):
#   sh tools/route_psu.sh
# The charger/receiver barrier comes from CHARGER_NETS / RECEIVER_NETS in layout.py and
# goes to Freerouting as class-to-class clearances (route.py --barrier), so the router
# keeps the 1 mm KiCad custom rule too.
set -e
export DISPLAY=${DISPLAY:-:99}
pgrep -x Xvfb >/dev/null || (Xvfb :99 >/dev/null 2>&1 &)
PY=.venv/bin/python
nets() { $PY -c "import ast,re;s=open('PCB/acdc_converter/layout.py').read();print(','.join(ast.literal_eval(re.search(r'$1 = (\(.*?\))',s,re.S).group(1))))"; }
kicad-py PCB/acdc_converter/layout.py place
cd PCB/acdc_converter
../../$PY ../../tools/kicadgen/route.py acdc_converter.dsn acdc_converter.ses \
    --cls "mains:1000:2000:AC_L,AC_N,L_IN,PE" \
    --cls "contact:600:1000:CHG_A,CHG_B,LOAD_A,LOAD_B,LA_D,LB_D" \
    --cls "current:600:300:+15V_C,CC_SET,CC_OUT,CHG,CHG_D,A_P,A_N,B_P,B_N,A_1,A_2,A_3,B_1,B_2,B_3,+9V_OUT,OUT_N,GND_C,OR_P,LIM_S" \
    --cls "mid:400:200:LOAD_P,VREG" \
    --barrier "1050:$(cd ../.. && nets RECEIVER_NETS):$(cd ../.. && nets CHARGER_NETS)" --passes 60 \
    > route.log 2>&1 || { tail -20 route.log; echo "FAIL: Freerouting"; exit 1; }   # no pipe: keep route.py's status
tail -2 route.log
cd ../..
kicad-py PCB/acdc_converter/layout.py finish > /tmp/psu_finish.log 2>&1 || { tail -20 /tmp/psu_finish.log; exit 1; }
tail -1 /tmp/psu_finish.log
