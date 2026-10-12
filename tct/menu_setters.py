from .scans.common import reconfigure
from .prompts import readline_float

from constellation.core.protocol.cscp1 import SatelliteState

def set_bias(tgt: dict[str, any]) -> None:
    voltage: float = readline_float("New voltage")
    recfg = {"voltage": voltage}
    reconfigure(tgt["ctrl"], HV, recfg)
    tgt["ctrl"].await_state(SatelliteState.ORBIT)
    # ADD READ BIAS HERE
    print(f"Voltage set to {voltage}")
    return