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
import pandas

CHANNELS = 128

# ADD RUNTYPE
def decode_record(payload: numpy.ndarray) -> numpy.ndarray:
    """Split one Alibava data record into ...

       Each record contains a data block of 256 words, with value ADC count and SOMETHING?.
    """

    #
    # The data comes in pairs of two:
    #       (val1, val2)
    # The stored value by Alibava is uint16, meaning it has the max value of 256x256
    # which corresponds to (0,256) = 0*256 + 256*256. Therefore val1 is the least 
    # significant value. 
    #
    adc = payload[0::2] + payload[1::2] * 256 # size 128

    return adc

class Run:

    """One run in an HDF5 file, giving access to the adc data.
    """

    SAMPLE_FORMAT = "%.9g" # Ignore

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
    def bor_conf(self) -> dict[str, Any]:
        """User tags of the begin-of-run message of the Alibava"""
        return dict(self._file[self._daq]["BOR"]["configuration"].attrs)

    @property
    def bor_user(self) -> dict[str, Any]:
        """User tags of the begin-of-run message of the Alibava"""
        return dict(self._file[self._daq]["BOR"]["user_tags"].attrs)

    @property
    def eor(self) -> dict[str, Any]:
        """Run metadata of the end-of-run message, e.g. condition and time_end"""
        return dict(self._file[self._daq]["EOR"]["run_metadata"].attrs)

    @property
    def channels(self) -> numpy.ndarray[int]:
        """Channels contained in every record. It is hardcoded"""
        return numpy.arange(CHANNELS)

    @property
    def run_type(self) -> str:
        "DAQ run type, e.g. Pedestal or Laser"
        return str(self.bor_user["run_type"])

    @property
    def n_chips(self) -> int:
        "The number of active Beetle chips, either 1 or 2"
        return int(self.bor_user["nchips"])

    @property
    def chip_mask(self) -> list[int]:
        "The binary chip mask indicating which of the chips is active"
        return [int(c) for c in self.bor_user["chip_mask"]]

    @property
    def sample_size(self) -> int:
        "Sample_size of Alibava. We can't interrupt a run in between a sample size,"
        "so we set it low (1-10)."
        return self.bor_conf["sample_size"]

    @property
    def num_records(self) -> int:
        "Records collected"
        return self.eor["data_records"]

    def records(self, chip : int) -> Iterator[numpy.ndarray]:
        """Payload of every data record. Should be as many payloads as triggers"""
        group = self._file[self._daq]
        for name in sorted(k for k in group.keys() if k.startswith("data_")):
            record = group[name]
            dtype = record.attrs.get("dtype", "float64")
            block = "block_0" + str(1 + 2*chip)
            yield numpy.asarray(record[block], dtype=dtype)

    def adc(self, chip: int) -> numpy.ndarray:
        """
        Returns an array with the adc values per chip for all records, 
        shaped (number of records, number of channels)
        """
        # channels = self.channels * (1 + chip)
        counts = [decode_record(record) for record in self.records(chip)]
        return numpy.stack(counts)
    
    def pedestals(self, chip: int) -> numpy.ndarray:
        """Returns an array with the pedestal value per channel"""
        adcs = self.adc(chip)
        return adcs.mean(axis=0)
    
    def noise(self, chip: int) -> numpy.ndarray:
        """Returns an array with the noise value per channel"""
        adcs = self.adc(chip)
        return adcs.std(axis=0)

    def global_pedestal(self, chip: int) -> float:
        """Returns the pedestal value (average adc) over all channels (per chip)"""
        pedestals = self.pedestals(chip)
        return numpy.mean(pedestals)

    def to_csv_pedestals(self, output_path: pathlib.Path | str, point: dict[str, Any] | None) -> pathlib.Path:
        """Write the pedestal data to csv"""

        n_chips = self.n_chips # use this to separate between chips
        channels = numpy.asarray(self.channels).tolist()

        frames = []
        for chip in range(n_chips):
            frames.append(pandas.DataFrame({
                "channel": numpy.arange(len(channels) * chip, len(channels) * (1 + chip)),
                "pedestals": numpy.asarray(self.pedestals(chip)).flatten(),
            }))

        df = pandas.concat(frames, ignore_index=True)
        df = df.sort_values("channel")

        header = {}
        if point is not None:
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
            df.to_csv(f, index=False)
        return csv_path

    def to_csv_adc(self, output_path: pathlib.Path | str, point: dict[str, Any] | None) -> pathlib.Path:
        """Write the output data to csv"""

        n_chips = self.n_chips # use this to separate between chips
        channels = numpy.asarray(self.channels).tolist()
        chip_records : dict[str, list[numpy.ndarray]] = {}
        for chip in range(n_chips):
            chip_records["beetle"+str(chip)] = [decode_record(record) for record in self.records(chip)]

        frames = []
        for id, beetle in enumerate(chip_records.values()):
            for run, record in enumerate(beetle):
                frames.append(pandas.DataFrame({
                    "run": run,
                    "channel": numpy.arange(len(channels) * id, len(channels) * (1 + id)),
                    "adc": numpy.asarray(record).flatten(),
                }))

        df = pandas.concat(frames, ignore_index=True)
        df = df.sort_values(["channel", "run"], ascending=[True, False])

        header = {}
        if point is not None:
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
            df.to_csv(f, index=False)
        return csv_path


def load_manifest(path: pathlib.Path | str) -> dict[str, Any]:
    """Load the JSON manifest written by a scan script"""
    with open(path) as f:
        return json.load(f)


def scan_integrals(
        manifest: dict[str, Any], data_dir: pathlib.Path | str, channel: int
) -> list[dict[str, Any]]:
    results = [{"test": 2}]
    return results