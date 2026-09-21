"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Synthetic end-to-end test of the analysis: fake H5DataWriter files -> focus fit.
Run with `python tests/synthetic_focus.py`, it writes the plot next to itself.
"""

import json
import pathlib
import sys
import tempfile

import h5py
import numpy
from scipy.special import erf

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from tct.analysis import Run, focus, load_manifest  # noqa: E402
from tct.scans.motor_scan import run_identifier  # noqa: E402

rng = numpy.random.default_rng(1)
tmp = pathlib.Path(tempfile.mkdtemp())
NSEQ, NSAMP, CHANNELS, NREC = 1, 200, [1, 2], 5
TRUE_W0, TRUE_Z0, TRUE_ZR, X0 = 0.8, 5.0, 3.0, 20.0


def write_run(run_id: str, level: float) -> None:
    with h5py.File(tmp / f"data_{run_id}.h5", "w") as f:
        f.create_group("H5DataWriter.Writer")
        scope = f.create_group("LeCroySatellite.Scope")
        scope.create_group("BOR/user_tags").attrs.update(
            {"channels": ",".join(map(str, CHANNELS)), "num_sequences": NSEQ, "trigger_delay": 0.0, "sampling_period": 1e-9}
        )
        scope.create_group("BOR/configuration")
        scope.create_group("EOR/run_metadata").attrs.update({"condition": "GOOD"})
        for seq in range(1, NREC + 1):
            payload = [numpy.zeros(NSEQ), [NSAMP]]  # trigger times, number of samples
            for ch in CHANNELS:
                wave = numpy.full(NSAMP, level if ch == 1 else 0.0) + rng.normal(0, 0.01, NSAMP)
                payload += [numpy.zeros(NSEQ), wave]  # trigger offsets, samples
            grp = scope.create_group(f"data_{seq:09}")
            grp.attrs["dtype"] = "float64"
            grp.create_dataset("block_00", data=numpy.concatenate([numpy.asarray(p, dtype=float) for p in payload]))


points = []
for z in numpy.arange(0.0, 10.1, 1.0):
    width = TRUE_W0 * numpy.sqrt(1 + ((z - TRUE_Z0) / TRUE_ZR) ** 2)
    for x in numpy.arange(15.0, 25.1, 0.5):
        level = 0.5 * (1 + erf(-numpy.sqrt(2) * (x - X0) / width))  # per-sample level -> integral = NSAMP * level
        pos = {"x": float(x), "y": 20.0, "z": float(z)}
        rid = run_identifier(pos)
        write_run(rid, level)
        points.append({"run_id": rid, "position": pos, "triggers": NREC})

manifest = tmp / "focus_scan.json"
manifest.write_text(json.dumps({"scan": "focus_scan", "settings": {}, "points": points}))

# Reader sanity
with Run.from_run_id(points[0]["run_id"], tmp) as run:
    print("channels", run.channels, "| waveforms", run.waveforms(1).shape, "| eor", run.eor)

result = focus.analyse(load_manifest(manifest), tmp, channel=1)
print("edge fits failed at z:", result["edge_fit_failed"])
print("widths:", numpy.round(result["width"], 3))
w0, z0, zr = result["waist_params"]
print(f"fit  w0={w0:.3f} z0={z0:.3f} zr={zr:.3f}")
print(f"true w0={TRUE_W0:.3f} z0={TRUE_Z0:.3f} zr={TRUE_ZR:.3f}")
plot_path = pathlib.Path(__file__).with_suffix(".png")
focus.plot(result, plot_path)
print("plot:", plot_path)
assert abs(w0 - TRUE_W0) < 0.05 and abs(z0 - TRUE_Z0) < 0.1 and abs(zr - TRUE_ZR) < 0.2
print("OK")
