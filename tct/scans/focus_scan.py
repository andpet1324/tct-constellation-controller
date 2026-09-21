"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Focus calibration: knife-edge scan in x at several z, replacing CalibrateFocusWorker

Unlike the old worker, acquisition and analysis are separate steps: the scan
only takes data, the fits run afterwards on the files. A failed fit therefore
never loses the data, and the analysis can be repeated with --analyse-only.
"""

import argparse
import json
import pathlib
from typing import Any

from ..analysis import focus, load_manifest
from ..controller import TCTController
from .common import add_common_arguments, bring_up, save_manifest
from .motor_scan import SATELLITES, motor_scan


def main(args: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Focus calibration: knife-edge scans in x at several z")
    add_common_arguments(parser)
    parser.add_argument("--x", type=float, nargs=3, default=(0.0, 40.1, 1.0), metavar=("START", "STOP", "STEP"))
    parser.add_argument("--z", type=float, nargs=3, default=(0.0, 10.1, 1.0), metavar=("START", "STOP", "STEP"))
    parser.add_argument("--y", type=float, help="Fixed y position during the scan")
    parser.add_argument("--channel", type=int, default=1, help="Oscilloscope channel of the signal")
    parser.add_argument("--data-dir", type=pathlib.Path, required=True, help="output_directory of the H5DataWriter")
    parser.add_argument("--analyse-only", type=pathlib.Path, metavar="MANIFEST", help="Skip the scan, analyse this manifest")
    opts = parser.parse_args(args)


    if opts.analyse_only:
        manifest_path = opts.analyse_only
    else:
        ctrl = TCTController(opts.group)
        if not opts.no_launch:
            bring_up(ctrl, opts.config, SATELLITES)
        if opts.channel:
            ctrl.set_channels(opts.channel)

        # Get current y position. This should be known or aligned manually.
        if not opts.y:
            response = ctrl.command("position_y")
            opts.y = response.pos_y

        settings = {"xrange": opts.x, "y": opts.y, "zrange": opts.z, "triggers": opts.triggers, "channel": opts.channel}
        results: list[dict[str, Any]] = []
        try:
            motor_scan(ctrl, tuple(opts.x), (opts.y, opts.y + 0.5, 1.0), tuple(opts.z), opts.triggers, results)
        finally:
            manifest_path = save_manifest(opts.manifest, "focus_scan", settings, results)
            ctrl.log.status(f"Manifest of {len(results)} points written to {manifest_path}")

    result = focus.analyse(load_manifest(manifest_path), opts.data_dir, opts.channel)

    result_path = manifest_path.with_suffix("_focus.json")
    with open(result_path, "w") as f:
        json.dump(result, f, indent=2)
    if result["z"]:
        focus.plot(result, manifest_path.with_suffix("_focus.png"))

    if "waist_params" in result:
        w0, z0, zr = result["waist_params"]
        print(f"Beam waist {w0:.4f} mm at z = {z0:.3f} mm (Rayleigh length {zr:.3f} mm), see {result_path}")
    else:
        print(f"Waist fit failed, edge fits failed at z = {result['edge_fit_failed']}, see {result_path}")


if __name__ == "__main__":
    main()
