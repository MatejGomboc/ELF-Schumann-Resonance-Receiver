# SPDX-License-Identifier: CERN-OHL-W-2.0
"""
ELARA -- helpers for the electromagnetic studies (run_em.py)

1. A minimal KiCad 9 S-expression reader that pulls the copper out of a
   .kicad_pcb: track segments, vias, pads (with footprint rotation) and filled
   zone polygons, all in board millimetres (file coordinates minus the +50 mm
   page offset that kicadgen applies).
2. A finite-difference Laplace solver on a non-uniform tensor grid with a
   layered permittivity eps_r(z).  Conductors are sets of grid nodes held at a
   fixed potential; grid edges without a neighbour are natural Neumann
   (zero normal flux) boundaries.  The charge on every conductor follows from
   the discrete Gauss law (Q_n = sum_m c_nm (V_n - V_m)), which gives one row of
   the Maxwell capacitance matrix per excitation.

The solver uses pyamg (Ruge-Stuben AMG preconditioned CG) when it is
installed and falls back to Jacobi-preconditioned CG from scipy otherwise
(same answer, about ten times slower).

Licence: CERN-OHL-W-2.0
"""

import math
import re

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import os as _os  # noqa: E402
_os.environ.setdefault("SOURCE_DATE_EPOCH", "0")   # fixed SVG date: no churn on re-runs
import matplotlib  # noqa: E402
matplotlib.rc_file(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "matplotlibrc"))
from matplotlib.path import Path  # noqa: E402

try:
    import pyamg
except ImportError:          # pragma: no cover
    pyamg = None

EPS0 = 8.8541878128e-12
OFFSET = 50.0                # kicadgen places the 200 x 100 board at (50, 50) on the page

# ---------------------------------------------------------------------------
# S-expression reader
# ---------------------------------------------------------------------------
_TOK = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')


def parse_sexpr(text):
    """Return the nested-list form of a KiCad S-expression (atoms stay strings)."""
    stack = [[]]
    for m in _TOK.finditer(text):
        t = m.group(0)
        if t == '(':
            stack.append([])
        elif t == ')':
            node = stack.pop()
            stack[-1].append(node)
        elif t[0] == '"':
            stack[-1].append(t[1:-1])
        else:
            stack[-1].append(t)
    return stack[0][0]


def _kids(node, key):
    return [c for c in node[1:] if isinstance(c, list) and c and c[0] == key]


def _kid(node, key):
    k = _kids(node, key)
    return k[0] if k else None


def _xy(node):
    return float(node[1]), float(node[2])


def load_board(path):
    """Copper of a KiCad board in board mm: dict(nets, segments, vias, pads, zones)."""
    with open(path, encoding='utf-8') as fh:
        root = parse_sexpr(fh.read())
    nets = {int(n[1]): n[2] for n in _kids(root, 'net')}
    segs, vias, pads, zones = [], [], [], []
    for s in _kids(root, 'segment'):
        (x1, y1), (x2, y2) = _xy(_kid(s, 'start')), _xy(_kid(s, 'end'))
        segs.append(dict(x1=x1 - OFFSET, y1=y1 - OFFSET, x2=x2 - OFFSET, y2=y2 - OFFSET,
                         w=float(_kid(s, 'width')[1]), layer=_kid(s, 'layer')[1],
                         net=nets[int(_kid(s, 'net')[1])]))
    for v in _kids(root, 'via'):
        x, y = _xy(_kid(v, 'at'))
        vias.append(dict(x=x - OFFSET, y=y - OFFSET, d=float(_kid(v, 'size')[1]),
                         drill=float(_kid(v, 'drill')[1]), net=nets[int(_kid(v, 'net')[1])]))
    for fp in _kids(root, 'footprint'):
        at = _kid(fp, 'at')
        fx, fy = float(at[1]), float(at[2])
        frot = float(at[3]) if len(at) > 3 else 0.0
        ref = next((p[2] for p in _kids(fp, 'property') if p[1] == 'Reference'), '?')
        side = _kid(fp, 'layer')[1]
        th = math.radians(frot)
        for p in _kids(fp, 'pad'):
            pat = _kid(p, 'at')
            px, py = float(pat[1]), float(pat[2])
            prot = float(pat[3]) if len(pat) > 3 else 0.0      # absolute angle (includes the footprint's)
            # KiCad: board = fp + R(-theta) * local, with y pointing down
            bx = fx + px * math.cos(th) + py * math.sin(th)
            by = fy - px * math.sin(th) + py * math.cos(th)
            size = _kid(p, 'size')
            layers = _kid(p, 'layers')[1:]
            net = _kid(p, 'net')
            drill = _kid(p, 'drill')
            pads.append(dict(ref=ref, num=p[1], kind=p[2], shape=p[3], x=bx - OFFSET, y=by - OFFSET,
                             w=float(size[1]), h=float(size[2]), rot=prot, layers=layers,
                             net=net[2] if net else '', side=side,
                             drill=float(drill[1]) if drill and len(drill) > 1 and drill[1] != 'oval' else 0.0))
    for z in _kids(root, 'zone'):
        net = _kid(z, 'net_name')
        for fpoly in _kids(z, 'filled_polygon'):
            pts = np.array([_xy(q) for q in _kid(fpoly, 'pts')[1:] if q[0] == 'xy']) - OFFSET
            zones.append(dict(net=net[1] if net else '', layer=_kid(fpoly, 'layer')[1], pts=pts,
                              name=(_kid(z, 'name') or [None, ''])[1]))
    return dict(nets=nets, segments=segs, vias=vias, pads=pads, zones=zones)


def pad_on_layer(pad, layer):
    return layer in pad['layers'] or '*.Cu' in pad['layers']


# ---------------------------------------------------------------------------
# Non-uniform grid helpers
# ---------------------------------------------------------------------------
def graded_axis(lo, hi, fine_lo, fine_hi, h_fine, h_max, growth=1.3, keep=()):
    """Node coordinates: uniform h_fine on [fine_lo, fine_hi], geometric growth outside,
    plus the exact coordinates in `keep` (copper planes, interfaces)."""
    core = np.arange(fine_lo, fine_hi + 1e-9, h_fine)
    left, x, h = [], fine_lo, h_fine
    while x - h > lo + 1e-9:
        h = min(h * growth, h_max)
        x -= h
        if x - lo < 0.5 * h:
            break
        left.append(x)
    right, x, h = [], fine_hi, h_fine
    while x + h < hi - 1e-9:
        h = min(h * growth, h_max)
        x += h
        if hi - x < 0.5 * h:
            break
        right.append(x)
    ax = np.unique(np.round(np.concatenate([[lo], left[::-1], core, right, [hi], list(keep)]), 6))
    return ax[(ax >= lo - 1e-9) & (ax <= hi + 1e-9)]


def dual_lengths(ax):
    """Length of the dual cell around each node (half spacing at the ends)."""
    d = np.diff(ax)
    out = np.zeros(len(ax))
    out[:-1] += d / 2
    out[1:] += d / 2
    return out


# ---------------------------------------------------------------------------
# Finite-difference electrostatic solver
# ---------------------------------------------------------------------------
class Laplace3D:
    """Electrostatics on a tensor grid (x, y, z in mm).

    `eps` is the relative permittivity per grid cell: either one value per z
    interval (layered media) or a full (nx-1, ny-1, nz-1) array.  `cond` is an
    int array of node labels: -1 free, >= 0 conductor id.  Each solve holds every
    conductor at the potential given for its id and returns the potential field
    and the charge (coulomb) on every conductor.
    """

    def __init__(self, xs, ys, zs, eps):
        self.xs, self.ys, self.zs = map(np.asarray, (xs, ys, zs))
        self.nx, self.ny, self.nz = len(xs), len(ys), len(zs)
        eps = np.asarray(eps, float)
        if eps.ndim == 1:
            assert len(eps) == self.nz - 1
            eps = np.broadcast_to(eps[None, None, :], (self.nx - 1, self.ny - 1, self.nz - 1))
        assert eps.shape == (self.nx - 1, self.ny - 1, self.nz - 1)
        self.eps = eps
        self.cond = -np.ones((self.nx, self.ny, self.nz), dtype=np.int32)
        self._L = None

    def idx(self):
        return np.arange(self.nx * self.ny * self.nz).reshape(self.nx, self.ny, self.nz)

    def laplacian(self):
        """Symmetric positive semi-definite matrix L with (L V)_n = Q_n / (eps0 * 1 mm).

        Edge coefficient = (sum over the four cells around the edge of eps * the
        part of the dual face lying in that cell) / edge length; nodes on the
        domain boundary simply have fewer cells (zero-flux Neumann)."""
        if self._L is not None:
            return self._L
        dx, dy, dz = np.diff(self.xs), np.diff(self.ys), np.diff(self.zs)
        hx = np.pad(dx / 2, 1)          # half widths of the cells either side of each node
        hy = np.pad(dy / 2, 1)
        hz = np.pad(dz / 2, 1)
        E = self.eps
        I = self.idx()
        rows, cols, vals = [], [], []
        # x edges: cells (i, j-1|j, k-1|k)
        P = np.pad(E, ((0, 0), (1, 1), (1, 1))) * hy[None, :, None] * hz[None, None, :]
        c = (P[:, :-1, :-1] + P[:, 1:, :-1] + P[:, :-1, 1:] + P[:, 1:, 1:]) / dx[:, None, None]
        rows.append(I[:-1].ravel()); cols.append(I[1:].ravel()); vals.append(c.ravel())
        # y edges: cells (i-1|i, j, k-1|k)
        P = np.pad(E, ((1, 1), (0, 0), (1, 1))) * hx[:, None, None] * hz[None, None, :]
        c = (P[:-1, :, :-1] + P[1:, :, :-1] + P[:-1, :, 1:] + P[1:, :, 1:]) / dy[None, :, None]
        rows.append(I[:, :-1].ravel()); cols.append(I[:, 1:].ravel()); vals.append(c.ravel())
        # z edges: cells (i-1|i, j-1|j, k)
        P = np.pad(E, ((1, 1), (1, 1), (0, 0))) * hx[:, None, None] * hy[None, :, None]
        c = (P[:-1, :-1] + P[1:, :-1] + P[:-1, 1:] + P[1:, 1:]) / dz[None, None, :]
        rows.append(I[:, :, :-1].ravel()); cols.append(I[:, :, 1:].ravel()); vals.append(c.ravel())
        r = np.concatenate(rows).astype(np.int64)
        cc = np.concatenate(cols).astype(np.int64)
        v = np.concatenate(vals)
        n = self.nx * self.ny * self.nz
        off = sp.coo_matrix((v, (r, cc)), shape=(n, n)).tocsr()
        off = off + off.T
        diag = np.asarray(off.sum(axis=1)).ravel()
        self._L = (sp.diags(diag) - off).tocsr()
        return self._L

    def solve(self, potentials_list, tol=1e-8, maxiter=4000, verbose=False):
        """Solve for each dict {cond_id: V} in potentials_list (ids not given are at 0 V).

        Returns (list of V fields, list of {cond_id: Q in coulomb})."""
        L = self.laplacian()
        flat = self.cond.ravel()
        free = np.flatnonzero(flat < 0)
        fixed = np.flatnonzero(flat >= 0)
        Lr = L[free]
        Lff = Lr[:, free].tocsr()
        Lfd = Lr[:, fixed].tocsr()
        ids = np.unique(flat[fixed])
        if pyamg is not None:
            # classical Ruge-Stuben AMG: ~10 CG iterations on these strongly anisotropic grids
            # (smoothed aggregation needs ~100 because of the thin board layers)
            ml = pyamg.ruge_stuben_solver(Lff, max_coarse=500)
            M = ml.aspreconditioner(cycle='V')
        else:
            M = spla.LinearOperator(Lff.shape, matvec=lambda x, d=1.0 / Lff.diagonal(): d * x)
        fields, charges = [], []
        for pots in potentials_list:
            vd = np.zeros(len(fixed))
            for cid, val in pots.items():
                vd[flat[fixed] == cid] = val
            b = -Lfd @ vd
            it = [0]

            def cb(_x):
                it[0] += 1
            x, info = spla.cg(Lff, b, rtol=tol, maxiter=maxiter, M=M, callback=cb)
            if info != 0:
                raise RuntimeError(f'CG did not converge (info {info})')
            V = np.zeros(L.shape[0])
            V[free] = x
            V[fixed] = vd
            q = L @ V                                            # eps0 * mm units
            qs = np.bincount(flat[fixed], weights=q[fixed], minlength=ids.max() + 1)
            charges.append({int(i): qs[i] * EPS0 * 1e-3 for i in ids})
            fields.append(V.reshape(self.nx, self.ny, self.nz))
            if verbose:
                print(f'      CG {it[0]} iterations, {len(free) / 1e6:.2f} M free nodes')
        return fields, charges


# ---------------------------------------------------------------------------
# Rasterising copper onto grid planes
# ---------------------------------------------------------------------------
def seg_mask(X, Y, x1, y1, x2, y2, r):
    """Nodes within r of the segment (a track with round ends)."""
    dx, dy = x2 - x1, y2 - y1
    l2 = dx * dx + dy * dy
    if l2 == 0:
        t = np.zeros_like(X)
    else:
        t = np.clip(((X - x1) * dx + (Y - y1) * dy) / l2, 0, 1)
    return (X - x1 - t * dx) ** 2 + (Y - y1 - t * dy) ** 2 <= r * r


def pad_mask(X, Y, pad, grow=0.0):
    """Nodes inside a pad (rect / roundrect / oval approximated by their rectangle,
    circles as discs)."""
    if pad['shape'] == 'circle':
        r = pad['w'] / 2 + grow
        return (X - pad['x']) ** 2 + (Y - pad['y']) ** 2 <= r * r
    th = math.radians(pad['rot'])
    u = (X - pad['x']) * math.cos(th) - (Y - pad['y']) * math.sin(th)
    v = (X - pad['x']) * math.sin(th) + (Y - pad['y']) * math.cos(th)
    return (np.abs(u) <= pad['w'] / 2 + grow) & (np.abs(v) <= pad['h'] / 2 + grow)


def poly_mask(X, Y, pts):
    return Path(pts).contains_points(np.column_stack([X.ravel(), Y.ravel()])).reshape(X.shape)
