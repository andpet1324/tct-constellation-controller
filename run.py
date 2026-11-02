"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Reading the HDF5 files written by the H5DataWriter satellite.
DAQ specific decoding lives in the subclasses
"""

import os
import pathlib
from abc import ABC, abstractmethod
import h5py
from typing import Any

class Run(ABC):
    """One run in an HDF5 file."""
    def __init__(self, path: pathlib.Path | str, daq: str, clear: bool = False) -> None:
        self.path = pathlib.Path(path)
        self._file = h5py.File(self.path, "r")
        self._daq = daq
        self._clear = clear
        if daq not in self._file:
            senders = list(self._file.keys())
            self.close()
            raise KeyError(f"No data of {daq} in {self.path}, senders: {senders}")

    @classmethod
    def from_run_id(cls, run_id: str, data_dir: pathlib.Path | str, daq: str, clear: bool = False) -> "Run":
        """Open the file the H5DataWriter creates for a run identifier"""
        return cls(pathlib.Path(data_dir) / f"data_{run_id}.h5", daq, clear=clear)

    def __enter__(self) -> "Run":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        self._file.close()
        if self._clear:
            self._delete_file()

    def _delete_file(self) -> None:
        if os.path.exists(self.path):
            os.remove(self.path)

    @property
    def _group(self) -> h5py.Group:
        """Group holding everything the DAQ sender wrote"""
        return self._file[self._daq]

    @property
    def bor_conf(self) -> dict[str, Any]:
        """Configuration of the DAQ satellite in the begin-of-run message"""
        return dict(self._group["BOR"]["configuration"].attrs)

    @property
    def bor_user(self) -> dict[str, Any]:
        """User tags of the begin-of-run message"""
        return dict(self._group["BOR"]["user_tags"].attrs)

    @property
    def eor(self) -> dict[str, Any]:
        """Run metadata of the end-of-run message, e.g. condition and time_end"""
        return dict(self._group["EOR"]["run_metadata"].attrs)

    def _data_groups(self) -> list[h5py.Group]:
        """Data record groups in acquisition order"""
        return [self._group[name] for name in sorted(k for k in self._group.keys() if k.startswith("data_"))]

    @staticmethod
    def _header(point: dict[str, Any], **extra: Any) -> dict[str, Any]:
        """Metadata for the csv"""
        return {
            "run_id": point["run_id"],
            **point["position"],
            "voltage": point.get("voltage"),
            "current": point.get("current"),
            "triggers": point.get("triggers"),
            **extra,
        }

    @staticmethod
    def _csv_path(output_path: pathlib.Path | str, point: dict[str, Any]) -> pathlib.Path:
        """Csv file of a run, creating the output directory"""
        output_path = pathlib.Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)
        return output_path / f"{point['run_id']}.csv"

    @abstractmethod
    def to_csv(self, output_path: pathlib.Path | str, point: dict[str, Any]) -> pathlib.Path:
        """Write the raw data of the run to a csv, return its path"""
