# SPDX-License-Identifier: CERN-OHL-W-2.0
"""
Small Kirchhoff-plate finite-element solver for ELARA's mechanical checks.

Element: Bogner-Fox-Schmit (BFS) conforming rectangle, bicubic Hermite,
4 nodes x 4 DOF (w, w_x, w_y, w_xy).  The mesh is a tensor grid with
non-uniform spacing, so mesh lines can be put on holes, wall faces and stud
positions.  Per-element bending stiffness D and areal mass rho*h, lumped point
masses, point / patch supports (pinned or clamped) and linear constraints
(penalty) are supported; holes in the plates are ignored (small).

Units: SI (m, kg, N, Pa).  Grid coordinates are given in metres.
"""

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as sla

GAUSS_X, GAUSS_W = np.polynomial.legendre.leggauss(4)
GAUSS_X = 0.5 * (GAUSS_X + 1.0)
GAUSS_W = 0.5 * GAUSS_W


def axis(length, h, required=()):
    """Grid coordinates 0..length with spacing <= h through every required point."""
    pts = sorted(set([0.0, length] + [p for p in required if 0.0 < p < length]))
    out = [pts[0]]
    for a, b in zip(pts[:-1], pts[1:]):
        n = max(1, int(np.ceil((b - a) / h - 1e-9)))
        out += list(np.linspace(a, b, n + 1)[1:])
    return np.array(out)


def _hermite(xi, a):
    """1D cubic Hermite functions on an interval of length a: value, d/dx, d2/dx2.
    Order: [w(0), w'(0), w(1), w'(1)]."""
    N = np.array([1 - 3 * xi**2 + 2 * xi**3, a * (xi - 2 * xi**2 + xi**3),
                  3 * xi**2 - 2 * xi**3, a * (-xi**2 + xi**3)])
    dN = np.array([(-6 * xi + 6 * xi**2) / a, 1 - 4 * xi + 3 * xi**2,
                   (6 * xi - 6 * xi**2) / a, -2 * xi + 3 * xi**2])
    d2N = np.array([(-6 + 12 * xi) / a**2, (-4 + 6 * xi) / a,
                    (6 - 12 * xi) / a**2, (-2 + 6 * xi) / a])
    return N, dN, d2N


# element node order (p, q) and, per node, which 1D function (value 0 / slope 1)
# is used in x and y for the DOFs w, w_x, w_y, w_xy
_CORNERS = [(0, 0), (1, 0), (1, 1), (0, 1)]
_DOFKIND = [(0, 0), (1, 0), (0, 1), (1, 1)]


def _shape(xi, eta, a, b):
    """N (16,), B (3, 16) = [w_xx, w_yy, 2 w_xy] rows at one point."""
    X = _hermite(xi, a)
    Y = _hermite(eta, b)
    N = np.zeros(16)
    B = np.zeros((3, 16))
    k = 0
    for (p, q) in _CORNERS:
        for (sx, sy) in _DOFKIND:
            ix, iy = 2 * p + sx, 2 * q + sy
            N[k] = X[0][ix] * Y[0][iy]
            B[0, k] = X[2][ix] * Y[0][iy]
            B[1, k] = X[0][ix] * Y[2][iy]
            B[2, k] = 2 * X[1][ix] * Y[1][iy]
            k += 1
    return N, B


class Plate:
    """Rectangular plate on a tensor grid xs (nx,) x ys (ny,) [m]."""

    def __init__(self, xs, ys, D, rho_h, nu):
        self.xs, self.ys, self.nu = np.asarray(xs), np.asarray(ys), nu
        self.nx, self.ny = len(xs), len(ys)
        self.nn = self.nx * self.ny
        self.ndof = 4 * self.nn
        ex = 0.5 * (self.xs[:-1] + self.xs[1:])
        ey = 0.5 * (self.ys[:-1] + self.ys[1:])
        self.ecx, self.ecy = np.meshgrid(ex, ey)          # element centres (ney, nex)
        self.D = np.broadcast_to(np.asarray(D(self.ecx, self.ecy) if callable(D) else D, float),
                                 self.ecx.shape).copy()
        self.rho_h = np.broadcast_to(np.asarray(rho_h(self.ecx, self.ecy) if callable(rho_h) else rho_h,
                                                float), self.ecx.shape).copy()
        self.point_mass = np.zeros(self.nn)
        self.fixed = set()
        self.penalties = []          # list of (dofs, coeffs)
        self.springs = []            # (dof, k) grounded springs

    # ---------------------------------------------------------------- helpers
    def node(self, i, j):
        return j * self.nx + i

    def nearest(self, x, y):
        i = int(np.argmin(np.abs(self.xs - x)))
        j = int(np.argmin(np.abs(self.ys - y)))
        return self.node(i, j)

    def node_xy(self):
        X, Y = np.meshgrid(self.xs, self.ys)
        return X.ravel(), Y.ravel()

    def nodes_in(self, pred):
        X, Y = self.node_xy()
        return np.nonzero(pred(X, Y))[0]

    def area_weights(self):
        """Nodal tributary areas (trapezoid rule) -- for area averages."""
        wx = np.zeros(self.nx)
        dx = np.diff(self.xs)
        wx[:-1] += dx / 2
        wx[1:] += dx / 2
        wy = np.zeros(self.ny)
        dy = np.diff(self.ys)
        wy[:-1] += dy / 2
        wy[1:] += dy / 2
        return np.outer(wy, wx).ravel()

    # ---------------------------------------------------------------- supports
    def fix(self, nodes, dofs=(0, 1, 2, 3)):
        for n in np.atleast_1d(nodes):
            for d in dofs:
                self.fixed.add(4 * int(n) + d)

    def pin(self, nodes):
        self.fix(nodes, (0,))

    def clamp(self, nodes):
        self.fix(nodes, (0, 1, 2, 3))

    def add_mass(self, x, y, m):
        self.point_mass[self.nearest(x, y)] += m

    def add_constraint(self, dofs, coeffs):
        """Linear constraint sum(c_i u_i) = 0, enforced by a penalty."""
        self.penalties.append((np.asarray(dofs, int), np.asarray(coeffs, float)))

    def rigid_link(self, nodes):
        """Tie nodes to one rigid body (w plane + common slopes), as for a stiff unit
        bolted at its studs with moment-carrying joints."""
        X, Y = self.node_xy()
        n0 = nodes[0]
        # a rigid body has w = w0 + tx (x - x0) + ty (y - y0), w_x = tx, w_y = ty
        # use node 0's w, w_x, w_y as the master DOFs
        for n in nodes:
            dx, dy = X[n] - X[n0], Y[n] - Y[n0]
            if n != n0:
                self.add_constraint([4 * n, 4 * n0, 4 * n0 + 1, 4 * n0 + 2], [1, -1, -dx, -dy])
                self.add_constraint([4 * n + 1, 4 * n0 + 1], [1, -1])
                self.add_constraint([4 * n + 2, 4 * n0 + 2], [1, -1])

    # ---------------------------------------------------------------- assembly
    def _unit_mats(self, a, b):
        key = (round(a * 1e7), round(b * 1e7))
        if not hasattr(self, "_cache"):
            self._cache = {}
        if key not in self._cache:
            nu = self.nu
            Dm = np.array([[1, nu, 0], [nu, 1, 0], [0, 0, (1 - nu) / 2]])
            K = np.zeros((16, 16))
            M = np.zeros((16, 16))
            for xi, wx in zip(GAUSS_X, GAUSS_W):
                for eta, wy in zip(GAUSS_X, GAUSS_W):
                    N, B = _shape(xi, eta, a, b)
                    w = wx * wy * a * b
                    K += w * B.T @ Dm @ B
                    M += w * np.outer(N, N)
            Nc, Bc = _shape(0.5, 0.5, a, b)
            self._cache[key] = (K, M, Bc)
        return self._cache[key]

    def _edofs(self, i, j):
        ns = [self.node(i, j), self.node(i + 1, j), self.node(i + 1, j + 1), self.node(i, j + 1)]
        return np.array([4 * n + k for n in ns for k in range(4)])

    def assemble(self):
        rows, cols, kv, mv = [], [], [], []
        for j in range(self.ny - 1):
            b = self.ys[j + 1] - self.ys[j]
            for i in range(self.nx - 1):
                a = self.xs[i + 1] - self.xs[i]
                Ku, Mu, _ = self._unit_mats(a, b)
                ed = self._edofs(i, j)
                r = np.repeat(ed, 16)
                c = np.tile(ed, 16)
                rows.append(r)
                cols.append(c)
                kv.append((self.D[j, i] * Ku).ravel())
                mv.append((self.rho_h[j, i] * Mu).ravel())
        rows = np.concatenate(rows)
        cols = np.concatenate(cols)
        K = sp.coo_matrix((np.concatenate(kv), (rows, cols)), shape=(self.ndof, self.ndof)).tocsr()
        M = sp.coo_matrix((np.concatenate(mv), (rows, cols)), shape=(self.ndof, self.ndof)).tocsr()
        pm = np.zeros(self.ndof)
        pm[0::4] = self.point_mass
        M = M + sp.diags(pm)
        if self.penalties or self.springs:
            alpha = 1e4 * K.diagonal().max()
            pr, pc, pv = [], [], []
            for dofs, c in self.penalties:
                # scale slope-type DOFs consistently: constraints are mixed, keep simple
                pr.append(np.repeat(dofs, len(dofs)))
                pc.append(np.tile(dofs, len(dofs)))
                pv.append(alpha * np.outer(c, c).ravel())
            for d, k in self.springs:
                pr.append([d])
                pc.append([d])
                pv.append([k])
            K = K + sp.coo_matrix((np.concatenate(pv), (np.concatenate(pr), np.concatenate(pc))),
                                  shape=K.shape).tocsr()
        self.K, self.M = K, M
        self.free = np.array(sorted(set(range(self.ndof)) - self.fixed))
        return K, M

    def rigid_vector(self):
        """Unit normal translation (w = 1, slopes 0)."""
        r = np.zeros(self.ndof)
        r[0::4] = 1.0
        return r

    # ---------------------------------------------------------------- solvers
    def modes(self, n=6, shift=None):
        if not hasattr(self, "K"):
            self.assemble()
        f = self.free
        Kf = self.K[f][:, f]
        Mf = self.M[f][:, f]
        if shift is None:
            shift = -1.0 if len(self.fixed) == 0 else 0.0
        lam, vec = sla.eigsh(Kf, k=n, M=Mf, sigma=shift, which="LM",
                             v0=np.ones(Kf.shape[0]))   # fixed start vector: reproducible
        order = np.argsort(lam)
        lam, vec = lam[order], vec[:, order]
        phi = np.zeros((self.ndof, n))
        phi[f] = vec                                    # mass-normalised
        freq = np.sqrt(np.clip(lam, 0, None)) / (2 * np.pi)
        return freq, phi

    def static_accel(self, a=1.0):
        """Static deflection under a uniform normal acceleration a [m/s^2] (relative
        to the supports): K u = -M r a.  Returns the full DOF vector."""
        if not hasattr(self, "K"):
            self.assemble()
        f = self.free
        F = -(self.M @ self.rigid_vector()) * a
        u = np.zeros(self.ndof)
        u[f] = sla.spsolve(self.K[f][:, f].tocsc(), F[f])
        return u

    def w_grid(self, u):
        return u[0::4].reshape(self.ny, self.nx)

    def curvatures(self, u):
        """[k_xx, k_yy, 2 k_xy] at element centres (3, ney, nex)."""
        out = np.zeros((3, self.ny - 1, self.nx - 1))
        for j in range(self.ny - 1):
            b = self.ys[j + 1] - self.ys[j]
            for i in range(self.nx - 1):
                a = self.xs[i + 1] - self.xs[i]
                _, _, Bc = self._unit_mats(a, b)
                out[:, j, i] = Bc @ u[self._edofs(i, j)]
        return out

    def stress_vm(self, u, E, t):
        """Surface von Mises stress at element centres for a homogeneous plate."""
        k = self.curvatures(u)
        c = E * (t / 2) / (1 - self.nu**2)
        sx = c * (k[0] + self.nu * k[1])
        sy = c * (k[1] + self.nu * k[0])
        txy = E * (t / 2) / (2 * (1 + self.nu)) * k[2]
        return np.sqrt(sx**2 + sy**2 - sx * sy + 3 * txy**2)


def flex_rigidity(E, t, nu):
    return E * t**3 / (12 * (1 - nu**2))


def _selftest():
    """Compare with classical results (Leissa 1969, nu = 0.3): square plate side a,
    lambda = omega a^2 sqrt(rho h / D)."""
    a, h = 1.0, 1 / 24
    E, nu, t, rho = 1.0, 0.3, 0.01, 1.0
    D = flex_rigidity(E, t, nu)
    xs = ys = axis(a, h)
    res = {}
    for name, ref in (("SSSS", 19.739), ("CCCC", 35.99), ("FFFF", 13.47), ("corner points", 7.12)):
        p = Plate(xs, ys, D, rho * t, nu)
        edge = p.nodes_in(lambda X, Y: (X < 1e-9) | (X > a - 1e-9) | (Y < 1e-9) | (Y > a - 1e-9))
        if name == "SSSS":
            p.pin(edge)
        elif name == "CCCC":
            p.clamp(edge)
        elif name == "corner points":
            p.pin([p.nearest(0, 0), p.nearest(a, 0), p.nearest(0, a), p.nearest(a, a)])
        f, _ = p.modes(8)
        lam = 2 * np.pi * f * a**2 * np.sqrt(rho * t / D)
        lam = lam[lam > 1e-3]
        res[name] = (float(lam[0]), ref)
    return res


if __name__ == "__main__":
    for k, (v, r) in _selftest().items():
        print(f"{k:14s} lambda = {v:7.3f}  (Leissa {r})")
