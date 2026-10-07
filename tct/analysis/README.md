---
# SPDX-FileCopyrightText: 2026 Andreas Pettersson, DESY and the Constellation authors
# SPDX-License-Identifier: CC-BY-4.0 OR EUPL-1.2
---

# h5.py

## decode_run

The meat of the decoding...

The payload contains the record for each channel. The record contains the data of each trigger.
The first index ([0]) in the payload is `num_samples`. The total expected values in the payload is
```
    1 + num_sequences * num_samples * nr_channels
```
where `num_sequences` is the number of sequences per trigger-point (normally 1).
_Note!_ There are additional out-commented lines in the case that the trigger offsets are included. *TODO:* Implement cases.

## Class Run

Class for decoding hd5f data. 

### waveforms

Returns all waveforms per channel. The ndarray is shaped by the `triggers` and `num_samples`

### all_waveforms

Concatenates waveform ndarrays.

### integrals

Sums the rows of the waveform ndarrays, that contain the samples. Returns the integral of the waveform.

### to_csv

Data is sorted one file per position. The header contains `run_id`, `position` (`x,y,z,`), `voltage` (from Keitley), `current` (from Keithley), `triggers` and `channels`, and is json formated. Each column of data contains `num_samples` samples, and is defined by the channel and trigger.



