"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Bias scan: one run per voltage, replacing BiasScanWorker
"""

import argparse
from typing import Any

import numpy

from ..controller import TCTController
from .common import add_common_arguments, bring_up, format_value, read_hv, reconfigure, save_manifest

STAGE = "Standa.Stage"
HV = "Keithley.HV"
SCOPE = "LeCroySatellite.Scope"
WRITER = "H5DataWriter.Writer"
SATELLITES = [STAGE, HV, SCOPE, WRITER]

def run_identifier(voltage: float) -> str:
    """Run identifier encoding the voltage, e.g. v-50p000 -> vm50p000"""
    return f"v{format_value(voltage)}"


def bias_scan(
    ctrl: TCTController,
    vrange: tuple[float, float, float],
    triggers: int,
    results: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Take a run at every voltage of the range.

    The range is (start, stop, step) as for numpy.arange. The Keithley ramps
    to each voltage in the steps configured for it and settles before the
    reconfigure returns. Entries are appended to `results` as they are taken.
    """
    if results is None:
        results = []

    voltages = [float(v) for v in numpy.arange(*vrange)]
    if not voltages:
        raise ValueError("Voltage range contains no points")

    for index, voltage in enumerate(voltages, start=1):
        ctrl.log.status(f"Voltage {index}/{len(voltages)}: {voltage}V")

        reconfigure(ctrl, HV, {"voltage": voltage})

        run_id = run_identifier(voltage)
        collected = ctrl.take_run(run_id, triggers)

        # The reading is the actual output, which may differ from the setpoint
        results.append({"run_id": run_id, "setpoint": voltage, "triggers": collected, **read_hv(ctrl, HV)})

    return results


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
