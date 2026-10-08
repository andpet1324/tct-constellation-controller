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
    """Split one Alibava data record into ...
    """

    print(payload)
    return payload
    #index = num_sequences  # skip the trigger times
    # num_samples = int(payload[0])
    # index = 1

    # #expected = num_sequences + 1 + len(channels) * (num_sequences + num_sequences * num_samples) 
    # expected = 1 + num_sequences * num_samples * len(channels) 
    # if payload.size != expected:
    #     raise ValueError(
    #         f"Record has {payload.size} words, expected {expected} for {len(channels)} channel(s), "
    #         f"{num_sequences} sequence(s) and {num_samples} samples"
    #     )

    # waveforms = {}
    # for channel in channels:
    #     #index += num_sequences  # skip the trigger offsets
    #     samples = payload[index : index + num_sequences * num_samples]
    #     waveforms[channel] = samples.reshape(num_sequences, num_samples)
    #     index += num_sequences * num_samples
    # return waveforms

class Run:
    """One run in an HDF5 file, giving access to the oscillodaq waveforms.
    """

    SAMPLE_FORMAT = "%.6g" # Ignor

    def __init__(self, path: pathlib.Path | str, daq: str = "Alibava.DAQ") -> None:
        self.path = pathlib.Path(path)
        self._file = h5py.File(self.path, "r")
        self._daq = daq
        if daq not in self._file:
            senders = list(self._file.keys())
            self._file.close()
            raise KeyError(f"No data of {daq} in {self.path}, senders: {senders}")

    @classmethod
    def from_run_id(cls, run_id: str, data_dir: pathlib.Path | str, daq: str = "Alibava.DAQ") -> "Run":
        """Open the file the H5DataWriter creates for a run identifier"""
        return cls(pathlib.Path(data_dir) / f"data_{run_id}.h5", daq)

    def __enter__(self) -> "Run":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        self._file.close()

    @property
    def bor(self) -> dict[str, Any]:
        """User tags of the begin-of-run message of the oscillodaq"""
        return dict(self._file[self._daq]["BOR"]["user_tags"].attrs)

    @property
    def eor(self) -> dict[str, Any]:
        """Run metadata of the end-of-run message, e.g. condition and time_end"""
        return dict(self._file[self._daq]["EOR"]["run_metadata"].attrs)

    # @property
    # def channels(self) -> list[int]:
    #     """Oscillodaq channels contained in every record"""
    #     return [int(c) for c in str(self.bor["channels"]).split(",")]

    @property
    def run_type(self) -> str:
        "DAQ run type, e.g. Pedestal or Laser"
        return str(self.bor["run_type"])

    @property
    def n_chips(self) -> int:
        "The number of active Beetle chips, either 1 or 2"
        return int(self.bor["nchips"])

    @property
    def chip_mask(self) -> list[int]:
        "The binary chip mask indicating which of the chips is active"
        return [int(c) for c in self.bor["chip_mask"]]

    @property
    def sample_size(self) -> int:
        "Sample_size of Alibava. We can't interrupt a run in between a sample size,"
        "so we set it low (1-10)."
        return self.bor["sample_size"]


    # @property
    # def num_sequences(self) -> int:
    #     return int(self.bor["num_sequences"])

    def records(self) -> Iterator[numpy.ndarray]:
        """Payload of every data record in order of their sequence number"""
        group = self._file[self._daq]
        for name in sorted(k for k in group.keys() if k.startswith("data_")):
            record = group[name]
            dtype = record.attrs.get("dtype", "float64")
            yield numpy.asarray(record["block_00"], dtype=dtype)

    # def waveforms(self, channel: int) -> numpy.ndarray:
    #     """All waveforms of a channel, shaped (number of triggers, number of samples)"""
    #     channels = self.channels
    #     if channel not in channels:
    #         raise ValueError(f"Channel {channel} not in run, available: {channels}")
    #     traces = [decode_record(record, channels, self.num_sequences)[channel] for record in self.records()]
    #     if not traces:
    #         return numpy.empty((0, 0))
    #     return numpy.concatenate(traces)

    # def integrals(self, channel: int) -> numpy.ndarray:
    #     """Sum of samples of every waveform of a channel.
    #     """
    #     return self.waveforms(channel).sum(axis=1)

    # def all_waveforms(self) -> dict[int, numpy.ndarray]:
    #     """All waveforms of every channel, each shaped (number of triggers, number of samples)"""
    #     channels = self.channels
    #     records = [decode_record(record, channels, self.num_sequences) for record in self.records()]
    #     all_samples: dict[int, list[numpy.ndarray]] = {channel: [] for channel in channels}
    #     for record in records:
    #         for channel, samples in record.items():
    #             all_samples[channel].append(samples)
    #     return {
    #         channel: numpy.concatenate(blocks) if blocks else numpy.empty((0, 0))
    #         for channel, blocks in all_samples.items()
    #     }

    def to_csv(self, output_path: pathlib.Path | str, point: dict[str, Any]) -> pathlib.Path:
        """Write the output data to csv"""

        n_chips = self.n_chips # use this to seperate per chip
        channels = [int(c) for c in range(len(self.bor["_data"]["beetle_0"]["mask"]))]
        records = [decode_record(n_chips, channels) for record in self.records()]

        # waveforms = self.all_waveforms()
        # channels = sorted(channel for channel, traces in waveforms.items() if traces.size)
        # if not channels:
        #     raise ValueError(f"Run {point['run_id']} holds no waveforms")

        # num_samples = {waveforms[channel].shape[1] for channel in channels}
        # if len(num_samples) != 1:
        #     raise ValueError(f"Channels of {point['run_id']} differ in length: {sorted(num_samples)}")

        names = ["sample"]
        columns = [numpy.arange(num_samples.pop())]
        for channel in channels:
            traces = waveforms[channel]
            names += [f"ch{channel}_{trigger}" for trigger in range(len(traces))]
            columns.append(traces.T)

        header = {
            "run_id": point["run_id"],
            **point["position"],
            "voltage": point.get("voltage"),
            "current": point.get("current"),
            "triggers": point.get("triggers"),
            "channels": channels,
        }

        output_path = pathlib.Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)
        csv_path = output_path / f"{point['run_id']}.csv"
        with open(csv_path, "w") as f:
            f.write(f"# {json.dumps(header, separators=(',', ':'))}\n")
            f.write(",".join(names) + "\n")
            numpy.savetxt(
                f,
                numpy.column_stack(columns),
                delimiter=",",
                fmt=["%d"] + [self.SAMPLE_FORMAT] * (len(names) - 1),
            )
        return csv_path


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
