from .scans.common import reconfigure
from .prompts import readline_float

from constellation.core.protocol.cscp1 import SatelliteState

def set_bias(tgt: dict[str, any]) -> None:
    voltage: float = readline_float("New voltage")
    recfg = {"voltage": voltage}

    reconfigure(tgt["ctrl"], tgt["hv"], recfg)
    tgt["ctrl"].await_state(SatelliteState.ORBIT)

    new_voltage = tgt["hv"].read_output()["voltage"]
    tgt["ctrl"].log.status(f"Voltage set to {new_voltage}")
    return