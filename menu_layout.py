from .scans.manual_translation import cmd_manual_translation
from .scans.motor_scan import cmd_motor_scan
from .scans.calibrate import cmd_calibrate
from .scans.bias_scan import cmd_bias_scan
from .alibava.pedestal_scan import cmd_pedestal_scan
from .alibava.continuous_runs import cmd_run_pedestals
from .alibava.continuous_runs import cmd_run_adc
from .alibava.laser_scan import cmd_laser_scan
from .alibava.focus_finder import cmd_focus_finder

from .menu_setters import set_bias
from .menu_getters import read_position

MENU = {
    "SETTINGS": ("Settings menu", {
        "SET-BIAS": ("set the bias", set_bias),
        "GET-POSITION": ("get position of the stages", read_position),
    }),
    "SCANS": ("TCT scans menu", {
        "MANUAL": ("translate stages manually and record data", cmd_manual_translation),
        "MOTOR-SCAN": ("scan a spatial range", cmd_motor_scan),
        "BIAS-SCAN": ("scan a bias range in one position", cmd_bias_scan),
        "CALIBRATE": ("calibrate scope or stages", cmd_calibrate),
    }),
    "ALIBAVA": ("Alibava scans menu", {
        "PEDESTAL": ("pedestal run", cmd_pedestal_scan),
        "CONTINOUS-PEDESTALS": ("runs a continous pedestal scan for monitoring", cmd_run_pedestals),
        "CONTINOUS-ADC": ("runs a continous laser scan for monitoring", cmd_run_adc),
        "LASER-SCAN": ("laser scan with adcs per channel to csv", cmd_laser_scan),
        "FOCUS-FINDER": ("scans hits over x-z range to find the laser focus NOT WORKING!!", cmd_focus_finder)
    }),
    "LECROY": ("LeCroy scans menu", {
        "RUN-ADC": ("runs a continous laser scan for monitoring", cmd_run_adc),
    }),
}
