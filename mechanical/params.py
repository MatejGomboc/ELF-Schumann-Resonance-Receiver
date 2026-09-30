# SPDX-License-Identifier: CERN-OHL-W-2.0
"""
ELARA mechanical parameters -- single source of truth.

Every dimension used by the CadQuery scripts in this directory lives here.
All lengths in millimetres.

Coordinate conventions
----------------------
* PCB data (hole lists, cut-outs, compartments) is given in **KiCad
  coordinates**: origin at the board's top-left corner, x to the right,
  y DOWNWARD, as read off the PCB editor.
* CadQuery models use a right-handed frame with z up.  The conversion is
  ``X = x_kicad``, ``Y = -y_kicad`` (see ``kicad_to_cq``).  The top surface
  of the amplifier PCB is at Z = 0; the top frame/walls grow in +Z, the
  PCB and the bottom tray lie in -Z.
"""

# ---------------------------------------------------------------------------
# Generic hardware
# ---------------------------------------------------------------------------
M3_CLEAR = 3.4          # clearance hole in aluminium parts (ISO 273 medium)
M3_PCB_HOLE = 3.2       # plated/unplated M3 hole in the PCBs (as drawn in KiCad)
M3_TAP_DRILL = 2.5
M3_THREAD = 3.0         # nominal major diameter (used for clash checks)
M4_CLEAR = 4.5
M4_TAP_DRILL = 3.3

# ISO 7380 button head M3 / M4 (exposed fasteners -- the brutalist detail)
BUTTON_M3 = dict(head_d=5.7, head_h=1.65, hex=2.0, d=3.0)
BUTTON_M4 = dict(head_d=7.6, head_h=2.2, hex=2.5, d=4.0)
# DIN 912 socket cap M3 (frame corner joints)
SOCKET_M3 = dict(head_d=5.5, head_h=3.0, hex=2.5, d=3.0)

# ---------------------------------------------------------------------------
# 1. ANTENNA-AMPLIFIER PCB
# ---------------------------------------------------------------------------
PCB_W = 200.0            # x extent
PCB_H = 100.0            # y extent
PCB_T = 1.6

GND_STRIP_W = 7.0        # exposed GND copper strip width (both sides)
INTERNAL_WALL_X = (45.0, 120.0)     # strip / wall centre lines

# M3 hole list, KiCad coordinates (x, y).  Agreed with the PCB drawing:
#   top & bottom rows (y = 3.5, 96.5):   x = 3.5, 45, 82.5, 120, 158, 196.5
#   left & right columns (x = 3.5, 196.5): y = 15, 50, 85
#   internal walls (x = 45, 120):          y = 15, 50, 85
# 12 + 6 + 6 = 24 holes.  The side columns deliberately use the same rows as
# the internal walls so that nothing lands in the AES3/BNC cut-outs.
_ROW_X = (3.5, 45.0, 82.5, 120.0, 158.0, 196.5)
_COL_Y = (15.0, 50.0, 85.0)
AMP_HOLES = (
    [(x, 3.5) for x in _ROW_X]
    + [(x, 96.5) for x in _ROW_X]
    + [(3.5, y) for y in _COL_Y]
    + [(196.5, y) for y in _COL_Y]
    + [(45.0, y) for y in _COL_Y]
    + [(120.0, y) for y in _COL_Y]
)

# Compartments (inner faces of the walls), KiCad coordinates
COMPARTMENTS = {
    "C1 INPUT":   dict(x0=7.0,   x1=41.5,  y0=7.0, y1=93.0),
    "C2 ANALOG":  dict(x0=48.5,  x1=116.5, y0=7.0, y1=93.0),
    "C3 DIGITAL": dict(x0=123.5, x1=193.0, y0=7.0, y1=93.0),
}

# ---------------------------------------------------------------------------
# Amplifier shield -- top frame (6 bars), lid, bottom tray
# ---------------------------------------------------------------------------
WALL_T = 7.0             # wall thickness = GND strip width (compartments above)
FRAME_H = 52.0           # walls above PCB top (tallest part: C202 100 uF film cap, 50 mm)
LID_T = 2.0
TRAY_DEPTH = 12.0        # clear depth under the PCB (THT leads)
TRAY_FLOOR_T = 2.0
TRAY_T = TRAY_DEPTH + TRAY_FLOOR_T   # tray milled from 15 mm plate, faced to 14
TRAY_POCKET_R = 3.0      # inside corner radius (6 mm end mill)

# Tapped holes in the wall bars (vertical, from both ends at the hole list)
FRAME_TAP_DEPTH_BOTTOM = 12.0   # tray screws
FRAME_TAP_DEPTH_TOP = 10.0      # lid screws

# Frame corner / tee joints: M3 socket caps through the long bars (along y)
# into tapped holes in the ends of the short/internal bars.
JOINT_Z = (20.0, 32.0)          # heights above PCB top, clear of the vertical taps
JOINT_TAP_DEPTH = 12.0
JOINT_SCREW_L = 16.0

# Screws
TRAY_SCREW_L = 25.0      # M3x25 button: 14 tray + 1.6 PCB + 9.4 engagement
LID_SCREW_L = 8.0        # M3x8 button: 2 lid + 6 engagement

# Lid mounting ears (the lid is the mounting face of the shield; it sits
# against the mounting plate, tray facing the enclosure door)
LID_EAR = 14.0           # ear length beyond the frame at each short end (x)
LID_EAR_HOLES_Y = (20.0, 80.0)   # KiCad y of the M4 mounting holes in the ears
LID_EAR_HOLE_X_OFF = 7.0          # from the frame end face, outward

# PTFE input feed-through in the tray floor (under compartment 1)
FEEDTHROUGH_XY = (24.0, 50.0)
FEEDTHROUGH_HOLE_D = 10.0
FEEDTHROUGH_FLANGE_D = 18.0
FEEDTHROUGH_FLANGE_T = 3.0
FEEDTHROUGH_SPIGOT_L = 8.0     # length inside the tray above the floor
FEEDTHROUGH_BORE = 1.2

# Connector cut-outs in the top frame (connectors on PCB top side, board edge)
# edge: "top" (y = 0), "bottom" (y = 100), "left" (x = 0), "right" (x = 200)
# pos: centre along the edge (x for top/bottom, y for left/right)
CUTOUTS = [
    dict(name="J_PWR  9 V Micro-Fit 3.0 R/A", edge="top", pos=185.0,
         shape="rect", w=12.0, h=12.0),          # w along edge, h from PCB top
    dict(name="J_AES3 3-pole 5.08 mm terminal block", edge="right", pos=30.0,
         shape="rect", w=18.0, h=12.0),
    dict(name="J_BNC  R/A BNC jack (S/PDIF coax)", edge="right", pos=70.0,
         shape="round", d=12.5, zc=7.5),          # zc = centre above PCB top
]

# Placeholder components (fit-check only)
FILM_CAP = dict(x=51.5, y=50.0, w=35.0, d=41.5, h=50.0)   # C202 WIMA MKS4 100 uF 63 V (41.5 x 35 x 50)
MICROFIT = dict(w=8.4, d=10.5, h=9.6)
TERMBLOCK = dict(w=15.2, d=16.0, h=10.0, overhang=4.0)
BNC = dict(body=14.5, body_h=14.5, barrel_d=9.6, barrel_l=13.0, zc=7.5)

# ---------------------------------------------------------------------------
# 2. PSU enclosure (generic bar-frame box; commercial alternative in README)
# ---------------------------------------------------------------------------
PSU_PCB_W = 150.0
PSU_PCB_H = 90.0
PSU_PCB_T = 1.6
PSU_PCB_HOLE_INSET = 4.0
PSU_CLEAR = 3.0           # PCB to inner wall, each side
PSU_BAR_T = 6.0           # 40 x 6 aluminium flat bar -- stock size, no milling
PSU_INNER_H = 40.0        # = bar height
PSU_INNER_W = PSU_PCB_W + 2 * PSU_CLEAR    # 156
PSU_INNER_D = PSU_PCB_H + 2 * PSU_CLEAR    # 96
PSU_BASE_T = 3.0          # base carries the PE stud -> 3 mm
PSU_LID_T = 2.0
PSU_EAR = 14.0            # base-plate ears at the short ends
PSU_STANDOFF_H = 10.0     # M3 hex standoffs under the PCB
PSU_JOINT_Z = (14.0, 26.0)
PSU_LIDSCREW_TAP = 8.0
PSU_GLAND_MAINS = dict(thread=16.0, hole=16.2, body_d=22.0, dome_l=18.0, nut_t=5.0, af=20.0)
PSU_GLAND_OUT = dict(thread=12.0, hole=12.2, body_d=17.0, dome_l=15.0, nut_t=4.0, af=15.0)
PSU_GLAND_Z = 26.0        # gland centre above the inner floor (locknut clears the PCB)
PSU_PE_STUD = dict(d=4.0, l=16.0, x=20.0, y=20.0)   # from inner corner, mains end

# ---------------------------------------------------------------------------
# 3. Air-gap plate capacitors (PLAN 3.0)
# ---------------------------------------------------------------------------
PLATE_SIZE = 64.0
PLATE_T = 1.6
PLATE_GAP = 0.5
PLATE_CU = 53.1           # copper square, centred -> 50 pF at 0.5 mm
PLATE_CU_T = 0.035
PLATE_HOLE_INSET = 5.0    # M3 nylon screws at (5, 5) from each corner
PLATE_CU_KEEPOUT_R = 4.8  # copper relief around the corner holes (see README)
PLATE_LAND_OD = 7.0       # isolated copper landing ring under each washer, so the
                          # 0.5 mm PTFE washer sets the copper-to-copper gap directly
PTFE_WASHER = dict(od=6.0, id=3.2, t=PLATE_GAP)
PTFE_CENTRE_SPACER_D = 6.0
PLATE_STANDOFF = dict(d=10.0, h=15.0, bore=3.2)    # PTFE rod standoffs
NYLON_SCREW_L = 25.0      # M3x25 nylon cheese head into tapped POM base
PLATECAP_SPACING = 16.0   # air gap between the two capacitors
PLATECAP_POST_MARGIN = 12.0
PLATECAP_BASE_T = 8.0     # POM-C base plate
PLATECAP_BASE_W = 184.0
PLATECAP_BASE_D = 92.0
PLATECAP_BASE_HOLE_INSET = 6.0   # M4 fixing holes
TERMINAL_POST = dict(d=10.0, h=24.0, pin_d=1.6, pin_h=8.0)   # PTFE post + turret
GND_POST = dict(d=8.0, h=12.0, x=0.0, y=-39.0)
RES_Z = dict(r1=27.0, r2=22.0)   # height of resistor axes above the base top
RESISTOR = dict(l=6.3, d=2.5, lead_d=0.6)          # 33 k axial thin-film

# ---------------------------------------------------------------------------
# 4. Outer IP65/66 enclosure (generic -- see README for commercial parts)
# ---------------------------------------------------------------------------
# Inner size of the generic box, chosen to fit Fibox ARCA 403015
# (inner 261 x 361.5 x 144) and Hammond PCJ14126 (inner 309 x 354 x 152).
BOX_INNER_W = 261.0       # X
BOX_INNER_H = 361.0       # Y (vertical when wall-mounted; antenna gland on top)
BOX_INNER_D = 144.0       # Z (out of the wall, towards the door)
BOX_WALL = 4.0
BOX_LID_T = 4.0
BOX_BOSS_D = 14.0
BOX_BOSS_H = 10.0

MOUNT_PLATE_W = 240.0
MOUNT_PLATE_H = 350.0
MOUNT_PLATE_T = 8.0       # PE-HD (or 3 mm aluminium, see README)
MOUNT_PLATE_HOLE_INSET = 10.0
MOUNT_SPACER_H = 5.0      # spacers between plate and each unit's ears

# Placement on the mounting plate (plate centre = origin, X right, Y up).
# Each entry is the centre of the unit's footprint in plate coordinates.
# The amplifier shield is mounted lid-down (lid = mounting face, rotated 180 deg
# about X), so KiCad y = 0 (power header edge) points DOWN towards the PSU and
# the tray with the PTFE feed-through faces the enclosure door.
LAYOUT = {
    "platecap": (0.0, 121.0),   # base centre
    "amp": (-6.0, 19.0),        # PCB centre; AES3/BNC on the right edge
    "psu": (0.0, -112.0),       # centre of the PSU inner cavity
}
MICROFIT_PLUG_CLEAR = 25.0      # mated plug + cable bend below the amp's y = 0 edge

# Cable glands in the outer box (M-thread, position along the wall in X)
# z = height of the gland axis above the box's inner floor
BOX_GLANDS = [
    dict(name="Antenna", wall="top", x=84.0, z=60.0, thread=12.0, af=15.0, dome=15.0, cable=4.0),
    dict(name="Mains", wall="bottom", x=-110.0, z=60.0, thread=20.0, af=24.0, dome=22.0, cable=9.0),
    dict(name="AES3", wall="bottom", x=112.0, z=60.0, thread=16.0, af=20.0, dome=18.0, cable=7.0),
]


# ---------------------------------------------------------------------------
# Helpers and consistency checks
# ---------------------------------------------------------------------------
def kicad_to_cq(x, y):
    """KiCad (x right, y down) -> CadQuery (X right, Y up)."""
    return (x, -y)


def wall_rects():
    """Top-frame bars as KiCad rectangles (x0, y0, x1, y1)."""
    t = WALL_T
    rects = {
        "long_top": (0.0, 0.0, PCB_W, t),
        "long_bottom": (0.0, PCB_H - t, PCB_W, PCB_H),
        "end_left": (0.0, t, t, PCB_H - t),
        "end_right": (PCB_W - t, t, PCB_W, PCB_H - t),
    }
    for i, xc in enumerate(INTERNAL_WALL_X):
        rects[f"internal_{i + 1}"] = (xc - t / 2, t, xc + t / 2, PCB_H - t)
    return rects


def cutout_rect(c):
    """Return the cut-out as (edge, lo, hi, z0, z1) along the edge."""
    if c["shape"] == "rect":
        return c["edge"], c["pos"] - c["w"] / 2, c["pos"] + c["w"] / 2, 0.0, c["h"]
    r = c["d"] / 2
    return c["edge"], c["pos"] - r, c["pos"] + r, c["zc"] - r, c["zc"] + r


def check(verbose=True):
    """Geometric sanity checks; returns a list of problems (empty = OK)."""
    problems = []
    rects = wall_rects()
    # 1. each tapped hole (major dia + 1 mm wall each side) inside one bar
    for (x, y) in AMP_HOLES:
        r = M3_THREAD / 2 + 1.0
        ok = any(x0 <= x - r and x + r <= x1 and y0 <= y - r and y + r <= y1
                 for (x0, y0, x1, y1) in rects.values())
        if not ok:
            problems.append(f"hole ({x}, {y}): thread + 1 mm not inside a single wall bar")
    # 2. holes vs connector cut-outs (bottom taps are FRAME_TAP_DEPTH_BOTTOM deep)
    for c in CUTOUTS:
        edge, lo, hi, z0, z1 = cutout_rect(c)
        for (x, y) in AMP_HOLES:
            along = x if edge in ("top", "bottom") else y
            near = {"top": y < WALL_T, "bottom": y > PCB_H - WALL_T,
                    "left": x < WALL_T, "right": x > PCB_W - WALL_T}[edge]
            if near and lo - 2.0 < along < hi + 2.0 and z0 < FRAME_TAP_DEPTH_BOTTOM:
                problems.append(f"hole ({x}, {y}) clashes with cut-out '{c['name']}'")
    # 3. compartments consistent with walls
    for name, c in COMPARTMENTS.items():
        for (x, y) in AMP_HOLES:
            if c["x0"] < x < c["x1"] and c["y0"] < y < c["y1"]:
                problems.append(f"hole ({x}, {y}) inside compartment {name}")
    # 4. feed-through under compartment 1
    fx, fy = FEEDTHROUGH_XY
    c1 = COMPARTMENTS["C1 INPUT"]
    if not (c1["x0"] + FEEDTHROUGH_FLANGE_D / 2 <= fx <= c1["x1"] - FEEDTHROUGH_FLANGE_D / 2):
        problems.append("feed-through flange does not fit under compartment 1")
    # 5. plate capacitor corner holes vs copper
    cu_edge = (PLATE_SIZE - PLATE_CU) / 2
    if PLATE_HOLE_INSET + M3_PCB_HOLE / 2 > cu_edge:
        problems.append(
            f"plate cap: corner hole edge ({PLATE_HOLE_INSET + M3_PCB_HOLE / 2:.2f} mm) "
            f"reaches into copper square (edge at {cu_edge:.2f} mm) -> copper corner "
            f"relief R{PLATE_CU_KEEPOUT_R} required (modelled)")
    if verbose:
        print(f"params.check(): {len(AMP_HOLES)} amplifier holes")
        for p in problems:
            print("  NOTE:", p)
        if not problems:
            print("  all checks passed")
    return problems


def plate_capacitance_pf():
    """Parallel-plate capacitance of one air-gap cap, including corner reliefs."""
    eps0 = 8.854e-12
    a = PLATE_CU ** 2
    # area lost to the four corner reliefs (circle R centred on the hole,
    # intersected with the copper square) -- numeric estimate
    cu0 = (PLATE_SIZE - PLATE_CU) / 2
    n = 400
    lost = 0.0
    h = (PLATE_CU_KEEPOUT_R * 2) / n
    for i in range(n):
        for j in range(n):
            px = PLATE_HOLE_INSET - PLATE_CU_KEEPOUT_R + (i + 0.5) * h
            py = PLATE_HOLE_INSET - PLATE_CU_KEEPOUT_R + (j + 0.5) * h
            if (px - PLATE_HOLE_INSET) ** 2 + (py - PLATE_HOLE_INSET) ** 2 <= PLATE_CU_KEEPOUT_R ** 2:
                if px >= cu0 and py >= cu0:
                    lost += h * h
    a_eff = a - 4 * lost   # the PTFE centre spacer is a dielectric; copper stays
    return eps0 * a_eff * 1e-6 / (PLATE_GAP * 1e-3) * 1e12, 4 * lost


if __name__ == "__main__":
    check()
    c, lost = plate_capacitance_pf()
    print(f"plate capacitor: {c:.2f} pF (corner reliefs remove {lost:.1f} mm^2)")
