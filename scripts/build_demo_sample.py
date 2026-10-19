"""Create a small, reproducible sample from the local UCI Online Retail II workbook."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "raw" / "online_retail_II.xlsx"
TARGET = ROOT / "data" / "sample" / "online_retail_sample.csv"
EVERY_NTH_ROW = 50


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(
            f"Place the original workbook at {SOURCE} before building the demo sample."
        )
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    sheets = pd.read_excel(SOURCE, sheet_name=None)
    sample = pd.concat(
        [frame.iloc[::EVERY_NTH_ROW] for frame in sheets.values()],
        ignore_index=True,
    )
    sample.to_csv(TARGET, index=False)
    print(f"Wrote {len(sample):,} sampled source rows to {TARGET}")


if __name__ == "__main__":
    main()
