"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Helpers for characterising a waveform
"""

import json
import pathlib
from collections.abc import Iterator
from typing import Any

import h5py
import numpy

PEDESTAL_AVERAGE_POINTS: int = 30 # How many points from 0 to average over
CFD: float = 70.0


def get_pedestal(trace: numpy.ndarray) -> float:
    return trace[:PEDESTAL_AVERAGE_POINTS].mean()


def get_maximum(trace: numpy.ndarray) -> tuple[float, float]:
    return (trace.max(), trace.argmax())


def x(k,m,y):
    return (y-m)/k


# def get_tot(trace: numpy.ndarray, times: numpy.ndarray, cfd: float = CFD) -> tuple[float, float]:
#     threshold = (get_maximum(trace) - get_pedestal(trace)) * cfd
#     mask = (trace > threshold)
#     tot_range_y = trace[mask]
#     tot_range_x = times[mask]

#     left_of_max_y = trace[times < get_maximum(trace)[1]]
#     left_of_max_x = times[times < get_maximum(trace)[1]]
#     right_of_max_y = trace - left_of_max_y
#     right_of_max_x = times - left_of_max_x

#     x_left = numpy.interp(threshold, left_of_max_x, left_of_max_y)
    
#     #tot = tot_range[-1] - tot_range[0]
#     return tot, threshold
