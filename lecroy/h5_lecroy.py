"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Reading the HDF5 files written by the H5DataWriter satellite
with LeCroy DAQ
"""

import json
import pathlib
import numpy
from collections.abc import Iterator
from typing import Any

from ..data.run import Run

def decode_record(payload: numpy.ndarray, channels: list[int], num_sequences: int) -> dict[int, numpy.ndarray]:
    """
        Split one LeCroy data record into the waveforms of every channel.
            #[trigger times (num_sequences)] [number of samples]
            #then per channel: [trigger offsets (num_sequences)] [samples (num_sequences * number of samples)]
        [number of samples]
        then per channel: [samples (num_sequences * number of samples)]

        Returns the samples per channel in volts, shaped (num_sequences, number of samples).
    """
    #index = num_sequences  # skip the trigger times
    num_samples = int(payload[0])
    index = 1

    #expected = num_sequences + 1 + len(channels) * (num_sequences + num_sequences * num_samples) 
    expected = 1 + num_sequences * num_samples * len(channels) 
    if payload.size != expected:
        raise ValueError(
            f"Record has {payload.size} words, expected {expected} for {len(channels)} channel(s), "
            f"{num_sequences} sequence(s) and {num_samples} samples"
        )

    waveforms = {}
    for channel in channels:
        #index += num_sequences  # skip the trigger offsets
        samples = payload[index : index + num_sequences * num_samples]
        waveforms[channel] = samples.reshape(num_sequences, num_samples)
        index += num_sequences * num_samples
    return waveforms

class LeCroyRun(Run):
    """One run in an HDF5 file, giving access to the oscilloscope waveforms."""
    SAMPLE_FORMAT = "%.6g"

    @property
    def channels(self) -> list[int]:
        """Oscilloscope channels contained in every record"""
        return [int(c) for c in str(self.bor_user["channels"]).split(",")]

    @property
    def num_sequences(self) -> int:
        return int(self.bor_user["num_sequences"])

    def records(self) -> Iterator[numpy.ndarray]:
        """Payload of every data record in order of their sequence number"""
        for record in self._data_groups():
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
        """Sum of samples of every waveform of a channel"""
        return self.waveforms(channel).sum(axis=1)

    def all_waveforms(self) -> dict[int, numpy.ndarray]:
        """All waveforms of every channel, each shaped (number of triggers, number of samples)"""
        channels = self.channels
        records = [decode_record(record, channels, self.num_sequences) for record in self.records()]
        all_samples: dict[int, list[numpy.ndarray]] = {channel: [] for channel in channels}
        for record in records:
            for channel, samples in record.items():
                all_samples[channel].append(samples)
        return {
            channel: numpy.concatenate(blocks) if blocks else numpy.empty((0, 0))
            for channel, blocks in all_samples.items()
        }

    def to_csv(self, output_path: pathlib.Path | str, point: dict[str, Any]) -> pathlib.Path:
        """Write the waveforms as one CSV, samples as rows and triggers as columns"""
        waveforms = self.all_waveforms()
        channels = sorted(channel for channel, traces in waveforms.items() if traces.size)
        if not channels:
            raise ValueError(f"Run {point['run_id']} holds no waveforms")

        num_samples = {waveforms[channel].shape[1] for channel in channels}
        if len(num_samples) != 1:
            raise ValueError(f"Channels of {point['run_id']} differ in length: {sorted(num_samples)}")

        names = ["sample"]
        columns = [numpy.arange(num_samples.pop())]
        for channel in channels:
            traces = waveforms[channel]
            names += [f"ch{channel}_{trigger}" for trigger in range(len(traces))]
            columns.append(traces.T)

        header = self._header(point, channels=channels)
        csv_path = self._csv_path(output_path, point)
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
