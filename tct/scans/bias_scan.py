"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Bias scan: one run per voltage, replacing BiasScanWorker
"""

import argparse
from typing import Any

import numpy
import pathlib

from ..controller import TCTController
from .common import add_common_arguments, bring_up, format_value, read_hv, reconfigure, save_manifest, data_directory, run_identifier
from ..prompts import readline_int, readline_dir
from ..menu_meta import SATELLITES


def bias_scan(
    ctrl: TCTController,
    voltages: list[float],
    triggers: int,
    results: list[dict[str, Any]] | None = None,
    data_dir: pathlib.Path | None = None,
    csv_dir: pathlib.Path | None = None,
) -> list[dict[str, Any]]:
    """Take a run at every voltage of the range.

    The range is (start, stop, step).
    """
    print(voltages)
    if results is None:
        results = []

    if not voltages:
        raise ValueError("Voltage range contains no points")

    for index, voltage in enumerate(voltages, start=1):
        ctrl.log.status(f"Voltage {index}/{len(voltages)}: {voltage}V")

        reconfigure(ctrl, SATELLITES["HV"], {"voltage": voltage})

        run_id = run_identifier("bias_scan")
        collected = ctrl.take_run(run_id, triggers)

        # The reading is the actual output, which may differ from the setpoint
        results.append({"run_id": run_id, "setpoint": voltage, "triggers": collected, **read_hv(ctrl, SATELLITES["HV"])})

    return results

def cmd_bias_scan(tgt: dict[str, any]) -> None:
    trgs = readline_int("Triggers", 1000)
    vi = readline_int("Start voltage", 0)
    vf = readline_int("Stop voltage", 100)
    vstep = readline_int("Voltage steps", 5)
    voltages = [float(v) for v in range(vi, vf, vstep)]
    csv_dir = readline_dir("data directory for csv (default is none)", None)
    data_dir = data_directory(tgt["cfg"], SATELLITES["WRITER"]) if csv_dir else None
    results = []
    settings = {"vrange": (vi, vf, vstep), "triggers": trgs}
    try:
        bias_scan(tgt["ctrl"], voltages, trgs, results, data_dir, csv_dir)
    except Exception as err:
        print(f"Bias scan interrupted with {err}")
    finally:
        path = save_manifest(data_dir, "bias_scan", settings, results)
        tgt["ctrl"].log.status(f"Manifest of {len(results)} points written to {path}")
        print("Bias scan ended")
        return


def main(args: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Bias voltage scan, one run per voltage")
    add_common_arguments(parser)
    # Default is that of the old bias scan dialog
    parser.add_argument("--v", type=float, nargs=3, default=(0.0, 101.0, 5.0), metavar=("START", "STOP", "STEP"))
    opts = parser.parse_args(args)

    ctrl = TCTController(opts.group)
    if not opts.no_launch:
        bring_up(ctrl, opts.config, SATELLITES)

    settings = {"vrange": opts.v, "triggers": opts.triggers}
    results: list[dict[str, Any]] = []
    try:
        bias_scan(ctrl, tuple(opts.v), opts.triggers, results)
    finally:
        path = save_manifest(opts.manifest, "bias_scan", settings, results)
        ctrl.log.status(f"Manifest of {len(results)} points written to {path}")


if __name__ == "__main__":
    main()
