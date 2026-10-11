"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Coverting existing HDF5 files written by the H5DataWriter satellite to csv
"""

import json
import pathlib
from collections.abc import Iterator
from typing import Any

from .analysis.h5 import Run

import numpy
import argparse


def main(args: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Manual translation, one run per position entered by the user")
    parser.add_argument("h5-data", type=pathlib.Path, nargs = ...)
    parser.add_argument("--data", type=pathlib.Path, default=None, required=True, help="Directory for csv data output")
    args = parser.parse_args(args)

    h5_data = args.h5_data
    csv_dir = args.data

    for data_dir in h5_data:
        run_id = str(data_dir).split(".")[0]
        try:
            with Run.from_run_id(run_id, data_dir) as run:
                print(f"Waveforms written to {run.to_csv(csv_dir)}")
        except Exception as err:
            print(f"Could not write {run_id} to csv: {err}")


if __name__ == "__main__":
    main()
