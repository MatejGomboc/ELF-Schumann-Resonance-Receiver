# SPDX-License-Identifier: CERN-OHL-W-2.0
"""Command-line interface: ``python -m elara {simulate,analyse,capture}``."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import __version__


def _cmd_simulate(args) -> int:
    from .io import default_metadata, write_wav
    from .simulate import simulate

    data, fs, truth = simulate(duration_s=args.duration, fs=args.fs, mains_hz=args.mains,
                               seed=args.seed)
    meta = default_metadata(fs, synthetic=True, truth=truth)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_wav(out, data, fs, subtype=args.subtype, metadata=meta)
    print(f"wrote {out} ({len(data) / fs:.1f} s @ {fs:.0f} Hz, "
          f"{len(truth['sferic_times_s'])} sferics) + {out.with_suffix('.json').name}")
    return 0


def _cmd_analyse(args) -> int:
    from .io import read_metadata
    from .pipeline import analyse_file, write_modes_csv, write_sferics_csv
    from .plots import plot_psd, plot_spectrogram

    path = Path(args.file)
    mains = args.mains or read_metadata(path).get("truth", {}).get("mains_hz_nominal", 50.0)
    t0 = time.perf_counter()
    res = analyse_file(path, mains_hz=mains, elf_rate=args.elf_rate,
                       resolution_hz=args.resolution, fmax=args.fmax,
                       cancel_mains=not args.no_mains, use_reference=not args.no_reference,
                       detect_sferics=not args.no_sferics)
    out_dir = Path(args.out_dir or path.parent)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = path.stem
    written = []
    for fmt in args.format:
        written.append(plot_psd(res, out_dir / f"{stem}_psd.{fmt}"))
        written.append(plot_spectrogram(res, out_dir / f"{stem}_spectrogram.{fmt}"))
    if res.fit is not None:
        write_modes_csv(out_dir / f"{stem}_modes.csv", res.fit)
        written.append(out_dir / f"{stem}_modes.csv")
    if not args.no_sferics:
        write_sferics_csv(out_dir / f"{stem}_sferics.csv", res.sferics)
        written.append(out_dir / f"{stem}_sferics.csv")

    print(f"analysed {path.name}: {res.duration_s:.1f} s @ {res.fs:.0f} Hz "
          f"in {time.perf_counter() - t0:.1f} s")
    if res.mains_tracked_hz is not None:
        print(f"  mains tracked at {res.mains_tracked_hz:.3f} Hz (nominal {mains:g} Hz)")
    if res.fit is not None:
        print("  mode   f [Hz]           HWHM [Hz]   Q      ASD [uV/rtHz]")
        for m in res.fit.modes:
            print(f"  SR{m.index}   {m.freq_hz:6.2f} ± {m.freq_err_hz:4.2f}    "
                  f"{m.width_hz:5.2f}      {m.q:5.1f}  {m.amplitude ** 0.5 * 1e6:6.2f}")
    else:
        print("  Schumann fit failed or disabled")
    if not args.no_sferics:
        print(f"  {len(res.sferics)} sferics detected")
    for p in written:
        print(f"  -> {p}")
    return 0


def _cmd_capture(args) -> int:
    try:
        from .io import Hdf5Writer, capture, default_metadata, list_devices, open_writer
        if args.list_devices:
            print(list_devices())
            return 0
        if not args.output:
            print("capture: an output file is required", file=sys.stderr)
            return 2
        device = int(args.device) if args.device and args.device.isdigit() else args.device
        meta = default_metadata(args.fs)
        with open_writer(args.output, args.fs, metadata=meta) as w:
            for ts, chunk in capture(fs=args.fs, device=device, duration_s=args.duration):
                if isinstance(w, Hdf5Writer):
                    w.write(chunk, ts)        # per-block timestamps
                else:
                    w.write(chunk)
    except (ImportError, OSError) as exc:
        print(f"capture unavailable: {exc}\n(install 'sounddevice' and PortAudio)",
              file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        pass
    print(f"wrote {args.output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="elara",
                                description="ELARA ELF receiver — capture and analysis tools")
    p.add_argument("--version", action="version", version=f"elara {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("simulate", help="write a synthetic recording (WAV + JSON sidecar)")
    s.add_argument("output")
    s.add_argument("--duration", type=float, default=30.0, help="seconds (default 30)")
    s.add_argument("--fs", type=float, default=192000.0, help="sample rate (default 192000)")
    s.add_argument("--mains", type=float, default=50.0, choices=(50.0, 60.0))
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--subtype", default="PCM_24", choices=("PCM_24", "FLOAT"))
    s.set_defaults(func=_cmd_simulate)

    a = sub.add_parser("analyse", aliases=["analyze"],
                       help="clean a recording, plot spectra and fit Schumann modes")
    a.add_argument("file")
    a.add_argument("--out-dir", help="output directory (default: next to the input)")
    a.add_argument("--mains", type=float, choices=(50.0, 60.0),
                   help="mains frequency (default: from metadata, else 50)")
    a.add_argument("--elf-rate", type=float, default=1000.0,
                   help="analysis sample rate after decimation (default 1000)")
    a.add_argument("--resolution", type=float, default=0.25,
                   help="PSD bin width for the fit [Hz] (default 0.25)")
    a.add_argument("--fmax", type=float, default=60.0, help="upper plot frequency [Hz]")
    a.add_argument("--format", nargs="+", default=["png"], choices=("png", "svg", "pdf"))
    a.add_argument("--no-mains", action="store_true", help="skip mains cancellation")
    a.add_argument("--no-reference", action="store_true",
                   help="skip noise-reference (R channel) subtraction")
    a.add_argument("--no-sferics", action="store_true", help="skip sferic detection")
    a.set_defaults(func=_cmd_analyse)

    c = sub.add_parser("capture", help="record from the S/PDIF audio interface")
    c.add_argument("output", nargs="?", help=".wav (24-bit + JSON sidecar) or .h5")
    c.add_argument("--duration", type=float, help="seconds (default: until Ctrl-C)")
    c.add_argument("--fs", type=float, default=192000.0)
    c.add_argument("--device", help="PortAudio device name or index")
    c.add_argument("--list-devices", action="store_true")
    c.set_defaults(func=_cmd_capture)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
