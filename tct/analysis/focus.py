"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Focus calibration: beam width from knife-edge scans in x at several z,
then the beam waist from the width as a function of z
"""

import pathlib
from collections import defaultdict
from typing import Any

import numpy
from scipy.optimize import curve_fit
from scipy.special import erf

from .h5 import scan_integrals


def knife_edge(x: numpy.ndarray, amplitude: float, x0: float, width: float, offset: float) -> numpy.ndarray:
    return offset + amplitude / 2 * (1 + erf(-numpy.sqrt(2) * (x - x0) / width))


def beam_width(z: numpy.ndarray, w0: float, z0: float, zr: float) -> numpy.ndarray:
    return w0 * numpy.sqrt(1 + ((z - z0) / zr) ** 2)


def fit_knife_edge(x: numpy.ndarray, signal: numpy.ndarray) -> numpy.ndarray:
    x = numpy.asarray(x, dtype=float)
    signal = numpy.asarray(signal, dtype=float)
    # Start values: edge at the point closest to half the signal range
    low, high = signal.min(), signal.max()
    x0 = x[numpy.argmin(numpy.abs(signal - (low + high) / 2))]
    p0 = [high - low, x0, (x.max() - x.min()) / 4, low]
    params, _ = curve_fit(knife_edge, x, signal, p0=p0)
    return params


def fit_beam_width(z: numpy.ndarray, widths: numpy.ndarray) -> numpy.ndarray:
    z = numpy.asarray(z, dtype=float)
    widths = numpy.asarray(widths, dtype=float)
    p0 = [widths.min(), z[numpy.argmin(widths)], (z.max() - z.min()) / 2]
    params, _ = curve_fit(beam_width, z, widths, p0=p0)
    return params


def analyse(manifest: dict[str, Any], data_dir: pathlib.Path | str, channel: int = 1) -> dict[str, Any]:
    """Beam width at every z of a focus scan and the waist from their z dependence.
    """
    points = scan_integrals(manifest, data_dir, channel)

    # Group the integrals into one knife-edge curve per z
    curves: dict[float, list[tuple[float, float]]] = defaultdict(list)
    for point in points:
        curves[point["position"]["z"]].append((point["position"]["x"], point["integral"]))

    result: dict[str, Any] = {"channel": channel, "z": [], "width": [], "edge_params": {}, "edge_fit_failed": []}
    for z in sorted(curves):
        xs, signal = zip(*sorted(curves[z]))
        try:
            params = fit_knife_edge(numpy.array(xs), numpy.array(signal))
        except RuntimeError:
            result["edge_fit_failed"].append(z)
            continue
        result["z"].append(z)
        result["width"].append(abs(params[2]))
        result["edge_params"][z] = params.tolist()

    if len(result["z"]) >= 3:
        try:
            result["waist_params"] = fit_beam_width(result["z"], result["width"]).tolist()
        except RuntimeError:
            result["waist_fit_failed"] = True
    else:
        result["waist_fit_failed"] = True

    return result


def plot(result: dict[str, Any], path: pathlib.Path | str) -> None:
    """Save the width against z with the beam width fit, as in the old calibration"""
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib.figure import Figure

    z = numpy.array(result["z"])
    widths = numpy.array(result["width"])

    fig = Figure()
    ax = fig.add_subplot(111)
    ax.plot(z, widths, "o", label="measured")
    if "waist_params" in result:
        w0, z0, zr = result["waist_params"]
        z_fit = numpy.linspace(z.min(), z.max(), 200)
        ax.plot(z_fit, beam_width(z_fit, w0, z0, zr), "-", label=f"fit: waist {w0:.4f} at z={z0:.3f}")
        ax.legend()
    ax.set_xlabel("z [mm]")
    ax.set_ylabel("beam width [mm]")
    ax.set_title("Focus calibration")
    fig.savefig(path)
