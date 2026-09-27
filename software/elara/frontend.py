# SPDX-License-Identifier: CERN-OHL-W-2.0
"""Analogue front-end model of the ELARA outdoor unit.

Every hardware constant the software relies on lives in :class:`FrontEnd`,
so a board revision only needs changing here.  The chain modelled is::

    antenna --[cap divider]--> LMP7721 (Rf||Cf, Rg+Cg) --[C_out/R_bias HPF]-->
    [R_AA/C_AA LPF] --> PCM1804 (5 Vpp differential full scale)

Sample values are ADC full-scale units (+/-1.0 == +/-2.5 V differential).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from scipy import signal

#: Nominal Schumann resonance mode frequencies [Hz].
SCHUMANN_MODES_HZ = (7.83, 14.3, 20.8, 27.3, 33.8, 39.0, 45.0)

#: Stereo channel roles as wired on the PCB (PCM1804 L / R).
CHANNEL_ROLES = ("antenna", "noise_reference")


@dataclass(frozen=True)
class FrontEnd:
    """Component values of the analogue signal chain (PLAN.md section 3)."""

    rf: float = 100e3          # preamp feedback resistor [ohm]
    cf: float = 15e-9          # preamp feedback capacitor [F]  -> 106 Hz pole
    rg: float = 1e3            # preamp ground-leg resistor [ohm]
    cg: float = 100e-6         # preamp ground-leg DC block [F] -> 1.6 Hz corner
    c_out: float = 10e-6       # output coupling capacitor [F]
    r_bias: float = 47e3       # ADC-side bias resistor [ohm]   -> 0.34 Hz corner
    r_aa: float = 10e3         # anti-alias resistor [ohm]
    c_aa: float = 100e-9       # anti-alias capacitor [F]      -> 159 Hz pole
    divider: float = 0.583     # antenna / input-filter capacitive divider (-4.7 dB)
    adc_fs_vpk: float = 2.5    # PCM1804 full scale, differential peak [V]
    #: PCM1804 on-chip DC-removal HPF corner [Hz] (fs/48000 when enabled);
    #: ``None`` means the BYPAS pin disables it.
    adc_hpf_hz: float | None = None

    # -- derived quantities -------------------------------------------------
    @property
    def midband_gain(self) -> float:
        """Preamp gain in the flat part of the ELF band (1 + Rf/Rg)."""
        return 1.0 + self.rf / self.rg

    def corners_hz(self) -> dict[str, float]:
        """Corner frequencies of the individual first-order sections."""
        tw = 2 * np.pi
        return {
            "preamp_lf_hz": 1 / (tw * self.rg * self.cg),
            "preamp_hf_hz": 1 / (tw * self.rf * self.cf),
            "coupling_hpf_hz": 1 / (tw * self.c_out * self.r_bias),
            "anti_alias_hz": 1 / (tw * self.r_aa * self.c_aa),
        }

    def as_dict(self) -> dict:
        d = asdict(self)
        d.update(self.corners_hz(), midband_gain=self.midband_gain)
        return d

    def zpk_s(self) -> tuple[np.ndarray, np.ndarray, float]:
        """Analogue transfer function antenna volts -> ADC full-scale units.

        Returns ``(b, a, _)`` polynomial coefficients in *s* (highest power first).
        """
        tf, tg = self.rf * self.cf, self.rg * self.cg
        # Non-inverting stage: G = 1 + Zf/Zg = 1 + s Rf Cg / ((1+s tf)(1+s tg))
        den_pre = np.polymul([tf, 1.0], [tg, 1.0])
        num_pre = np.polyadd(den_pre, [self.rf * self.cg, 0.0])
        to = self.c_out * self.r_bias
        b = np.polymul(num_pre, [to, 0.0])                   # coupling HPF zero at DC
        a = np.polymul(den_pre, [to, 1.0])
        a = np.polymul(a, [self.r_aa * self.c_aa, 1.0])      # anti-alias pole
        if self.adc_hpf_hz:
            ta = 1 / (2 * np.pi * self.adc_hpf_hz)
            b, a = np.polymul(b, [ta, 0.0]), np.polymul(a, [ta, 1.0])
        k = self.divider / self.adc_fs_vpk
        return b * k, a, k

    def response(self, f) -> np.ndarray:
        """Complex response H(f) from antenna voltage to ADC full-scale units."""
        b, a, _ = self.zpk_s()
        return signal.freqs(b, a, worN=2 * np.pi * np.asarray(f, dtype=float))[1]

    def to_antenna_psd(self, f, psd, f_min: float = 0.5) -> np.ndarray:
        """Refer a PSD in FS^2/Hz at the ADC to V^2/Hz at the antenna.

        ``psd`` has frequency along axis 0 (a spectrogram (f, t) works too).
        Bins below ``f_min``, where the high-pass sections make the inverse
        meaningless, are set to NaN.
        """
        f = np.asarray(f, dtype=float)
        psd = np.asarray(psd, dtype=float)
        h2 = np.abs(self.response(f)) ** 2
        h2 = np.where(f < f_min, np.nan, h2).reshape((-1,) + (1,) * (psd.ndim - 1))
        return psd / h2

    def correction_sos(self, fs: float, f_min: float = 0.2, f_max: float | None = None):
        """Digital IIR (second-order sections) equalising the front-end.

        The exact inverse has poles at DC and at infinity, so it is regularised:
        high-pass zeros at DC are moved to ``f_min`` and the inverted low-pass
        poles are rolled off again at ``f_max`` (default ``0.4 * fs``).  Within
        ``f_min << f << f_max`` the filtered output is in antenna volts.
        """
        f_max = 0.4 * fs if f_max is None else f_max
        b, a, _ = self.zpk_s()
        z, p, k = signal.tf2zpk(b, a)
        w_min, w_max = 2 * np.pi * f_min, 2 * np.pi * f_max
        # Inverse: swap zeros and poles.  All front-end zeros are real, so the
        # inverse poles are clamped into [f_min, f_max] and padded with HF poles.
        inv_z = p
        inv_p = -np.clip(np.abs(z), w_min, w_max)
        n_extra = len(inv_z) - len(inv_p)
        inv_p = np.concatenate([inv_p, np.full(n_extra, -w_max)])
        # Normalise gain so that |H_fe * H_inv| = 1 at a mid-band reference.
        f_ref = np.sqrt(8.0 * 30.0)
        s_ref = 2j * np.pi * f_ref
        h_inv = np.prod(s_ref - inv_z) / np.prod(s_ref - inv_p)
        gain = 1.0 / np.abs(self.response(f_ref) * h_inv)
        zd, pd, kd = signal.bilinear_zpk(inv_z, inv_p, gain, fs)
        return signal.zpk2sos(zd, pd, kd)


DEFAULT_FRONTEND = FrontEnd()
