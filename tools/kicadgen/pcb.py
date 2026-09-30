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
    bb = item.GetBoundingBox()
    return (bb.GetX() - grow, bb.GetY() - grow, bb.GetRight() + grow, bb.GetBottom() + grow)


def _hit(a, b, m=0):
    return a[0] - m < b[2] and b[0] - m < a[2] and a[1] - m < b[3] and b[1] - m < a[3]


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
        """Add vias at the given points where they fit; returns how many were placed."""
        n = 0
        for x, y in points:
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
        for fp in self.board.GetFootprints():
            for p in fp.Pads():
                if p.IsOnLayer(cu):
                    out.append(_box(p, mm(0.1)))
            for gi in fp.GraphicalItems():
                if gi.GetLayer() == silk and gi.GetClass() not in ('PCB_FIELD', 'PCB_TEXT'):
                    out.append(_box(gi))
                if courtyards and fp is not skip and gi.GetLayer() == crt:
                    out.append(_box(gi))
            if fp is not skip and fp.Reference().IsVisible() and fp.Reference().GetLayer() == silk:
                out.append(_box(fp.Reference()))
        for d in self.board.Drawings():
            if d.GetLayer() == silk:
                out.append(_box(d))
        return out

    def text_free(self, s, spots, keep_clear=(), **kw):
        """Place a text at the first of the candidate spots (board mm) that is clear
        of pads, silk, footprint bodies and mask openings."""
        side = 'B' if kw.get('layer') == pcbnew.B_SilkS else 'F'
        obst = self.silk_obstacles(side, keep_clear, courtyards=True)
        eb = self.board.GetBoardEdgesBoundingBox()
        why = []
        for x, y in spots:
            t = self.text(s, x, y, **kw)
            bb = _box(t)
            inside = eb.GetX() < bb[0] and bb[2] < eb.GetRight() and eb.GetY() < bb[1] and bb[3] < eb.GetBottom()
            hits = [o for o in obst if _hit(bb, o, mm(0.2))]
            if inside and not hits:
                return (x, y)
            if len(why) < 4:
                why.append(f'  {(x, y)}: ' + ('' if inside else 'off board ') +
                           ' '.join(str(tuple(round(pcbnew.ToMM(v) - ORIGIN[0], 1) for v in o)) for o in hits[:4]))
            self.board.Remove(t)
        raise SystemExit(f'no free spot for text {s!r}; blocked by\n' + '\n'.join(why))

    def tidy_refs(self, keep_clear=(), gap=0.15):
        """Move every visible reference designator to a spot clear of pads, silk and
        mask openings (current spot first, then around the part); hide it where
        nothing fits -- the assembly drawing (F.Fab) still carries it."""
        g = mm(gap)
        eb = self.board.GetBoardEdgesBoundingBox()
        edge = (eb.GetX() + mm(0.5), eb.GetY() + mm(0.5), eb.GetRight() - mm(0.5), eb.GetBottom() - mm(0.5))
        hidden = []
        # fitted parts first: a do-not-fit footprint only gets a label where one is left
        for fp in sorted(self.board.GetFootprints(), key=lambda f: (f.IsDNP(), f.GetReference())):
            ref = fp.Reference()
            if not ref.IsVisible() or ref.GetLayer() not in (pcbnew.F_SilkS, pcbnew.B_SilkS):
                continue
            side = 'F' if ref.GetLayer() == pcbnew.F_SilkS else 'B'
            body = [_box(p) for p in fp.Pads()] + [_box(gi) for gi in fp.GraphicalItems()
                                                  if gi.GetLayer() in (pcbnew.F_CrtYd, pcbnew.B_CrtYd)]
            if not body:
                continue
            x0, y0 = min(b[0] for b in body), min(b[1] for b in body)
            x1, y1 = max(b[2] for b in body), max(b[3] for b in body)
            cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
            ref.SetTextAngleDegrees(0)
            tw, th = ref.GetBoundingBox().GetWidth(), ref.GetBoundingBox().GetHeight()
            m = mm(0.25)
            cands = [(ref.GetPosition().x, ref.GetPosition().y, ref.GetTextAngleDegrees()),
                     (cx, y0 - th // 2 - m, 0), (cx, y1 + th // 2 + m, 0),
                     (x1 + tw // 2 + m, cy, 0), (x0 - tw // 2 - m, cy, 0),
                     (x1 + th // 2 + m, cy, 90), (x0 - th // 2 - m, cy, 90),
                     (x0 + tw // 2, y0 - th // 2 - m, 0), (x1 - tw // 2, y0 - th // 2 - m, 0),
                     (x0 + tw // 2, y1 + th // 2 + m, 0), (x1 - tw // 2, y1 + th // 2 + m, 0),
                     (cx, y0 - tw // 2 - m, 90), (cx, y1 + tw // 2 + m, 90)]
            placed = False
            for courtyards in (True, False):
                obst = self.silk_obstacles(side, keep_clear, courtyards, skip=fp)
                for x, y, a in cands:
                    ref.SetTextAngleDegrees(a)
                    ref.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
                    bb = _box(ref)
                    if not (edge[0] <= bb[0] and bb[2] <= edge[2] and edge[1] <= bb[1] and bb[3] <= edge[3]):
                        continue
                    if any(_hit(bb, o, g) for o in obst):
                        continue
                    placed = True
                    break
                if placed:
                    break
            if not placed:
                ref.SetVisible(False)
                hidden.append(fp.GetReference())
        return hidden

    def fill(self):
        pcbnew.ZONE_FILLER(self.board).Fill(self.board.Zones())

    def save(self, path=None):
        pcbnew.SaveBoard(path or self.path, self.board)


def rect_pts(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
