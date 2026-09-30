"""Board-building helpers on top of KiCad's pcbnew Python API.

Runs inside KiCad's Python (e.g. the kicad/kicad:9.0-full image), reads the
design_netlist.json written by a design.py, and places footprints with the
schematic links (symbol paths) KiCad needs for "Update PCB from schematic".
Coordinates passed to these helpers are board millimetres (origin at the
board's top-left corner, y down); ORIGIN shifts them onto the drawing sheet.
"""

import json
import os

import pcbnew

FP_ROOT = '/usr/share/kicad/footprints'
ORIGIN = (50.0, 50.0)


def mm(v):
    return pcbnew.FromMM(v)


def pt(x, y):
    return pcbnew.VECTOR2I(mm(ORIGIN[0] + x), mm(ORIGIN[1] + y))


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

    def stitch(self, points, net='GND', **kw):
        """Add vias at the given points where they fit; returns how many were placed."""
        n = 0
        for x, y in points:
            if self.free_for_via(x, y, **kw):
                self.via(net, x, y, locked=True)
                n += 1
        return n

    def fill(self):
        pcbnew.ZONE_FILLER(self.board).Fill(self.board.Zones())

    def save(self, path=None):
        pcbnew.SaveBoard(path or self.path, self.board)


def rect_pts(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
