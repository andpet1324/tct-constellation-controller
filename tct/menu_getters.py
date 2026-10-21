from constellation.core.protocol.cscp1 import SatelliteState

from .scans.common import get_position

def read_position(tgt: dict[str, any]) -> str:
    position = get_position(tgt["ctrl"], tgt["stage"])
    tgt["ctrl"].log.status(f"Stages currently at {position}")
    return f"Stages currently at {position}"