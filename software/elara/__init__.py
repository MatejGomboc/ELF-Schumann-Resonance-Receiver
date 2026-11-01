# SPDX-License-Identifier: CERN-OHL-W-2.0
"""ELARA -- ELF Atmospheric Radio Analyser, PC-side software.

Modules
-------
frontend  analogue front-end model and hardware constants
io        WAV/FLAC/HDF5 reading and writing, live capture
dsp       streaming decimation, mains cancellation, noise-reference subtraction
analysis  PSD/spectrogram, Schumann-resonance fitting, sferic detection
simulate  synthetic recordings
pipeline  end-to-end processing of a recording
"""

__version__ = "0.1.0"
