# Data

`sample/online_retail_sample.csv` is a small systematic sample of the public UCI
Online Retail II workbook (`raw/online_retail_II.xlsx`), sampled every 50th row
from each worksheet. The sample is derived from real historical transactions
and does not contain the full source dataset.

The original workbook is intentionally excluded from Git by `.gitignore`. To
regenerate the demo sample, place the workbook at
`data/raw/online_retail_II.xlsx` and run:

```powershell
python scripts\build_demo_sample.py
```

The workbook's fields do not include on-hand inventory, lead time, or reorder
points. Inventory optimization is therefore not supported by this source.
