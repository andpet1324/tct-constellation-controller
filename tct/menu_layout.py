

from .scans.manual_translation import cmd_manual_translation
from .scans.motor_scan import cmd_motor_scan
from .scans.calibrate import cmd_calibrate
from .scans.bias_scan import cmd_bias_scan
# from .scans.focus_scan import focus

from .menu_setters import set_bias

MENU = {
    "SETTINGS": ("Settings menu", {
        "SETBIAS": ("set the bias", set_bias),
    }),
    "SCANS": ("TCT scans menu", {
        "MANUAL": ("translate stages manually and record data", cmd_manual_translation),
        "MOTOR-SCAN": ("scan a spatial range", cmd_motor_scan),
        "BIAS-SCAN": ("scan a bias range in one position", cmd_bias_scan),
        "CALIBRATE": ("calibrate scope or stages", cmd_calibrate)
    })
}

