<!--
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: CC-BY-4.0
-->

# TCT Constellation Controller

> Scans for a TCT setup.

| | |
|---|---|
| **Type** | Controller / Monitor (Python) |
| **Requires** | Python >= 3.11, [Constellation](https://constellation.pages.desy.de) |
| **Maintainer** | A. Pettersson, DESY |

## Description

Controller and Monitor for a TCT dedicated experimental setup using a Keithley
HV supply, Standa stages for DUT translation, and a Alibava or LeCroy DAQ. Both DAQs
make use the H5 data writer.

## Installation

```sh
pip install -e .
```

| Command | Description |
|---|---|
| `tct-menu` | Interactive controller menu |
| `tct-monitor` | Live monitor listening to the runs of the controller |

## Satellites

| Satellite | Purpose |
|---|---|
| `Standa` | Translation stage |
| `Keithley` | Bias voltage |
| `H5DataWriter` | Data writing |
| `Alibava` | DAQ |
| `LeCroySatellite` | DAQ |

## Configuration

Example configurations for Alibava and LeCroy live in [config/](config/).

### Parameters

Parameters that can be set in the menus SETTINGS submenu.

| Parameter | Description | Type |
|---|---|---|
| `SET-BIAS` | Reconfigures the HV | `int` |

## Shared Scans

| Scan | Module | Description |
|---|---|---|
| Motor scan | [scans/motor_scan.py](scans/motor_scan.py) | Scans a given x,y,z range and takes data in each point, with choice of including a bias range scan. | Yes |
| Bias scan | [scans/bias_scan.py](scans/bias_scan.py) | Scans a bias range at one spatial position | Yes |
| Calibration | [scans/calibrate.py](scans/calibrate.py) | Self-calibrates the scope and homes the stages | No |
| Manual translation | [scans/manual_translation.py](scans/manual_translation.py) | Take data at a specified x,y,z coordinate | Yes |

## DAQ Specific Scans

### Alibava Scans

| Scan | Module | Description | Saves to CSV |
|---|---|---|
| Laser Scan | [alibava/laser_scan.py](alibava/laser_scan.py) | DEPRECATED! Use scans/manual_translation.py | Yes |
| Pedestal Scan | [alibava/pedestal_scan.py](alibava/pedestal_scan.py) | Takes data in Alibava's PEDESTAL mode. Writes the pedestal value per channel averaged 
                                                                        over the total amount of runs |  Yes |
| Run Pedestals | [alibava/continuous_runs.py](alibava/continuous_runs.py) | Continuously takes data in Alibava's PEDESTAL mode. Meant for use in combination with a monitor. | No |
| Run ADC | [alibava/continuous_runs.py](alibava/continuous_runs.py) | Continuously takes data in Alibava's RADSOURCE mode. Meant for use in combination with a monitor. | No |

### LeCroy Scans

| Scan | Module | Description |
|---|---|---|
| Laser Scan | [alibava/laser_scan.py](alibava/laser_scan.py) | DEPRECATED! Use scans/manual_translation.py |
| Pedestal Scan | [alibava/pedestal_scan.py](alibava/pedestal_scan.py) | Takes data in Alibava's PEDESTAL mode. Writes the pedestal value per channel averaged 
                                                                        over the total amount of runs |
| Run Pedestals | [alibava/continuous_runs.py](alibava/continuous_runs.py) | Continuously takes data in Alibava's PEDESTAL mode. Meant for use in combination with a monitor. |
| Run ADC | [alibava/continuous_runs.py](alibava/continuous_runs.py) | Continuously takes data in Alibava's RADSOURCE mode. Meant for use in combination with a monitor. |

## Metrics

Controller specific metrics the monitors subscribe to.

| Metric | Description | Type | Interval [s] |
|---|---|---|---|
| `RUN_IDENTIFIER` | Identifier of the current run | `String` | 1 |
| `DATA_DIRECTORY` | Directory of the current run | `String` | 10 |

## Data Format

The CSV data format depends on the type of DAQ as described below. All share a common header
which has the following format:

| Run ID | Position | Voltage | Current | Triggers | Extra |
|---|---|---|---|---|---|---|
| Identifier of the current run | Position of stages in x,y,z | Keithley voltage | Keithley current | Collected triggers | Any extra metadata |

### Alibava Data Format

Alibava output has two formats depending on wether the run is in PEDESTAL or RADSOURCE mode.
In PEDESTAL mode, the average ADC per channel is stored. In RADSOURCE mode, the raw ADC data is stored, along with the timestamp w.r.t the current 100 ns latency window.


### LeCroy Data Format

Saves the raw waveform data from the oscilloscope.

## Usage

```sh
tct-menu --help
tct-monitor --help
```

## License

Code: EUPL-1.2. Documentation: CC-BY-4.0.
