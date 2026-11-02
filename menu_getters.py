"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Getters of satellite parameters.
"""
from typing import Any

from constellation.core.protocol.cscp1 import SatelliteState

from .scans.common import get_position

def read_position(tgt: dict[str, Any]) -> str:
    position = get_position(tgt["ctrl"], tgt["stage"])
    tgt["ctrl"].log.status(f"Stages currently at {position}")
    return f"Stages currently at {position}"