# SPDX-License-Identifier: CERN-OHL-W-2.0
import csv

from elara.cli import main


def test_simulate_then_analyse(tmp_path, capsys):
    wav = tmp_path / "sim.wav"
    assert main(["simulate", str(wav), "--duration", "8", "--fs", "48000", "--seed", "3"]) == 0
    assert wav.exists() and (tmp_path / "sim.json").exists()
    out = tmp_path / "out"
    assert main(["analyse", str(wav), "--out-dir", str(out), "--format", "png", "svg"]) == 0
    for name in ("sim_psd.png", "sim_spectrogram.png", "sim_psd.svg", "sim_spectrogram.svg",
                 "sim_modes.csv", "sim_sferics.csv"):
        assert (out / name).stat().st_size > 0, name
    with open(out / "sim_modes.csv") as fh:
        rows = list(csv.DictReader(fh))
    assert [r["mode"] for r in rows] == [f"SR{i}" for i in range(1, 8)]
    assert abs(float(rows[0]["freq_hz"]) - 7.83) < 1.5
    text = capsys.readouterr().out
    assert "mains tracked at" in text and "sferics detected" in text


def test_capture_without_audio_hardware_fails_cleanly(tmp_path):
    # No PortAudio in CI: must report the problem, not raise.
    rc = main(["capture", str(tmp_path / "x.wav"), "--duration", "0.1"])
    assert rc in (0, 1)
