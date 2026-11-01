# SPDX-License-Identifier: CERN-OHL-W-2.0
import numpy as np
from scipy import signal

from elara.frontend import FrontEnd


def test_midband_gain_and_corners():
    fe = FrontEnd()
    c = fe.corners_hz()
    assert np.isclose(c["preamp_lf_hz"], 1.59, atol=0.01)
    assert np.isclose(c["coupling_hpf_hz"], 0.34, atol=0.01)
    assert np.isclose(c["preamp_hf_hz"], 106.1, atol=0.1)
    assert np.isclose(c["anti_alias_hz"], 159.2, atol=0.1)
    # Mid-band: antenna volts -> preamp output volts is divider * 101.
    g = np.abs(fe.response(15.0)) * fe.adc_fs_vpk / fe.divider
    assert abs(20 * np.log10(g / 101)) < 0.3
    # Response rolls off at both ends.
    assert np.abs(fe.response(0.05)) < 0.05 * np.abs(fe.response(15.0))
    assert np.abs(fe.response(1000.0)) < 0.05 * np.abs(fe.response(15.0))


def test_correction_filter_flattens_elf_band():
    fe = FrontEnd()
    fs = 1000.0
    sos = fe.correction_sos(fs)
    f = np.linspace(2.0, 50.0, 50)
    _, h = signal.sosfreqz(sos, worN=f, fs=fs)
    err_db = 20 * np.log10(np.abs(h * fe.response(f)))
    assert np.max(np.abs(err_db)) < 0.2


def test_to_antenna_psd_inverts_response():
    fe = FrontEnd()
    f = np.array([0.1, 5.0, 20.0])
    psd = np.abs(fe.response(f)) ** 2 * 1e-12
    out = fe.to_antenna_psd(f, psd)
    assert np.isnan(out[0])
    assert np.allclose(out[1:], 1e-12)
