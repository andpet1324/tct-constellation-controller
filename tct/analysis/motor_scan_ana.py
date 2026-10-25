import os
import pandas as pd
import numpy as np
from scipy.optimize import curve_fit
from scipy.optimize import OptimizeWarning
import warnings
import matplotlib.pyplot as plt
import matplotlib.ticker as tck
import json
import pathlib
import itertools
import argparse
import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.compute as pc

SNS_DEEP = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3",
            "#937860", "#DA8BC3", "#8C8C8C", "#CCB974", "#64B5CD"]
# ALPHA = 1
ALPHA = 1
HIT_THRESHOLD = 25

def load_data(paths, cache: pathlib.Path | None, rebuild: bool = False) -> pd.DataFrame:
    if (cache is not None and cache.exists() and not rebuild
            and cache.stat().st_mtime > max(p.stat().st_mtime for p in paths)):
        print(f"Loading cache {cache}")
        return pd.read_parquet(
            cache,
            dtype_backend="pyarrow")

    # We need pyarrow for these large datasets in pandas
    # When we have like 500+ files I think
    tables = []
    for i, path in enumerate(paths):
        print(f"File {i} / {len(paths) - 1}")
        with open(path) as f:
            meta = json.loads(f.readline().lstrip("# "))
        meta.pop("channels", None)
        keep = ("run_id", "x", "z", "voltage")
        meta = {k: meta[k] for k in keep}
        df = pd.read_csv(path, header=1).assign(**meta)
        # df = pd.read_csv(path, header=1)
        tables.append(pa.Table.from_pandas(df, preserve_index=False))
        del df
    table = pa.concat_tables(tables, promote_options="default")
    del tables

    new_cols = []
    for col in table.columns:
        if pa.types.is_floating(col.type):
            col = col.cast(pa.float32())
        elif pa.types.is_string(col.type) or pa.types.is_large_string(col.type):
            col = pc.dictionary_encode(col)
        new_cols.append(col)
    table = pa.table(new_cols, names=table.column_names)

    if cache is not None:
        try:
            pq.write_table(table, cache)
            print(f"Wrote cache {cache}")
        except Exception as err:
            print(f"Writing cache failed with {err}")

    df = table.to_pandas(types_mapper=pd.ArrowDtype)
    del table
    return df


CHUNK_SIZE = 100
def load_chunk(paths, cache: pathlib.Path | None, k: int, rebuild: bool = False) -> pd.DataFrame:
    """Loads files k*100 ... (k+1)*100 - 1, with their own numbered cache."""
    paths = sorted(paths)
    chunk = paths[k * CHUNK_SIZE:(k + 1) * CHUNK_SIZE]
    chunk_cache = None
    if cache is not None:
        chunk_cache = cache.with_name(f"{cache.stem}_{k:03d}{cache.suffix}")
    return load_data(chunk, chunk_cache, rebuild)


def gaussian(x, a, mean, stdev):
    return a * np.exp(-(x-mean)**2/(2*stdev**2))


BINS = 100
def common_mode_subtraction(df: pd.DataFrame, fast: bool = False) -> pd.DataFrame:
    """
    Takes a pedestal subtracted df and applies common mode subtraction
    Has to be done per chip half
    The fast method is actually not quite bad compared to the fit
    """
    if fast: # Skips gaussian fit and goes straight for median
        df["chip"] = df["channel"] // 128
        df["shift"] = df.groupby(["run", "chip"])["signal"].transform("median")
        df["signal"] = df["signal"] - df["shift"]
        return df
    
    runs = df.groupby("run")
    shifts = {0: {}, 1: {}}
    for run_id, run_df in runs:
        # fit the adc distribution and take mean as baseline value
        for chip in [0,1]:
            ch_mask = (run_df["channel"] >= 128 * chip) & (run_df["channel"] < 128 * (1+chip))
            adc = run_df.loc[ch_mask, "signal"].to_numpy() # make into float64 for better accuracy?
            med = np.median(adc) # take median to minimize outlier affecting the fit
            sigma = 1.4826 * np.median(np.abs(adc - med))
            counts, edges = np.histogram(
                adc, bins=BINS, range=(med - 5 * sigma, med + 5 * sigma)
            )
            centers = 0.5 * (edges[:-1] + edges[1:])
            p0 = [counts.max(), med, sigma]
            try:
                popt, pcov = curve_fit(gaussian, centers, counts, p0=p0)
                shifts[chip][run_id] = popt[1] #mean
                # ADD PCOV ERROR
            except Exception as err:
                print(f"Fit failed with {err}")
                shifts[chip][run_id] = med

    df["chip"] = df["channel"] // 128
    df["shift"] = np.where(df["chip"] == 0,
                    df["run"].map(shifts[0]),
                    df["run"].map(shifts[1]))
    df["signal"] = df["signal"] - df["shift"]
    return df

EMPTY_CHANNELS = [0, 63, 64, 127, 128, 191, 192, 256]
ALLOWANCE = 4
THRESHOLD = 25
def remove_noisy_channels(df: pd.DataFrame, allowance: int = ALLOWANCE, threshold: float = THRESHOLD) -> pd.DataFrame:
    """
        Removes the very noisy channels. We only allow removal of 
        channels close to the empty channels to not remove the signal
    """
    df["noise"] = df.groupby("channel")["adc"].transform("std")
    ch = df["channel"].to_numpy()
    dist = np.abs(ch[:, None] - np.array(EMPTY_CHANNELS)[None, :]).min(axis=1)
    mask = (
        (df["adc"] > 
        df.groupby(["channel"])["adc"].transform("median") + threshold) &
        (dist <= allowance)
    )
    noisy_channels = df.loc[mask, "channel"].unique()
    df = df[~df["channel"].isin(noisy_channels)]

    return df


def remove_empty_channels(df: pd.DataFrame) -> pd.DataFrame:
    """
        Masks empty channels and their very noisy neighbours.
    """
    ch = df["channel"]
    mask = ~ch.isin(EMPTY_CHANNELS)
    df = df[mask]
    df = remove_noisy_channels(df)
    return df


def get_delay(df: pd.DataFrame, plotdir: pathlib.Path) -> tuple[float, float]:
    """
        Scans ADC vs time and returns the time of the min signal
    """
    t = df["time"].to_numpy()
    s = df["signal"].to_numpy()
    pos = s >= HIT_THRESHOLD
    neg = s <= -HIT_THRESHOLD
    edges = np.histogram_bin_edges(t[pos | neg], bins=100)
    counts_pos, _ = np.histogram(t[pos], bins=edges)
    counts_neg, _ = np.histogram(t[neg], bins=edges)

    # fit the signal in time. We only fit the negative
    med = np.median(counts_neg)
    sigma = 1.4826 * np.median(np.abs(counts_neg - med))
    centers = 0.5 * (edges[:-1] + edges[1:])
    p0 = [counts_neg.max(), med, sigma]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            warnings.simplefilter("error", OptimizeWarning)
            popt, pcov = curve_fit(gaussian, centers, counts_neg, p0=p0)
    except (RuntimeError, RuntimeWarning, OptimizeWarning, ValueError) as err:
        print(f"Fit failed with {err}")
        return (None, None)

    fig, ax = plt.subplots(1,1)
    ax.stairs(counts_pos, edges, label="Positive signal")
    ax.stairs(-counts_neg, edges, label="Negative signal")
    xl = np.linspace(popt[1] - 2 * popt[2], popt[1] + 2 * popt[2], 1000)
    ax.plot(
        xl, -gaussian(xl, *popt), 
        label=f"Fit: ${popt[0]:.2f} * exp(-(x-{popt[1]:.2f})^2/(2*{popt[2]:.2f}^2))$")
    ax.set_xlabel("Time [ns]")
    ax.set_ylabel("Signal [ADC]")
    ax.legend()
    ax.set_title(f"{HIT_THRESHOLD} ADC hit threshold, {df["voltage"].iloc[0]} V")
    fig.savefig(plotdir / f"signal_in_time.png", dpi=150)
    return (popt[1], popt[2])


def main(args: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Motor scan analyser")
    parser.add_argument("data", type=pathlib.Path, nargs='+', help="Data file directory")
    parser.add_argument("-ped", "--pedestal", required=True, type=pathlib.Path, help="Pedestal data")
    parser.add_argument("-plots", "--plots", type=pathlib.Path, help="Path to folder for plots")
    parser.add_argument("-c", "--cache", type=pathlib.Path, default=None,
                help="Cache file (.parquet) for the parsed data")
    parser.add_argument("--rebuild", action="store_true", help="Ignore and rewrite the cache")
    parser.add_argument("--fast-common-mode", type=bool, default=False, help="Fast and weak method of subtracting the common mode")

    args = parser.parse_args(args)
    path_pedestals = args.pedestal
    plotdir = args.plots
    subdir = plotdir / "adcs"
    if not subdir.is_dir():
        print("Plots directory does not exist! Making it now...")
        try:
            subdir.mkdir(parents=True)
        except Exception as err:
            print(f"Exception when creating dir with {err}")

    # Load in stacks of CHUNK_SIZE files to reduce memory usage at one time
    paths = sorted(args.data)
    n_chunks = -(-len(paths) // CHUNK_SIZE)

    # Build all chunk caches before the analysis starts
    if args.cache is not None:
        for k in range(n_chunks):
            print(f"Caching chunk {k} / {n_chunks - 1}")
            load_chunk(paths, args.cache, k, args.rebuild)

    pedestals = pd.read_csv(path_pedestals, header=1)

    print("Plotting...")

    colors = itertools.cycle(plt.rcParams["axes.prop_cycle"].by_key()["color"])
    fig_hits, ax_hits = plt.subplots(1,1)

    mean_channel_hits = {}
    ch1 = 96
    ch2 = 97
    ch_counts = {}
    palette = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    ch_adc = {}
    with open(paths[0]) as f:
        voltage = json.loads(f.readline().lstrip("# "))["voltage"]
    delay = None
    sigma_t = None

    df_id = -1
    for k in range(n_chunks):
        print(f"Chunk {k} / {n_chunks - 1}")
        # The cache pre-pass above already honoured --rebuild
        df_all = load_chunk(paths, args.cache, k)
        data = [g for _, g in df_all.groupby("run_id")]
        del df_all

        for df in data:
            df_id += 1
            print(f"Df {df_id} / {len(paths) - 1}")

            if df.empty:
                print(f"Df {df_id} is empty!")
                continue

            # Subtract pedestals
            df = df.merge(pedestals[["channel", "pedestals"]], on="channel", how="left")
            df["signal"] = df["adc"] - df["pedestals"]
            # GET ERROR ON PEDESTAL AND INCLUDE IT!
            if df.empty:
                print(f"Df {df_id} is empty after pedestal subtraction!")
                continue

            # Remove empty and noisy channels
            df["chip"] = df["channel"] // 128
            df = remove_empty_channels(df)

            # Subtract common mode
            df = common_mode_subtraction(df, args.fast_common_mode)

            # Chose a time window (one sigma from mean)
            # We only need to do this once, unless we change
            # the voltage during the scan!
            if delay == None:
                d, st = get_delay(df, plotdir)
                if d == None:
                    continue
                delay = d
                sigma_t = st
            print(f"Delay = {delay} and sigma_t = {sigma_t}")

            df = df[abs(df["time"] - delay) < sigma_t]
            if df.empty:
                print(f"Df {df_id} is empty after time cuts!")
                continue

            # Region of interest
            ch_min = 80
            ch_max = 110
            channels_mask = (df["channel"] > ch_min) & (df["channel"] < ch_max)
            df = df[channels_mask]
            if df.empty:
                print(f"Df {df_id} is empty after channel selection!")
                continue

            z = df["z"].iloc[0]
            x = df["x"].iloc[0]

            # Plot adcs individually
            if True and df_id < 10:
                fig, ax = plt.subplots(1,1)
                df = df.sort_values("run", ascending=True)
                ax.plot(df["channel"], df["signal"], 
                    'o', ms=2, color=SNS_DEEP[9], alpha=ALPHA)
                ax.set_title(f"alpha {ALPHA}")
                ax.set_xlabel("Channel")
                ax.set_ylabel("ADC")
                fig.savefig(subdir / f"motor_scan_adc{df_id}.png", dpi=150)
                plt.close(fig)

            ch1_adc = df[df["channel"] == ch1]
            ch2_adc = df[df["channel"] == ch2]
            if z not in ch_adc:
                ch_adc.setdefault(z, {ch1: {}, ch2: {}})
            ch_adc[z][ch1][x] = ch1_adc["signal"].mean()
            ch_adc[z][ch2][x] = ch2_adc["signal"].mean()

            # Extract hits
            hit_df = df[df["signal"].abs() > HIT_THRESHOLD]
            hits = (hit_df["signal"] != 0).groupby(hit_df["channel"]).sum()
            if (hits.values.size) == 0:
                print(f"Df {df_id} had zero hits...")
                continue

            color = palette[df_id % len(palette)]
            ax_hits.stairs(
                hits.values, np.append(hits.index, hits.index[-1] + 1) - 0.5, 
                color=color)

            if z not in hit_df:
                mean_channel_hits.setdefault(z, {})[x] = np.average(hits.index, weights=hits.values)
            else:
                mean_channel_hits[z][x] = (np.average(hits.index, weights=hits.values))
            # Count hits in certain channels, normalized by amount of hits
            if z not in ch_counts:
                ch_counts.setdefault(z, {ch1: [], ch2: []})
            ch_counts[z][ch1].append(hits.get(ch1, 0) / hits.size)
            ch_counts[z][ch2].append(hits.get(ch2, 0) / hits.size)

        del data

    print("Saving plots...")

    # Mean pedestal subtracted adc over two select channels
    fig_adc, ax_adc = plt.subplots(1,1)
    fig_zs, ax_zs = plt.subplots(1,1)
    zs = []
    sigmas = {ch1: [], ch2: []}
    for i, (z, zf) in enumerate(ch_adc.items()):
        if i >= 0:
            for ch_id, ch_df in zf.items():
                if ch_id > ch1:
                    continue
                ax_adc.plot(ch_df.keys(), ch_df.values(), label=f"z {z}")
        # Fit and plot sigma
        for ch_id, ch_df in zf.items():
            x = list(ch_df.keys())
            adc = np.abs(np.median(list(ch_df.values())))
            edges = np.histogram_bin_edges(x, bins=100)
            argmin = np.argmin(adc)
            mean = x[argmin]
            # sigma = 1.4826 * np.median(np.abs(adc - mean))
            centers = 0.5 * (edges[:-1] + edges[1:])
            p0 = [adc.max(), mean, 0.1]
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", RuntimeWarning)
                    warnings.simplefilter("error", OptimizeWarning)
                    popt, pcov = curve_fit(gaussian, centers, adc, p0=p0)
            except (RuntimeError, RuntimeWarning, OptimizeWarning, ValueError) as err:
                print(f"Fit failed with {err}")
                continue
            sigmas[ch_id].append(popt[2])
        # Avoid cases where one channel had a bad fit
        if len(sigmas[ch1]) > len(sigmas[ch2]):
            sigmas[ch1].pop()
        if len(sigmas[ch2]) > len(sigmas[ch1]):
            sigmas[ch2].pop()
        if len(sigmas[ch1]) > len(zs) and len(sigmas[ch2]) > len(zs):
            zs.append(z)
    for ch in [ch1,ch2]:
        ax_zs.plot(zs, sigmas[ch], label=f"ch {ch}")
    ax_zs.legend()
    ax_zs.set_xlabel("Position in z [mm]")
    ax_zs.set_ylabel("σ in x [mm]")
    fig_zs.savefig(plotdir / "focus_scan.png", dpi=150)

    ax_adc.xaxis.set_minor_locator(tck.AutoMinorLocator())    
    ax_adc.legend()
    ax_adc.set_title(f"{HIT_THRESHOLD} ADC hit threshold , {voltage} V")
    ax_adc.set_xlabel("Position in x [mm]")
    ax_adc.set_ylabel("Mean ADC")
    fig_adc.savefig(plotdir / "motor_scan_two_channels_adc.png", dpi=150)

    # Hits
    ax_hits.set_title(f"{HIT_THRESHOLD} ADC hit threshold , {voltage} V")
    ax_hits.set_xlabel("Channel")
    ax_hits.set_ylabel("# Hits")
    fig_hits.savefig(plotdir / "motor_scan_hits.png", dpi=150)

    # Avg hits
    fig_avg_hits, ax_avg_hits = plt.subplots(1,1)
    for z, zf in mean_channel_hits.items():
        ax_avg_hits.plot(
            list(zf.keys()), list(zf.values()), 
            '-o', label=f"z = {z:.3f} mm", color=next(colors))
    
    ax_avg_hits.set_title(f"{HIT_THRESHOLD} ADC hit threshold , {voltage} V")
    ax_avg_hits.set_xlabel("Position in x [mm]")
    ax_avg_hits.set_ylabel("Hit average [channel]")
    ax_avg_hits.grid(True)
    ax_avg_hits.legend()
    fig_avg_hits.savefig(plotdir / "motor_scan_avg_hits.png", dpi=150)

    # Hits in specified channels
    fig_hc, ax_hc = plt.subplots(1,1)
    colors = itertools.cycle(plt.rcParams["axes.prop_cycle"].by_key()["color"])
    for z, zf in ch_counts.items():
        ax_hc.plot(
            zf[ch1], zf[ch2], 
            '-o', label=f"z = {z:.3f}", color=next(colors))

    ax_hc.set_title(f"{HIT_THRESHOLD} ADC hit threshold , {voltage} V")
    ax_hc.set_xlabel(f"# Hits in ch {ch1}")
    ax_hc.set_ylabel(f"# Hits in ch {ch2}")
    fig_hc.savefig(plotdir / "motor_scan_hits_channels.png", dpi=150)


if __name__ == "__main__":
    main()
