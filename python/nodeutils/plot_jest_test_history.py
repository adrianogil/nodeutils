#!/usr/bin/env python3

import os
import sys

import pandas as pd
import matplotlib.pyplot as plt


def plot_test_history(csv_path="jest_test_counts.csv", out_png="jest_test_counts.png"):
    """
    Read a CSV of (date, tests) and plot number of Jest tests over time,
    saving both to screen and to PNG.
    """
    if not os.path.exists(csv_path):
        print(f"Error: '{csv_path}' not found.", file=sys.stderr)
        sys.exit(1)

    # load + sort
    df = pd.read_csv(
        csv_path,
        names=["date", "tests"],
        parse_dates=["date"],
        header=None
    )
    if df.empty:
        print("No data to plot.", file=sys.stderr)
        sys.exit(1)

    df.sort_values("date", inplace=True)

    # set up figure
    fig, ax = plt.subplots(figsize=(10, 6))

    ax.plot(df["date"], df["tests"], marker="o", linewidth=1)
    ax.set_title("Jest unit tests over time")
    ax.set_xlabel("Commit date")
    ax.set_ylabel("Number of tests")
    ax.grid(True, linestyle="--", alpha=0.5)

    # date formatting
    fig.autofmt_xdate(rotation=45)
    plt.tight_layout()

    # save first, then show
    plt.savefig(out_png, dpi=300, bbox_inches="tight")
    print(f"Saved plot to {out_png}")
    plt.show()


if __name__ == "__main__":
    # allow overriding CSV/path via args
    csv_file = sys.argv[1] if len(sys.argv) > 1 else "jest_test_counts.csv"
    output_png = sys.argv[2] if len(sys.argv) > 2 else "jest_test_counts.png"
    plot_test_history(csv_file, output_png)
