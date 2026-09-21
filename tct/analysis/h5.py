"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Reading the HDF5 files written by the H5DataWriter satellite
"""

import json
import pathlib
from collections.abc import Iterator
from typing import Any

import h5py
import numpy


def decode_record(payload: numpy.ndarray, channels: list[int], num_sequences: int) -> dict[int, numpy.ndarray]:
    """Split one LeCroy data record into the waveforms of every channel.

    The LeCroy satellite packs a record as double precision floats:

        [trigger times (num_sequences)] [number of samples]
        then per channel: [trigger offsets (num_sequences)] [samples (num_sequences * number of samples)]

    Returns the samples per channel in volts, shaped (num_sequences, number of samples).
    """
    index = num_sequences  # skip the trigger times
    num_samples = int(payload[index])
    index += 1

    expected = num_sequences + 1 + len(channels) * (num_sequences + num_sequences * num_samples)
    if payload.size != expected:
        raise ValueError(
            f"Record has {payload.size} words, expected {expected} for {len(channels)} channel(s), "
            f"{num_sequences} sequence(s) and {num_samples} samples"
        )

    waveforms = {}
    for channel in channels:
        index += num_sequences  # skip the trigger offsets
        samples = payload[index : index + num_sequences * num_samples]
        waveforms[channel] = samples.reshape(num_sequences, num_samples)
        index += num_sequences * num_samples
    return waveforms


class Run:
    """One run in an HDF5 file, giving access to the oscilloscope waveforms.

    Use as a context manager, the file is closed on exit.
    """

    def __init__(self, path: pathlib.Path | str, scope: str = "LeCroySatellite.Scope") -> None:
        self.path = pathlib.Path(path)
        self._file = h5py.File(self.path, "r")
        self._scope = scope
        if scope not in self._file:
            raise KeyError(f"No data of {scope} in {self.path}, senders: {list(self._file.keys())}")

    @classmethod
    def from_run_id(cls, run_id: str, data_dir: pathlib.Path | str, scope: str = "LeCroySatellite.Scope") -> "Run":
        """Open the file the H5DataWriter creates for a run identifier"""
        return cls(pathlib.Path(data_dir) / f"data_{run_id}.h5", scope)

    def __enter__(self) -> "Run":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        self._file.close()

    @property
    def bor(self) -> dict[str, Any]:
        """User tags of the begin-of-run message of the oscilloscope"""
        return dict(self._file[self._scope]["BOR"]["user_tags"].attrs)

    @property
    def eor(self) -> dict[str, Any]:
        """Run metadata of the end-of-run message, e.g. condition and time_end"""
        return dict(self._file[self._scope]["EOR"]["run_metadata"].attrs)

    @property
    def channels(self) -> list[int]:
        """Oscilloscope channels contained in every record"""
        return [int(c) for c in str(self.bor["channels"]).split(",")]

    @property
    def num_sequences(self) -> int:
        return int(self.bor["num_sequences"])

    def records(self) -> Iterator[numpy.ndarray]:
        """Payload of every data record in order of their sequence number"""
        group = self._file[self._scope]
        for name in sorted(k for k in group.keys() if k.startswith("data_")):
            record = group[name]
            dtype = record.attrs.get("dtype", "float64")
            yield numpy.asarray(record["block_00"], dtype=dtype)

    def waveforms(self, channel: int) -> numpy.ndarray:
        """All waveforms of a channel, shaped (number of triggers, number of samples)"""
        channels = self.channels
        if channel not in channels:
            raise ValueError(f"Channel {channel} not in run, available: {channels}")
        traces = [decode_record(record, channels, self.num_sequences)[channel] for record in self.records()]
        if not traces:
            return numpy.empty((0, 0))
        return numpy.concatenate(traces)

    def integrals(self, channel: int) -> numpy.ndarray:
        """Sum of samples of every waveform of a channel.
        """
        return self.waveforms(channel).sum(axis=1)


def load_manifest(path: pathlib.Path | str) -> dict[str, Any]:
    """Load the JSON manifest written by a scan script"""
    with open(path) as f:
        return json.load(f)


def scan_integrals(
    manifest: dict[str, Any], data_dir: pathlib.Path | str, channel: int
) -> list[dict[str, Any]]:
    """Mean and standard deviation of the integral at every point of a scan.

    Returns the manifest points with `integral`, `integral_std` and `num_waveforms`
    added. Points whose file is missing are skipped with a warning printed, so
    that an interrupted scan can still be analysed.
    """
    results = []
    for point in manifest["points"]:
        try:
            with Run.from_run_id(point["run_id"], data_dir) as run:
                integrals = run.integrals(channel)
        except (FileNotFoundError, KeyError) as err:
            print(f"Skipping {point['run_id']}: {err}")
            continue
        results.append(
            {
                **point,
                "integral": float(integrals.mean()) if integrals.size else float("nan"),
                "integral_std": float(integrals.std()) if integrals.size else float("nan"),
                "num_waveforms": int(integrals.size),
            }
        )
    return results
