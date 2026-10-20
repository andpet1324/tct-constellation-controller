import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
import pathlib

import argparse

SNS_DEEP = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3",
            "#937860", "#DA8BC3", "#8C8C8C", "#CCB974", "#64B5CD"]
ALPHA = 0.08

def main(args: list[str] | None = None):
    print("Parsing data...")
    parser = argparse.ArgumentParser(description="Motor scan analyser")
    parser.add_argument("data", type=pathlib.Path, nargs='+', help="Data file directory")
    parser.add_argument("-p", "--pedestal", required=True, type=pathlib.Path, help="Pedestal data")

    args = parser.parse_args(args)
    data_path_l = args.data
    path_pedestals = args.pedestal

    data = []
    headers = []
    for path in data_path_l:
        headers.append(json.loads(open(path).readline().lstrip("# ")))
        data.append(pd.read_csv(path, header=1))
    pedestals = pd.read_csv(path_pedestals, header=1)

    print("Plotting...")

    fig, ax = plt.subplots(1,1)

    mean_channel_hits = {}

    ch1 = 97
    ch2 = 98
    ch1_counts = []
    ch2_counts = []

    for df_id, df in enumerate(data):
        # if df_id > 1:
        #     break
        print(f"Df {df_id+1} / {len(data)}")

        # Subtract pedestals
        df = df.merge(pedestals[["channel", "pedestals"]], on="channel", how="left")
        df["signal"] = df["adc"] - df["pedestals"]

        # Region of interest
        ch_min = 90
        ch_max = 105
        channels_mask = (df["channel"] > ch_min) & (df["channel"] < ch_max)
        df = df[channels_mask]

        # Only chose a select time
        delay = 50
        df = df[abs(df["time"] - delay) < 5]

        # Plot adcs
        run_group = df.groupby('run')
        for _, run_df in run_group:
            ax.plot(run_df["channel"], run_df["signal"], '-o', ms=2, color=SNS_DEEP[9], alpha=ALPHA)

        # Extract hits
        HIT_THRESHOLD = 25

        hit_df = df[df["signal"].abs() > HIT_THRESHOLD]
        hits = (hit_df["signal"] != 0).groupby(hit_df["channel"]).sum()
        # ax_hits.stairs(hits.values, np.append(hits.index, hits.index[-1] + 1) - 0.5, color=SNS_DEEP[df_id])
        mean_channel_hits[headers[df_id]["x"]] = (np.average(hits.index, weights=hits.values))

        # Count hits in certain channels, normalized by amount of hits
        ch1_counts.append(hits.get(ch1, 0) / hits.size)
        ch2_counts.append(hits.get(ch2, 0) / hits.size)


    ax.set_title(f"alpha {ALPHA}")
    ax.set_xlabel("Channel")
    ax.set_ylabel("ADC")

    print("Saving plot...")
    fig.savefig(f"motor_scan_adc.png", dpi=150)

    # Hits
    fig_hits, ax_hits = plt.subplots(1,1)
    ax_hits.plot(list(mean_channel_hits.keys()), list(mean_channel_hits.values()), '-o')
    ax_hits.set_title(f"hit threshold {HIT_THRESHOLD} ADC")
    ax_hits.set_xlabel("Position in x [mm]")
    ax_hits.set_ylabel("Average hit channel")

    fig_hits.savefig(f"motor_scan_hits.png", dpi=150)

    # Hits in specified channels
    fig_hc, ax_hc = plt.subplots(1,1)
    ax_hc.plot(ch1_counts, ch2_counts, '-o')
    ax_hc.set_title(f"hit threshold {HIT_THRESHOLD} ADC")
    ax_hc.set_xlabel(f"# Hits in ch {ch1}")
    ax_hc.set_ylabel(f"# Hits in ch {ch2}")

    fig_hc.savefig(f"motor_scan_hits_channels.png", dpi=150)


if __name__ == "__main__":
    main()