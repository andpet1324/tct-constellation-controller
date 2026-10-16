import pathlib
import matplotlib.pyplot as plt
import numpy
from scipy.optimize import curve_fit

from constellation.core.controller import SatelliteCommLink

from ..controller import TCTController
from ..prompts import readline_int, readline_float, readline_bool, readline_path
from ..analysis.h5 import Run
from ..scans.common import reconfigure, run_identifier, data_directory, get_position

ZOFFSET: float = 0.1 # 100 um


def gaussian(x, amp, mu, sigma):
    return amp * numpy.exp(-0.5 * ((x - mu) / sigma) ** 2)


def focus_finder(
    ctrl: TCTController,
    stage: SatelliteCommLink,
    daq: SatelliteCommLink,
    trgs: int,
    chip: int,
    hit_threshold: float,
    data_dir: pathlib.Path,
    pedestals: pathlib.Path,
    xrange: float, xsteps: int,
    zrange: float, zsteps: int,
    pos0: dict[str, float]
) -> None:
    """Take data in RADSOURCE mode for an amount of triggers
    """
    ctrl.log.status(f"Setting Alibava to RADSOURCE mode")
    reconfigure(ctrl, daq, {"run_type": "RADSOURCE"})

    # Move z-stage back slightly incase we're infront of the focus
    z_start = pos0["z"] - ZOFFSET
    position = {"x": pos0["x"], "y": pos0["y"], "z": float(z_start)}
    ctrl.log.status(f"Moving back z-stage by {ZOFFSET} mm to: {position}")
    reconfigure(ctrl, stage, {"position": position})

    pedestals_df = numpy.genfromtxt(pedestals, delimiter=",",
                    names=True, skip_header=1, dtype=float)
    pedestals = pedestals_df["pedestals"]
    ch = pedestals_df["channel"]
    mask = (ch >= chip * 128) & (ch < (chip + 1) * 128)
    pedestals = pedestals_df["pedestals"][mask]

    plt.ion()
    fig, (ax_hits, ax_sig) = plt.subplots(1, 2, figsize=(12, 5))
    plt.show(block=False)
    plt.pause(0.1)

    ax_hits.grid(True)
    ax_hits.set_xlabel("Channel")
    ax_hits.set_ylabel("# Hits")
    hhits = ax_hits.stairs([0], [0, 1], color="green", label="hits")
    (hfit,) = ax_hits.plot([], [], color="k", lw=1.5, label="Gaussian fit")
    lines = {"hits": hhits, "fit": hfit}
    ax_hits.legend()

    ax_sig.grid(True)
    ax_sig.set_xlabel("z position")
    ax_sig.set_ylabel("σ [channels]")

    print(k for k in numpy.linspace(z_start, z_start + zrange, zsteps))
    print(i for i in numpy.linspace(pos0["x"], pos0["x"] + xrange, xsteps))

    count = 0
    scan_range = xsteps + zsteps
    widths = []
    try:
        for z in numpy.linspace(z_start, z_start + zrange, zsteps):
            for x in numpy.linspace(pos0["x"], pos0["x"] + xrange, xsteps):
                position = {"x": float(x), "y": float(pos0["y"]), "z": float(z)}
                ctrl.log.status(f"Point {count}/{scan_range}: {position}")
                reconfigure(ctrl, stage, {"position": position})
                run_id = run_identifier("focus_finder_scan" + str(count))
                ctrl.take_run(run_id, trgs)
                try:
                    with Run.from_run_id(run_id, data_dir) as run:
                        channels = run.channels
                        xl = channels + chip * len(channels)
                        adcs = run.adc(chip)

                        # subtract pedestals
                        diff = adcs - pedestals
                        entries = diff[numpy.abs(diff) > hit_threshold]

                        # hits per channel
                        hits = numpy.count_nonzero(mask, axis=0)
                        edges = numpy.append(xl, xl[-1] + 1) - 0.5
                        lines["hits"].set_data(values=hits, edges=edges)

                        # fit the hits across channels
                        sigma, sigma_err = numpy.nan, numpy.nan
                        # Check that the spread of hits is not over all channels (no signal)
                        try:
                            mean = numpy.average(xl, weights=hits)
                            rms = numpy.sqrt(numpy.average((xl - mean) ** 2, weights=hits))
                            if rms < 0.5 * len(channels) / numpy.sqrt(12): # What is a good val here?
                                mean = numpy.average(xl, weights=hits)
                                rms = numpy.sqrt(numpy.average((xl - mean) ** 2, weights=hits))
                                p0 = [hits.max(), mean, max(rms, 0.5)]
                                popt, pcov = curve_fit(gaussian, xl, hits, p0=p0)
                                sigma = abs(popt[2])
                                sigma_err = numpy.sqrt(pcov[2, 2])

                                xf = numpy.linspace(edges[0], edges[-1], 200)
                                lines["fit"].set_data(xf, gaussian(xf, *popt))
                                lines["fit"].set_label(f"σ = {sigma:.2f} ± {sigma_err:.2f}")
                        except (RuntimeError, ValueError):
                            lines["fit"].set_data([], [])
                            lines["fit"].set_label("fit failed")

                        print(f"run {count} (z={z}, x={x}): sigma = {sigma:.3f} ± {sigma_err:.3f} channels")
                        widths.append((z, x, sigma, sigma_err))

                        ax_hits.set_title(f"z = {z}, x = {x}")
                        ax_hits.set_xlim(edges[0], edges[-1])
                        ax_hits.set_ylim(0, max(hits.max(), 1) * 1.15)
                        ax_hits.legend()

                        # Plot the widths against z
                        if numpy.isfinite(sigma):
                            ax_sig.errorbar(z, sigma, yerr=sigma_err, fmt="o", color="green")
                            ax_sig.relim()
                            ax_sig.autoscale_view()

                        fig.canvas.draw_idle()
                        plt.pause(0.01)
                except Exception as err:
                    import traceback
                    traceback.print_exc()
                    ctrl.log.warning(f"Could not get data from {run_id}: {err}")

                count += 1

        w = numpy.array(widths, dtype=float)
        valid = w.size > 0 and numpy.isfinite(w[:, 2]).any()
        if valid:
            i = numpy.nanargmin(w[:, 2])
            z_best, x_best, s_best, s_err = w[i]
            print(f"Smallest sigma: {s_best:.3f} ± {s_err:.3f} at z = {z_best:.3f}, x = {x_best:.3f}")
            ax_sig.axvline(z_best, color="k", ls="--", lw=1)
        else:
            print("No successful fits, could not determine focus")

    except KeyboardInterrupt:
        return

    
def cmd_focus_finder(tgt: dict[str, any]) -> None:
    """
    Scans along the x-axis, plotting the hits over channels and calcualting 
    the width of the gaussian (if there is a hit)
    """
    if (readline_bool("Did you align the laser and focus on the sensor?" \
        "You can eyeball the focus with MONITOR-ADC", True)):
        triggers = readline_int("Triggers per run", 1000)
        chip = readline_int("Beetle chip being read out", 0)
        hit_threshold = readline_float("Threshold for a hit (ADC)", 100)
        xrange = readline_float("Length to scan in x (mm)", 1.0)
        xsteps = readline_int("Number of scans in x", 10)
        zrange = readline_float("Length to scan in z (mm)", 2.0)
        zsteps = readline_int("Number of scans in z", 10)
        pedestal_data = readline_path("Pedestal data file path")
        data_dir = data_directory(tgt["cfg"], tgt["writer"])
        initial_position = get_position(tgt["ctrl"], tgt["stage"])
        try:
            focus_finder(tgt["ctrl"], tgt["stage"], tgt["daq"], 
                         triggers, chip, 
                         hit_threshold, data_dir, pedestal_data, 
                         xrange, xsteps, zrange, zsteps, 
                         initial_position)
        except Exception as err:
            print(f"Focus finder interrupted with error: {err}")
        finally:
            print("Focus finder ended. Moving stages to initial position")
            reconfigure(tgt["ctrl"], tgt["stage"], {"position": initial_position})
            return
    return