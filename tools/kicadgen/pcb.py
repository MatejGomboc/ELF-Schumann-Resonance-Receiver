"""Board-building helpers on top of KiCad's pcbnew Python API.

Runs inside KiCad's Python (e.g. the kicad/kicad:9.0-full image), reads the
design_netlist.json written by a design.py, and places footprints with the
schematic links (symbol paths) KiCad needs for "Update PCB from schematic".
Coordinates passed to these helpers are board millimetres (origin at the
board's top-left corner, y down); ORIGIN shifts them onto the drawing sheet.
"""

import json
import math
import os

import pcbnew

from kicadgen import fabrules
from kicadgen.models import MODEL_DIR, MODELS, MODELS_BY_MPN, STOCK_MODELS

FP_ROOT = '/usr/share/kicad/footprints'
ORIGIN = (50.0, 50.0)


def mm(v):
    return pcbnew.FromMM(v)


def pt(x, y):
    return pcbnew.VECTOR2I(mm(ORIGIN[0] + x), mm(ORIGIN[1] + y))


def near(pref, region, step=1.0):
    """Candidate text anchors in a region, nearest to the preferred spot first."""
    x0, y0, x1, y1 = region
    pts = [(x0 + i * step, y0 + j * step) for i in range(int((x1 - x0) / step) + 1)
           for j in range(int((y1 - y0) / step) + 1)]
    return sorted(pts, key=lambda p: (p[0] - pref[0]) ** 2 + (p[1] - pref[1]) ** 2)


def _box(item, grow=0):
    """Bounding box (IU); for texts the printed strokes, not KiCad's text cell, which
    adds about half a character of empty space each way."""
    bb = item.GetBoundingBox()
    if hasattr(item, 'GetEffectiveTextShape'):
        try:
            bb = item.GetEffectiveTextShape(True).BBox()
        except Exception:                     # empty text
            pass
    return (bb.GetX() - grow, bb.GetY() - grow, bb.GetRight() + grow, bb.GetBottom() + grow)


def _hit(a, b, m=0):
    return a[0] - m < b[2] and b[0] - m < a[2] and a[1] - m < b[3] and b[1] - m < a[3]


def _outline_segments(gi, n=72):
    """A silk shape as straight segments (IU), or None for shapes left alone."""
    st = gi.GetShape()
    if st == pcbnew.SHAPE_T_SEGMENT:
        s, e = gi.GetStart(), gi.GetEnd()
        return [((s.x, s.y), (e.x, e.y))]
    if st == pcbnew.SHAPE_T_RECT:
        s, e = gi.GetStart(), gi.GetEnd()
        c = [(s.x, s.y), (e.x, s.y), (e.x, e.y), (s.x, e.y)]
        return list(zip(c, c[1:] + c[:1]))
    if st == pcbnew.SHAPE_T_CIRCLE:
        c, r = gi.GetCenter(), gi.GetRadius()
        p = [(c.x + r * math.cos(2 * math.pi * i / n), c.y + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
        return list(zip(p, p[1:] + p[:1]))
    if st == pcbnew.SHAPE_T_POLY:
        ol = gi.GetPolyShape().Outline(0)
        p = [(ol.CPoint(i).x, ol.CPoint(i).y) for i in range(ol.PointCount())]
        return list(zip(p, p[1:] + p[:1]))
    if st == pcbnew.SHAPE_T_ARC:
        c, s, e = gi.GetCenter(), gi.GetStart(), gi.GetEnd()
        r = math.hypot(s.x - c.x, s.y - c.y)
        a0 = math.atan2(s.y - c.y, s.x - c.x)
        sweep = math.radians(gi.GetArcAngle().AsDegrees())
        end = lambda sw: (c.x + r * math.cos(a0 + sw), c.y + r * math.sin(a0 + sw))
        if math.hypot(end(sweep)[0] - e.x, end(sweep)[1] - e.y) > math.hypot(end(-sweep)[0] - e.x, end(-sweep)[1] - e.y):
            sweep = -sweep                   # KiCad's sign convention: follow the end point
        k = max(2, int(abs(sweep) / (2 * math.pi) * n) + 1)
        p = [end(sweep * i / k) for i in range(k + 1)]
        return list(zip(p, p[1:]))
    return None


def _seg_box(seg, box, m):
    """Does a segment come within m of a box?"""
    return len(_clip_outside(seg, box, m)) != 1 or _clip_outside(seg, box, m)[0] != seg


def _clip_outside(seg, box, m):
    """Parts of a segment outside an axis-aligned box grown by m (Liang-Barsky)."""
    (x0, y0), (x1, y1) = seg
    bx0, by0, bx1, by1 = box[0] - m, box[1] - m, box[2] + m, box[3] + m
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - bx0), (dx, bx1 - x0), (-dy, y0 - by0), (dy, by1 - y0)):
        if p == 0:
            if q < 0:
                return [seg]          # parallel and outside
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
    if t0 >= t1:
        return [seg]                  # no overlap
    at = lambda t: (x0 + t * dx, y0 + t * dy)
    out = []
    if t0 > 0:
        out.append((seg[0], at(t0)))
    if t1 < 1:
        out.append((at(t1), seg[1]))
    return [s for s in out if math.hypot(s[1][0] - s[0][0], s[1][1] - s[0][1]) > mm(0.15)]


class Board:
    def __init__(self, design_json, project_lib_dirs, pcb_path, layers=4):
        if design_json is None:
            self.design = {'components': []}
        else:
            with open(design_json, encoding='utf-8') as f:
                self.design = json.load(f)
        self.lib_dirs = project_lib_dirs
        self.path = pcb_path
        if os.path.exists(pcb_path):
            os.remove(pcb_path)
        self.board = pcbnew.NewBoard(pcb_path)   # attaches a project; bare BOARD() crashes on save
        self.board.SetCopperLayerCount(layers)
        self.nets = {}
        self.fps = {}
        self.comps = {c['ref']: c for c in self.design['components']}

    # ---- nets / footprints ----------------------------------------------
    def net(self, name):
        if name not in self.nets:
            n = pcbnew.NETINFO_ITEM(self.board, name)
            self.board.Add(n)
            self.nets[name] = n
        return self.nets[name]

    def _load(self, fpid):
        lib, name = fpid.split(':', 1)
        path = self.lib_dirs.get(lib, os.path.join(FP_ROOT, f'{lib}.pretty'))
        fp = pcbnew.FootprintLoad(path, name)
        if fp is None:
            raise RuntimeError(f'footprint {fpid} not found in {path}')
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        path = f'{MODEL_DIR}/{MODELS[name]}' if name in MODELS else STOCK_MODELS.get(name)
        if path:                              # no stock model under the footprint's name
            fp.Models().clear()
            m = pcbnew.FP_3DMODEL()
            m.m_Filename = path
            fp.Models().push_back(m)
        return fp

    def place(self, ref, x, y, rot=0, side='F'):
        c = self.comps[ref]
        fp = self._load(c['footprint'])
        fp.SetReference(ref)
        fp.SetValue(c['value'])
        for k, v in c['fields'].items():
            if k in ('Datasheet',):
                continue
            fp.SetField(k, str(v))
            fld = fp.GetFieldByName(k)
            if fld:
                fld.SetVisible(False)
        path = pcbnew.KIID_PATH(f"/{c['sheet_uuid']}/{c['uuid']}")
        fp.SetPath(path)
        fp.SetSheetname(c['sheet'])
        fp.SetSheetfile(f"{c['sheet']}.kicad_sch")
        mpn = c['fields'].get('MPN')
        if mpn in MODELS_BY_MPN:              # the real body differs from the footprint's model
            fp.Models().clear()
            m = pcbnew.FP_3DMODEL()
            m.m_Filename = f'{MODEL_DIR}/{MODELS_BY_MPN[mpn]}'
            fp.Models().push_back(m)
        if c.get('dnp'):
            fp.SetDNP(True)
            fp.SetExcludedFromBOM(True)
            fp.SetExcludedFromPosFiles(True)
        self.board.Add(fp)
        fp.SetPosition(pt(x, y))
        if side == 'B':
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            num = pad.GetNumber()
            net = c['pins'].get(num)
            if net:
                pad.SetNet(self.net(net))
        self.fps[ref] = fp
        return fp

    def pad_xy(self, ref, num):
        """Board-mm position of a pad centre."""
        for pad in self.fps[ref].Pads():
            if pad.GetNumber() == str(num):
                p = pad.GetPosition()
                return (pcbnew.ToMM(p.x) - ORIGIN[0], pcbnew.ToMM(p.y) - ORIGIN[1])
        raise KeyError(f'{ref} pad {num}')

    def unplaced(self):
        return sorted(set(self.comps) - set(self.fps))

    # ---- drawing ------------------------------------------------------------
    def outline(self, w, h):
        for a, b in (((0, 0), (w, 0)), ((w, 0), (w, h)), ((w, h), (0, h)), ((0, h), (0, 0))):
            s = pcbnew.PCB_SHAPE(self.board, pcbnew.SHAPE_T_SEGMENT)
            s.SetStart(pt(*a))
            s.SetEnd(pt(*b))
            s.SetLayer(pcbnew.Edge_Cuts)
            s.SetWidth(mm(0.1))
            self.board.Add(s)

    def rect(self, layer, x0, y0, x1, y1, width=0.0, filled=True):
        s = pcbnew.PCB_SHAPE(self.board, pcbnew.SHAPE_T_RECT)
        s.SetStart(pt(x0, y0))
        s.SetEnd(pt(x1, y1))
        s.SetLayer(layer)
        s.SetWidth(mm(width))
        s.SetFilled(filled)
        self.board.Add(s)
        return s

    def poly(self, layer, pts, width=0.0, filled=True):
        s = pcbnew.PCB_SHAPE(self.board, pcbnew.SHAPE_T_POLY)
        s.SetPolyPoints([pt(*p) for p in pts])
        s.SetLayer(layer)
        s.SetWidth(mm(width))
        s.SetFilled(filled)
        self.board.Add(s)
        return s

    def clip_silk(self, rects, margin=0.1):
        """Cut footprint silkscreen out of the given rectangles (board mm), e.g. mask
        openings: lines are shortened, circles and outlines are cut as polylines,
        filled marks inside are dropped. Returns the number of items changed."""
        boxes = [(b[0].x, b[0].y, b[1].x, b[1].y) for b in ((pt(r[0], r[1]), pt(r[2], r[3])) for r in rects)]
        changed = 0
        for fp in self.board.GetFootprints():
            for gi in list(fp.GraphicalItems()):
                if gi.GetLayer() not in (pcbnew.F_SilkS, pcbnew.B_SilkS) or gi.GetClass() != 'PCB_SHAPE':
                    continue
                m = gi.GetWidth() // 2 + mm(margin)
                if not any(_hit(_box(gi), b, m) for b in boxes):
                    continue
                segs = _outline_segments(gi)
                if segs is None or gi.IsFilled():
                    fp.Remove(gi)
                    changed += 1
                    continue
                for b in boxes:
                    segs = [piece for s in segs for piece in _clip_outside(s, b, m)]
                fp.Remove(gi)
                for a, c in segs:
                    s = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_SEGMENT)
                    s.SetStart(pcbnew.VECTOR2I(int(a[0]), int(a[1])))
                    s.SetEnd(pcbnew.VECTOR2I(int(c[0]), int(c[1])))
                    s.SetLayer(gi.GetLayer())
                    s.SetWidth(gi.GetWidth())
                    fp.Add(s)
                changed += 1
        return changed

    def silk_for_fab(self, width=fabrules.SILK_W, gap=fabrules.SILK_GAP, step=0.02):
        """Footprint silkscreen to the fab's legend limits: outlines thinner than
        `width` are widened (KiCad's library draws 0.12 mm, JLCPCB asks for 0.153 mm)
        and every outline is cut back to stay `gap` clear of all mask openings.
        Filled marks that would touch an opening are dropped. Returns (widened, cut)."""
        w_min, st = mm(width), mm(step)
        openings = {pcbnew.F_SilkS: [], pcbnew.B_SilkS: []}
        for fp in self.board.GetFootprints():
            for p in fp.Pads():
                for silk, mask in ((pcbnew.F_SilkS, pcbnew.F_Mask), (pcbnew.B_SilkS, pcbnew.B_Mask)):
                    if p.IsOnLayer(mask):
                        openings[silk].append((p, _box(p), max(0, p.GetSolderMaskExpansion(mask))))
        widened = cut = 0
        for fp in self.board.GetFootprints():
            for gi in list(fp.GraphicalItems()):
                layer = gi.GetLayer()
                if layer not in openings or gi.GetClass() != 'PCB_SHAPE':
                    continue
                if not gi.IsFilled() and gi.GetWidth() < w_min:
                    gi.SetWidth(w_min)
                    widened += 1
                # clearance from the outline's centre line, plus half a sample step
                m = gi.GetWidth() // 2 + mm(gap) + st
                near = [(p, m + e) for p, b, e in openings[layer] if _hit(_box(gi), b, m + e)]
                if not near:
                    continue
                bad = lambda x, y: any(p.HitTest(pcbnew.VECTOR2I(int(x), int(y)), r) for p, r in near)
                segs = _outline_segments(gi)
                if segs is None:                   # bezier etc.: judged by its box
                    bx = _box(gi)
                    segs = list(zip([(bx[0], bx[1]), (bx[2], bx[1]), (bx[2], bx[3]), (bx[0], bx[3])],
                                    [(bx[2], bx[1]), (bx[2], bx[3]), (bx[0], bx[3]), (bx[0], bx[1])]))
                    filled = True
                else:
                    filled = gi.IsFilled()
                keep = []
                for (x0, y0), (x1, y1) in segs:
                    n = max(2, int(math.hypot(x1 - x0, y1 - y0) / st) + 1)
                    run = []
                    for i in range(n + 1):
                        x, y = x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n
                        if bad(x, y):
                            if len(run) > 1:
                                keep.append((run[0], run[-1]))
                            run = []
                        else:
                            run.append((x, y))
                    if len(run) > 1:
                        keep.append((run[0], run[-1]))
                if keep == segs:
                    continue
                if filled:                         # a mark cannot be shortened: drop it
                    fp.Remove(gi)
                    cut += 1
                    continue
                fp.Remove(gi)
                cut += 1
                for a, c in keep:
                    if math.hypot(c[0] - a[0], c[1] - a[1]) < mm(0.15):
                        continue                   # stubs shorter than the line is wide
                    s = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_SEGMENT)
                    s.SetStart(pcbnew.VECTOR2I(int(a[0]), int(a[1])))
                    s.SetEnd(pcbnew.VECTOR2I(int(c[0]), int(c[1])))
                    s.SetLayer(layer)
                    s.SetWidth(gi.GetWidth())
                    fp.Add(s)
        return widened, cut

    def line(self, layer, a, b, width=0.15):
        s = pcbnew.PCB_SHAPE(self.board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pt(*a))
        s.SetEnd(pt(*b))
        s.SetLayer(layer)
        s.SetWidth(mm(width))
        self.board.Add(s)

    def text(self, s, x, y, layer=pcbnew.F_SilkS, size=1.5, thick=0.25, rot=0, justify='left', mirror=False):
        t = pcbnew.PCB_TEXT(self.board)
        t.SetText(s)
        t.SetPosition(pt(x, y))
        t.SetLayer(layer)
        t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
        t.SetTextThickness(mm(thick))
        t.SetTextAngleDegrees(rot)
        t.SetHorizJustify({'left': pcbnew.GR_TEXT_H_ALIGN_LEFT, 'center': pcbnew.GR_TEXT_H_ALIGN_CENTER,
                           'right': pcbnew.GR_TEXT_H_ALIGN_RIGHT}[justify])
        t.SetMirrored(mirror)
        self.board.Add(t)
        return t

    def npth(self, x, y, d=3.2):
        """Non-plated hole (a tiny board-only footprint)."""
        fp = pcbnew.FOOTPRINT(self.board)
        fp.SetReference(f'NP{len(self.board.GetFootprints()) + 1}')
        fp.SetFPID(pcbnew.LIB_ID('elara', 'Hole_NPTH'))
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_BOARD_ONLY)
        pad = pcbnew.PAD(fp)
        pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
        pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
        pad.SetSize(pcbnew.VECTOR2I(mm(d), mm(d)))
        pad.SetDrillSize(pcbnew.VECTOR2I(mm(d), mm(d)))
        pad.SetLayerSet(pad.UnplatedHoleMask())
        fp.Add(pad)
        self.board.Add(fp)
        fp.SetPosition(pt(x, y))
        return fp

    def hole(self, x, y, d=3.2, net='GND', pad_d=6.0):
        """Plated M3 hole with an annular pad on the given net (a tiny footprint)."""
        fp = pcbnew.FOOTPRINT(self.board)
        fp.SetReference(f'H{len([f for f in self.board.GetFootprints() if f.GetReference().startswith("H")]) + 1}')
        fp.SetFPID(pcbnew.LIB_ID('elara', 'MountingHole_M3_Strip'))   # an empty FPID breaks SES import
        fp.SetValue('M3')
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_BOARD_ONLY)
        pad = pcbnew.PAD(fp)
        pad.SetNumber('1')
        pad.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
        pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
        pad.SetSize(pcbnew.VECTOR2I(mm(pad_d), mm(pad_d)))
        pad.SetDrillSize(pcbnew.VECTOR2I(mm(d), mm(d)))
        pad.SetLayerSet(pad.PTHMask())
        pad.SetNet(self.net(net))
        fp.Add(pad)
        self.board.Add(fp)
        fp.SetPosition(pt(x, y))
        return fp

    # ---- copper -------------------------------------------------------------
    def track(self, net, pts, width=0.25, layer=pcbnew.F_Cu, locked=True):
        for a, b in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(self.board)
            t.SetStart(pt(*a))
            t.SetEnd(pt(*b))
            t.SetWidth(mm(width))
            t.SetLayer(layer)
            t.SetNet(self.net(net))
            t.SetLocked(locked)
            self.board.Add(t)

    def via(self, net, x, y, d=0.6, drill=0.3, locked=True):
        v = pcbnew.PCB_VIA(self.board)
        v.SetPosition(pt(x, y))
        v.SetWidth(mm(d))
        v.SetDrill(mm(drill))
        v.SetNet(self.net(net))
        v.SetLocked(locked)
        self.board.Add(v)
        return v

    def _poly(self, pts):
        chain = pcbnew.SHAPE_LINE_CHAIN()
        for p in pts:
            chain.Append(pt(*p))
        chain.SetClosed(True)
        return chain

    def _outline(self, z, pts, holes=()):
        # build in place: SetOutline() would take ownership of a Python-owned
        # SHAPE_POLY_SET and crash KiCad when the board is saved
        o = z.Outline()
        o.NewOutline()
        for p in pts:
            o.Append(pt(*p))
        for h in holes:
            o.NewHole()
            for p in h:
                o.Append(pt(*p), 0, 0)

    def zone(self, net, layer, pts, priority=0, clearance=0.25, min_w=0.25, name='', thermal=True, holes=()):
        z = pcbnew.ZONE(self.board)
        z.SetLayer(layer)
        z.SetNet(self.net(net))
        self._outline(z, pts, holes)
        z.SetAssignedPriority(priority)
        z.SetLocalClearance(mm(clearance))
        z.SetMinThickness(mm(min_w))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL if thermal else pcbnew.ZONE_CONNECTION_FULL)
        z.SetThermalReliefGap(mm(0.3))
        z.SetThermalReliefSpokeWidth(mm(0.4))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        if name:
            z.SetZoneName(name)
        self.board.Add(z)
        return z

    def keepout(self, layers, pts, tracks=True, vias=True, pads=False, pour=False, fps=False, name=''):
        z = pcbnew.ZONE(self.board)
        z.SetIsRuleArea(True)
        ls = pcbnew.LSET()
        for l in layers:
            ls.AddLayer(l)
        z.SetLayerSet(ls)
        self._outline(z, pts)
        z.SetDoNotAllowTracks(tracks)
        z.SetDoNotAllowVias(vias)
        z.SetDoNotAllowPads(pads)
        z.SetDoNotAllowCopperPour(pour)
        z.SetDoNotAllowFootprints(fps)
        if name:
            z.SetZoneName(name)
        self.board.Add(z)
        return z

    @classmethod
    def load(cls, pcb_path):
        """Wrap an existing board file (for the finish stages)."""
        self = cls.__new__(cls)
        self.path = pcb_path
        self.board = pcbnew.LoadBoard(pcb_path)
        self.nets = {n.GetNetname(): n for n in self.board.GetNetsByName().values()}
        self.fps = {f.GetReference(): f for f in self.board.GetFootprints()}
        self.design, self.comps, self.lib_dirs = {'components': []}, {}, {}
        return self

    def drop_rule_areas(self, prefix):
        for z in list(self.board.Zones()):
            if z.GetIsRuleArea() and z.GetZoneName().startswith(prefix):
                self.board.Remove(z)

    def free_for_via(self, x, y, d=0.6, clearance=0.3, avoid_courtyards=True):
        """True if a via at (x, y) would clear every pad, track, via and courtyard."""
        p = pt(x, y)
        r = mm(d / 2 + clearance)
        for fp in self.board.GetFootprints():
            if avoid_courtyards:
                c = fp.GetCourtyard(pcbnew.F_CrtYd)
                if c.OutlineCount() and c.Collide(p, r):
                    return False
                c = fp.GetCourtyard(pcbnew.B_CrtYd)
                if c.OutlineCount() and c.Collide(p, r):
                    return False
            for pad in fp.Pads():
                if pad.HitTest(p, r):
                    return False
        for t in self.board.GetTracks():
            if t.HitTest(p, r):
                return False
        return True

    def segment_free(self, a, b, net, width=0.3, clearance=0.25, steps=6):
        """True if a straight track a->b clears every pad and track of other nets."""
        r = mm(width / 2 + clearance)
        for k in range(steps + 1):
            p = pt(a[0] + (b[0] - a[0]) * k / steps, a[1] + (b[1] - a[1]) * k / steps)
            for fp in self.board.GetFootprints():
                for pad in fp.Pads():
                    if pad.GetNetname() != net and pad.HitTest(p, r):
                        return False
            for t in self.board.GetTracks():
                if t.GetNetname() != net and t.HitTest(p, r):
                    return False
        return True

    def fanout(self, net='GND', dist=1.3, exclude=None):
        """Give every SMD pad of `net` its own via (plus a short track) to the planes."""
        n = 0
        self.fanout_failed = []
        for fp in self.board.GetFootprints():
            for pad in fp.Pads():
                if pad.GetNetname() != net or pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                    continue
                c = pad.GetPosition()
                cx, cy = pcbnew.ToMM(c.x) - ORIGIN[0], pcbnew.ToMM(c.y) - ORIGIN[1]
                if exclude and exclude(cx, cy):
                    continue
                half = max(pcbnew.ToMM(pad.GetSize().x), pcbnew.ToMM(pad.GetSize().y)) / 2
                for k in range(16):
                    a = math.pi * k / 8
                    for d in (half + dist - 0.5, half + dist, half + dist + 0.8, half + dist + 1.6, half + dist + 2.4):
                        v = (cx + d * math.cos(a), cy + d * math.sin(a))
                        if self.free_for_via(*v, avoid_courtyards=False) and self.segment_free((cx, cy), v, net):
                            self.track(net, [(cx, cy), v], width=0.3, layer=pad.GetLayer())
                            self.via(net, *v)
                            n += 1
                            break
                    else:
                        continue
                    break
                else:
                    self.fanout_failed.append(f'{fp.GetReference()}.{pad.GetNumber()}')
        return n

    def stitch(self, points, net='GND', **kw):
        """Add vias at the given points where they fit; returns how many were placed.
        No via lands under board silkscreen text (it would break up the lettering)."""
        texts = [_box(d, mm(0.6)) for d in self.board.Drawings()
                 if d.GetClass() == 'PCB_TEXT' and d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS)]
        n = 0
        for x, y in points:
            p = pt(x, y)
            if any(b[0] <= p.x <= b[2] and b[1] <= p.y <= b[3] for b in texts):
                continue
            if self.free_for_via(x, y, **kw):
                self.via(net, x, y, locked=True)
                n += 1
        return n

    def silk_obstacles(self, side, keep_clear=(), courtyards=False, skip=None):
        """Boxes (IU) that silkscreen on one side must avoid: pads (with mask margin),
        footprint and board silk, the given keep-clear rectangles (board mm, e.g.
        mask openings) and, optionally, other footprints' bodies."""
        silk, cu, crt = ((pcbnew.F_SilkS, pcbnew.F_Cu, pcbnew.F_CrtYd) if side == 'F'
                         else (pcbnew.B_SilkS, pcbnew.B_Cu, pcbnew.B_CrtYd))
        out = [(pt(r[0], r[1]).x, pt(r[0], r[1]).y, pt(r[2], r[3]).x, pt(r[2], r[3]).y) for r in keep_clear]
        # compare by reference: SWIG hands out a new proxy object for the same
        # footprint on every call, so 'is' never matches
        skip = skip.GetReference() if skip is not None else None
        for fp in self.board.GetFootprints():
            other = fp.GetReference() != skip
            for p in fp.Pads():
                if p.IsOnLayer(cu):
                    out.append(_box(p, mm(0.1)))
            for gi in fp.GraphicalItems():
                if gi.GetLayer() == silk and gi.GetClass() not in ('PCB_FIELD', 'PCB_TEXT'):
                    out.append(_box(gi))
                if courtyards and other and gi.GetLayer() == crt:
                    out.append(_box(gi))
            if other and fp.Reference().IsVisible() and fp.Reference().GetLayer() == silk:
                out.append(_box(fp.Reference()))
        for d in self.board.Drawings():
            if d.GetLayer() == silk:
                out.append(_box(d))
        return out

    def text_block_free(self, lines, spots, keep_clear=(), avoid_tracks=False, **kw):
        """Place a block of text lines [(text, dy, size, thick)] as one unit at the first
        candidate anchor where every line is clear (see text_free)."""
        side = 'B' if kw.get('layer') == pcbnew.B_SilkS else 'F'
        obst = self.silk_obstacles(side, keep_clear, courtyards=True)
        cu = pcbnew.F_Cu if side == 'F' else pcbnew.B_Cu
        wires = [((t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y), t.GetWidth() // 2)
                 for t in self.board.GetTracks() if avoid_tracks and t.IsOnLayer(cu)]
        eb = self.board.GetBoardEdgesBoundingBox()
        for x, y in spots:
            made, ok = [], True
            for text, dy, size, thick in lines:
                t = self.text(text, x, y + dy, size=size, thick=thick, **kw)
                made.append(t)
                bb = _box(t)
                inside = eb.GetX() < bb[0] and bb[2] < eb.GetRight() and eb.GetY() < bb[1] and bb[3] < eb.GetBottom()
                if (not inside or any(_hit(bb, o, mm(0.2)) for o in obst)
                        or any(_seg_box((p, q), bb, hw + mm(0.2)) for p, q, hw in wires)):
                    ok = False
                    break
            if ok:
                return (x, y)
            for t in made:
                self.board.Remove(t)
        if avoid_tracks:
            return self.text_block_free(lines, spots, keep_clear, avoid_tracks=False, **kw)
        raise SystemExit(f'no free spot for text block {lines[0][0]!r}')

    def remove_texts(self, strings, layer=pcbnew.F_SilkS):
        for d in list(self.board.Drawings()):
            if d.GetClass() == 'PCB_TEXT' and d.GetLayer() == layer and d.GetText() in strings:
                self.board.Remove(d)

    def text_free(self, s, spots, keep_clear=(), avoid_tracks=False, **kw):
        """Place a text at the first of the candidate spots (board mm) that is clear
        of pads, silk, footprint bodies and mask openings (and tracks, if asked)."""
        side = 'B' if kw.get('layer') == pcbnew.B_SilkS else 'F'
        obst = self.silk_obstacles(side, keep_clear, courtyards=True)
        cu = pcbnew.F_Cu if side == 'F' else pcbnew.B_Cu
        wires = [((t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y), t.GetWidth() // 2)
                 for t in self.board.GetTracks() if avoid_tracks and t.IsOnLayer(cu)]
        eb = self.board.GetBoardEdgesBoundingBox()
        why = []
        for x, y in spots:
            t = self.text(s, x, y, **kw)
            bb = _box(t)
            inside = eb.GetX() < bb[0] and bb[2] < eb.GetRight() and eb.GetY() < bb[1] and bb[3] < eb.GetBottom()
            hits = [o for o in obst if _hit(bb, o, mm(0.2))]
            if any(_seg_box((p, q), bb, hw + mm(0.2)) for p, q, hw in wires):
                hits.append(bb)
            if inside and not hits:
                return (x, y)
            if len(why) < 4:
                why.append(f'  {(x, y)}: ' + ('' if inside else 'off board ') +
                           ' '.join(str(tuple(round(pcbnew.ToMM(v) - ORIGIN[0], 1) for v in o)) for o in hits[:4]))
            self.board.Remove(t)
        if avoid_tracks:        # nothing clear of the tracks: accept silk over masked tracks
            return self.text_free(s, spots, keep_clear, avoid_tracks=False, **kw)
        raise SystemExit(f'no free spot for text {s!r}; blocked by\n' + '\n'.join(why))

    def tidy_refs(self, keep_clear=(), gap=0.15):
        """Move every visible reference designator to a spot clear of pads, silk and
        mask openings; hide it where nothing fits -- the assembly drawing (F.Fab)
        still carries it. The candidate spots come in a fixed order that depends on
        the part's shape, so parts in a row get their labels in a row: a small
        vertical part takes a vertical label above or below it (else alongside), a
        horizontal or large part a horizontal one above or below it. Text reads left
        to right or bottom to top (0 or 90 degrees), never upside down."""
        g = mm(gap)
        eb = self.board.GetBoardEdgesBoundingBox()
        edge = (eb.GetX() + mm(0.5), eb.GetY() + mm(0.5), eb.GetRight() - mm(0.5), eb.GetBottom() - mm(0.5))
        hidden = []
        # fitted parts first: a do-not-fit footprint only gets a label where one is left
        todo = [fp for fp in sorted(self.board.GetFootprints(), key=lambda f: (f.IsDNP(), f.GetReference()))
                if fp.Reference().IsVisible() and fp.Reference().GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS)]
        for fp in todo:                 # labels not placed yet are no obstacles
            fp.Reference().SetVisible(False)
        for fp in todo:
            ref = fp.Reference()
            ref.SetVisible(True)
            side = 'F' if ref.GetLayer() == pcbnew.F_SilkS else 'B'
            body = [_box(p) for p in fp.Pads()] + [_box(gi) for gi in fp.GraphicalItems()
                                                  if gi.GetLayer() in (pcbnew.F_CrtYd, pcbnew.B_CrtYd)]
            if not body:
                continue
            x0, y0 = min(b[0] for b in body), min(b[1] for b in body)
            x1, y1 = max(b[2] for b in body), max(b[3] for b in body)
            cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
            ref.SetTextAngleDegrees(0)
            r0 = _box(ref)
            tw, th = r0[2] - r0[0], r0[3] - r0[1]
            m0 = mm(0.25)
            if y1 - y0 > x1 - x0 and x1 - x0 < mm(3.0):   # small vertical part: label in line with
                pref = [(cx, y0 - tw // 2 - m0, 90), (cx, y1 + tw // 2 + m0, 90),   # it, above/below,
                        (x1 + th // 2 + m0, cy, 90), (x0 - th // 2 - m0, cy, 90)]     # else alongside
            else:                                      # horizontal or large part: label above, then below
                pref = [(cx, y0 - th // 2 - m0, 0), (cx, y1 + th // 2 + m0, 0),
                        (x1 + th // 2 + m0, cy, 90), (x0 - th // 2 - m0, cy, 90)]
            cands = []
            for m in (m0, m0 + th):                    # around the part, then one text height out
                cands += [(cx, y0 - th // 2 - m, 0), (cx, y1 + th // 2 + m, 0),
                          (x1 + tw // 2 + m, cy, 0), (x0 - tw // 2 - m, cy, 0),
                          (x1 + th // 2 + m, cy, 90), (x0 - th // 2 - m, cy, 90),
                          (x0 + tw // 2, y0 - th // 2 - m, 0), (x1 - tw // 2, y0 - th // 2 - m, 0),
                          (x0 + tw // 2, y1 + th // 2 + m, 0), (x1 - tw // 2, y1 + th // 2 + m, 0),
                          (cx, y0 - tw // 2 - m, 90), (cx, y1 + tw // 2 + m, 90)]
            placed = False
            cu = pcbnew.F_Cu if side == 'F' else pcbnew.B_Cu
            wires = [((t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y), t.GetWidth() // 2)
                     for t in self.board.GetTracks() if t.IsOnLayer(cu)]
            # the shape-based spots first, clear of other parts, even over (masked) tracks:
            # rows of parts then get rows of labels; then every other spot, best first
            tries = [(pref, True, True), (pref, True, False)] + [
                (cands, c, t) for c, t in ((True, True), (False, True), (True, False), (False, False))]
            for spots, courtyards, avoid_tracks in tries:
                obst = self.silk_obstacles(side, keep_clear, courtyards, skip=fp)
                for x, y, a in spots:
                    ref.SetTextAngleDegrees(a)
                    ref.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
                    bb = _box(ref)
                    if not (edge[0] <= bb[0] and bb[2] <= edge[2] and edge[1] <= bb[1] and bb[3] <= edge[3]):
                        continue
                    if any(_hit(bb, o, g) for o in obst):
                        continue
                    if avoid_tracks and any(_seg_box((p, q), bb, hw + g) for p, q, hw in wires):
                        continue
                    placed = True
                    break
                if placed:
                    break
            if not placed:
                ref.SetVisible(False)
                hidden.append(fp.GetReference())
        return hidden

    def rename_nets_to_schematic(self, design_json):
        """Give every net the name KiCad's schematic uses (sheet-path prefix on local
        nets), so 'Update PCB from Schematic' and the DRC parity check agree. Routing
        and the finish stages work with the short design names; call this last."""
        with open(design_json, encoding='utf-8') as f:
            names = json.load(f).get('kicad_net_names', {})
        n = 0
        for net in list(self.board.GetNetsByName().values()):
            new = names.get(net.GetNetname())
            if new and new != net.GetNetname():
                net.SetNetname(new)
                n += 1
        # pins left open on purpose get KiCad's single-pin 'unconnected-(...)' nets
        with open(design_json, encoding='utf-8') as f:
            open_pins = json.load(f).get('kicad_unconnected', {})
        fps = {fp.GetReference(): fp for fp in self.board.GetFootprints()}
        for key, name in open_pins.items():
            ref, num = key.rsplit('.', 1)
            for pad in fps[ref].Pads() if ref in fps else ():
                if pad.GetNumber() == num and not pad.GetNetname():
                    net = pcbnew.NETINFO_ITEM(self.board, name)
                    self.board.Add(net)
                    pad.SetNet(net)
        self.board.BuildListOfNets()
        return n

    def hide_fab_values(self):
        """Values off the fab layers: the assembly drawing then shows only the
        references, which otherwise disappear under neighbouring values (values
        are in the BOM and the interactive BOM)."""
        n = 0
        for fp in self.board.GetFootprints():
            v = fp.Value()
            if v.GetLayer() in (pcbnew.F_Fab, pcbnew.B_Fab) and v.IsVisible():
                v.SetVisible(False)
                n += 1
        return n

    def hide_fab_refs(self):
        """The fab-layer copy of the reference ('${REFERENCE}' text) removed wherever the
        silkscreen reference is shown (KiCad 9 texts have no visibility flag, only fields
        do). The assembly drawing plots fab and silk together, so each part is then named
        once, and no fab copy can land on a neighbour's label. Parts whose silk reference
        found no room (tidy_refs) keep the fab copy."""
        n = 0
        for fp in self.board.GetFootprints():
            if not fp.Reference().IsVisible():
                continue
            copies = [gi for gi in fp.GraphicalItems()
                      if gi.GetClass() == 'PCB_TEXT' and gi.GetLayer() in (pcbnew.F_Fab, pcbnew.B_Fab)
                      and gi.GetText() == '${REFERENCE}']
            for gi in copies:
                fp.Remove(gi)
                n += 1
        return n

    def fab_ref_beside(self, ref, side='left', gap=0.5, size=1.0):
        """Fab-layer reference, upright, beside a part whose silk reference found no
        room (tidy_refs hid it), so the assembly drawing still names the part, clear of
        its pads. A footprint without a fab reference text gets one."""
        fp = self.fps[ref]
        layer = pcbnew.B_Fab if fp.IsFlipped() else pcbnew.F_Fab
        t = next((gi for gi in fp.GraphicalItems() if gi.GetClass() == 'PCB_TEXT'
                  and gi.GetLayer() == layer and gi.GetText() == '${REFERENCE}'), None)
        if t is None:
            t = pcbnew.PCB_TEXT(fp)
            t.SetText('${REFERENCE}')
            t.SetLayer(layer)
            fp.Add(t)
        t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
        t.SetTextThickness(mm(0.15))
        t.SetTextAngleDegrees(0)
        boxes = [p.GetBoundingBox() for p in fp.Pads()]
        x0, x1 = min(bb.GetX() for bb in boxes), max(bb.GetRight() for bb in boxes)
        ym = (min(bb.GetY() for bb in boxes) + max(bb.GetBottom() for bb in boxes)) // 2
        if side == 'left':
            t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_RIGHT)
            t.SetPosition(pcbnew.VECTOR2I(x0 - mm(gap), ym))
        else:
            t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
            t.SetPosition(pcbnew.VECTOR2I(x1 + mm(gap), ym))
        t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
        return t

    def fill(self):
        pcbnew.ZONE_FILLER(self.board).Fill(self.board.Zones())

    def title_block(self, title, rev, company='ELARA -- ELF Atmospheric Radio Analyser', date=None):
        tb = pcbnew.TITLE_BLOCK()
        tb.SetTitle(title)
        tb.SetRevision(rev)
        tb.SetCompany(company)
        if date:
            tb.SetDate(date)
        tb.SetComment(0, 'CERN-OHL-W-2.0')
        self.board.SetTitleBlock(tb)

    def save(self, path=None):
        """Save the board with the fab's rules: mask web in the board file, constraints
        in the project file, custom rules in <board>.kicad_dru (kicadgen/fabrules.py)."""
        path = path or self.path
        self.board.GetDesignSettings().m_SolderMaskMinWidth = mm(fabrules.MASK_DAM)
        pcbnew.SaveBoard(path, self.board)
        fabrules.write(path, self.board.GetCopperLayerCount(), extra_rules=getattr(self, 'extra_rules', ''))


def rect_pts(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
