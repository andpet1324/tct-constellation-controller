from .scans.manual_translation import manual
from .scans.motor_scan import motor_scan
from .scans.calibrate import calibrate
from .scans.bias_scan import bias_scan
# from .scans.focus_scan import focus

from .scans.common import reconfigure, readline_int
from .controller import TCTController

STAGE = "Standa.Stage"
HV = "Keithley.HV"
DAQ = "Alibava.DAQ"
WRITER = "H5DataWriter.Writer"
SATELLITES = [STAGE, HV, DAQ, WRITER]

def set_bias(tgt: dict[str, int]):
    voltage = readline_int("New voltage")
    recfg = {"voltage": voltage}
    reconfigure(tgt["ctrl"], HV, recfg)

MENU = {
    "SETTINGS": ("Settings menu", {
        "SETBIAS": ("set the bias", set_bias),
    }),
    "SCANS": ("TCT scans menu", {
        "MANUAL": ("translate stages manually and record data", manual),
        "SCAN": ("scan a spatial range", motor_scan),
        "BIAS-SCAN": ("scan a bias range in one position", bias_scan),
        "CALIBRATE": ("calibrate scope or stages", calibrate)
    })
}

