from .scans.common import reconfigure
from .prompts import readline_float

from constellation.core.protocol.cscp1 import SatelliteState

def set_bias(tgt: dict[str, any]) -> None:
    voltage: float = readline_float("New voltage")
    recfg = {"voltage": voltage}
    tgt["ctrl"].log.info(f"Setting bias to {voltage}")
    # EXTRACT THE TIME-STEP BETWEEN VOLTAGES, AND SET THE TIMEOUT TO BE
    # TIMEOUT = TIMEOUT + TIME-STEP * NR_STEPS 

    try:
        reconfigure(tgt["ctrl"], tgt["hv"], recfg)
        # WHY DOES THIS TIMEOUT NOT WORK???
        tgt["ctrl"].await_state(SatelliteState.ORBIT, timeout = 360) # Setting the bias takes time
    except TimeoutError as err:
        print(f"Waiting for state ORBIT failed with {err}")
        print("Check if the current reached compliance.")
        return

    new_voltage = (tgt["hv"].read_output().payload)["voltage"]
    tgt["ctrl"].log.status(f"Voltage set to {new_voltage}")
    return