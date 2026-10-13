
import pandas as pd
import matplotlib.pyplot as plt
import sys

path = str(sys.argv[1])

df = pd.read_csv(path, header=1)

run_group = df.groupby('run')

fig, ax = plt.subplots(1,1)

for run_id, run_df in run_group:
    if run_id != 1000:
        continue
    ax.plot(run_df["channel"], run_df["adc"], 'o', ms=2)

plt.show()
