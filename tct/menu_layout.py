

from .scans.manual_translation import cmd_manual_translation
from .scans.motor_scan import cmd_motor_scan
from .scans.calibrate import cmd_calibrate
from .scans.bias_scan import cmd_bias_scan
from .scans.pedestal_scan import cmd_pedestal_scan
from .alibava.monitors import cmd_monitor_pedestals
from .alibava.monitors import cmd_monitor_adc
from .alibava.latency_scan import cmd_latency_scan
from .alibava.laser_scan import cmd_laser_scan
from .alibava.focus_finder import cmd_focus_finder
# from .scans.focus_scan import focus

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
        "PEDESTAL": ("pedestal run", cmd_pedestal_scan),
    }),
    "ALIBAVA": ("Alibava scans menu", {
        "MONITOR-PEDESTALS": ("runs a pedestal scan and plots pedestals and noise", cmd_monitor_pedestals),
        "MONITOR-ADC": ("runs a pedestal scan and plots adc", cmd_monitor_adc),
        "LATENCY-SCAN": ("latency parameter scan to find the laser signal", cmd_latency_scan),
        "LASER-SCAN": ("laser scan with adcs per channel to csv", cmd_laser_scan),
        "FOCUS-FINDER": ("scans hits over x-z range to find the laser focus", cmd_focus_finder)
    }),
}

