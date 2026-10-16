import pathlib
import matplotlib.pyplot as plt
import numpy
from scipy.optimize import curve_fit

from constellation.core.controller import SatelliteCommLink

from ..controller import TCTController
from ..prompts import readline_int, readline_float, readline_bool
from ..analysis.h5 import Run
from ..scans.common import reconfigure, run_identifier, data_directory, get_position

ZOFFSET = 0.01 # 10 um


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
    xrange: float, xsteps: int,
    zrange: float, zsteps: int,
    pos0: dict[str, float]
) -> None:
    """Take data in RADSOURCE mode for an amount of triggers
    """
    ctrl.log.status(f"Setting Alibava to RADSOURCE mode")
    reconfigure(ctrl, daq, {"run_type": "RADSOURCE"})

    # Move z-stage back slightly incase we're infront of the focus
    position = {"x": pos0["x"], "y": pos0["y"], "z": pos0["z"] - ZOFFSET}
    reconfigure(ctrl, stage, position)

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

    count = 0
    widths = []
    try:
        for z in range(pos0["z"], pos0["z"] + zrange, zsteps):
            for x in range(pos0["x"], pos0["x"] + xrange, xsteps):
                position = {"x": x, "y": pos0["y"], "z": z}
                reconfigure(ctrl, stage, position)
                run_id = run_identifier("focus_finder_scan" + str(count))
                ctrl.take_run(run_id, trgs)
                try:
                    with Run.from_run_id(run_id, data_dir) as run:
                        channels = run.channels
                        xl = channels + chip * len(channels)
                        adcs = run.adc(chip)

                        # hits per channel
                        mask = adcs >= hit_threshold
                        hits = numpy.count_nonzero(mask, axis=0)
                        edges = numpy.append(xl, xl[-1] + 1) - 0.5
                        lines["hits"].set_data(values=hits, edges=edges)

                        # fit the hits across channels
                        sigma, sigma_err = numpy.nan, numpy.nan
                        if hits.sum() > 0:
                            try:
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
                            ax_sig.errorbar(z, sigma, yerr=sigma_err, fmt="o", capsize=3, color="green")
                            ax_sig.relim()
                            ax_sig.autoscale_view()

                        fig.canvas.draw_idle()
                        plt.pause(0.01)
                except Exception as err:
                    ctrl.log.warning(f"Could not get data from {run_id}: {err}")

        w = numpy.array(widths, dtype=float)
        if w.any():
            best = numpy.argmin(w[w, 2])
            print(f"Smallest sigma: {best[2]:.3f} ± {best[3]:.3f} at z = {best[0]:.0f}, x = {best[1]:.0f}")
            ax_sig.axvline(best, color="k", ls="--", lw=1)

        plt.ioff()
        plt.show()
        count += 1

    except KeyboardInterrupt:
        return

    
def cmd_focus_finder(tgt: dict[str, any]) -> None:
    """
    Scans along the x-axis, plotting the hit-profile and calcualting 
    the width of the gaussian across channels
    """
    if (readline_bool("Did you align the laser and focus on the sensor?", True)):
        triggers = readline_int("Triggers per run", 10000)
        chip = readline_int("Beetle chip being read out", 0)
        hit_threshold = readline_float("Threshold for a hit (ADC)", 100)
        xrange = readline_float("Length to scan in x (mm)", 1.0)
        xsteps = readline_int("Number of scans in x", 10)
        zrange = readline_float("Length to scan in z (mm)", 2.0)
        zsteps = readline_int("Number of scans in z" 10)
        data_dir = data_directory(tgt["cfg"], tgt["writer"])
        initial_position = get_position(tgt["ctrl"], tgt["stage"])
        try:
            focus_finder(tgt["ctrl"], tgt["stage"], tgt["daq"], 
                         triggers, chip, 
                         hit_threshold, data_dir, 
                         xrange, xsteps, zrange, zsteps, 
                         initial_position)
        except Exception as err:
            print(f"Focus finder interrupted with error: {err}")
        finally:
            print("Focus finder ended. Moving stages to initial position")
            reconfigure(tgt["ctrl"], tgt["stage"], initial_position)
            return
    return