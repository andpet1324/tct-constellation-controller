import pandas as pd
import numpy as np
import scipy as scp
import matplotlib.pyplot as plt
import json
import pathlib
import itertools
import argparse

SNS_DEEP = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3",
            "#937860", "#DA8BC3", "#8C8C8C", "#CCB974", "#64B5CD"]
ALPHA = 1
# ALPHA = 0.5
HIT_THRESHOLD = 25

def load_data(paths, cache: pathlib.Path | None, rebuild: bool = False) -> pd.DataFrame:
    if (cache is not None and cache.exists() and not rebuild
            and cache.stat().st_mtime > max(p.stat().st_mtime for p in paths)):
        print(f"Loading cache {cache}")
        return pd.read_parquet(cache)

    dfs = []
    for i, path in enumerate(paths):
        print(f"File {i} / {len(paths) - 1}")
        with open(path) as f:
            meta = json.loads(f.readline().lstrip("# "))
        meta.pop("channels", None)
        dfs.append(pd.read_csv(path, header=1).assign(**meta))
    df = pd.concat(dfs, ignore_index=True)

    if cache is not None:
        df.to_parquet(cache)
        print(f"Wrote cache {cache}")
    return df

def common_mode_subtractions(df: pd.DataFrame, pedestals: pd.DataFrame):
    runs = df.groupby("run")
    for run_id, run_df in runs:
        # fit the adc distribution and take mean as baseline value



def main(args: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Motor scan analyser")
    parser.add_argument("data", type=pathlib.Path, nargs='+', help="Data file directory")
    parser.add_argument("-ped", "--pedestal", required=True, type=pathlib.Path, help="Pedestal data")
    parser.add_argument("-plots", "--plots", type=pathlib.Path, help="Path to folder for plots")
    parser.add_argument("-c", "--cache", type=pathlib.Path, default=None,
                help="Cache file (.parquet) for the parsed data")
    parser.add_argument("--rebuild", action="store_true", help="Ignore and rewrite the cache")

    args = parser.parse_args(args)
    path_pedestals = args.pedestal
    plots_dir = args.plots
    subdir = plots_dir / "adcs"
    if not subdir.is_dir():
        print("Plots directory does not exist! Making it now...")
        try:
            subdir.mkdir(parents=True)
        except Exception as err:
            print(f"Exception when creating dir with {err}")

    df_all = load_data(args.data, args.cache, args.rebuild)
    data = [g for _, g in df_all.groupby("run_id")]
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

    for df_id, df in enumerate(data):

        # Chose a time windows
        delay = 50
        df = df[abs(df["time"] - delay) < 5]

        # df = df.sort_values('run', ascending=True)

        # for (motor_x, motor_y), group in df.groupby(["motor_x", "motor_y"]):

        # if df_id > 1:
        #     break
        print(f"Df {df_id} / {len(data)-1}")

        # Subtract pedestals
        df = df.merge(pedestals[["channel", "pedestals"]], on="channel", how="left")
        df["signal"] = df["adc"] - df["pedestals"]

        # Region of interest
        ch_min = 90
        ch_max = 105
        channels_mask = (df["channel"] > ch_min) & (df["channel"] < ch_max)
        df = df[channels_mask]

        z = df["z"].iloc[0]
        x = df["x"].iloc[0]

        # Plot adcs individually
        if True:
            # fig, ax = plt.subplots(1,1)
            # ax.plot(df["channel"], df["adc"], 
            #     '-o', ms=2, color=SNS_DEEP[9], alpha=ALPHA)
            # ax.set_title(f"alpha {ALPHA}")
            # ax.set_xlabel("Channel")
            # ax.set_ylabel("ADC")
            # fig.savefig(subdir / f"motor_scan_adc{df_id}.png", dpi=150)
            # plt.close(fig)

            ch1_adc = df[df["channel"] == ch1]
            ch2_adc = df[df["channel"] == ch2]
            if z not in ch_adc:
                ch_adc.setdefault(z, {ch1: {}, ch2: {}})
            ch_adc[z][ch1][x] = ch1_adc["adc"].mean()
            ch_adc[z][ch2][x] = ch2_adc["adc"].mean()


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

    print("Saving plots...")

    # Mean adc over my channels

    fig_adc, ax_adc = plt.subplots(1,1)
    for i, (z, zf) in enumerate(ch_adc.items()):
        if i > 0:
            break
        for ch_id, ch_df in zf.items():
            ax_adc.plot(ch_df.keys(), ch_df.values(), label=f"ch {ch_id}")

    ax_adc.legend()
    ax_adc.set_title(f"Hit threshold {HIT_THRESHOLD} ADC")
    ax_adc.set_xlabel("Position in x [mm]")
    ax_adc.set_ylabel("Mean ADC")

    fig_adc.savefig(plots_dir / "motor_scan_two_channels_adc.png", dpi=150)

    # Hits
    ax_hits.set_title(f"Hit threshold {HIT_THRESHOLD} ADC")
    ax_hits.set_xlabel("Channel")
    ax_hits.set_ylabel("# Hits")

    fig_hits.savefig(plots_dir / "motor_scan_hits.png", dpi=150)

    # Avg hits
    fig_avg_hits, ax_avg_hits = plt.subplots(1,1)
    for z, zf in mean_channel_hits.items():
        ax_avg_hits.plot(
            list(zf.keys()), list(zf.values()), 
            '-o', label=f"z = {z:.3f} mm", color=next(colors))
        ax_avg_hits.set_title(f"Hit threshold {HIT_THRESHOLD} ADC")
        ax_avg_hits.set_xlabel("Position in x [mm]")
        ax_avg_hits.set_ylabel("Hit average [channel]")

    ax_avg_hits.grid(True)
    ax_avg_hits.legend()
    fig_avg_hits.savefig(plots_dir / "motor_scan_avg_hits.png", dpi=150)

    # Hits in specified channels
    fig_hc, ax_hc = plt.subplots(1,1)
    colors = itertools.cycle(plt.rcParams["axes.prop_cycle"].by_key()["color"])
    for z, zf in ch_counts.items():
        ax_hc.plot(
            zf[ch1], zf[ch2], 
            '-o', label=f"z = {z:.3f}", color=next(colors))

    ax_hc.set_title(f"Hit threshold {HIT_THRESHOLD} ADC")
    ax_hc.set_xlabel(f"# Hits in ch {ch1}")
    ax_hc.set_ylabel(f"# Hits in ch {ch2}")

    fig_hc.savefig(plots_dir / "motor_scan_hits_channels.png", dpi=150)


if __name__ == "__main__":
    main()