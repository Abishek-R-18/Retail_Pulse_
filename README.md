# RetailPulse

RetailPulse is a small, reproducible retail analytics dashboard built around
actual transaction data. It prioritizes transparent calculations over claims
of unvalidated AI or production infrastructure.

## What it does

- Cleans CSV and Excel transaction data while reporting rows removed and missing customer IDs.
- Shows sales value, units, orders, top products, daily/monthly trends, and country summaries.
- Calculates customer recency, invoice frequency, monetary value (RFM), and a rule-based inactivity flag.
- Evaluates a rolling-mean daily-unit-demand baseline on a chronological holdout and provides a selectable forward forecast.
- Explains why inventory analytics are unavailable without stock-on-hand, lead-time, or reorder-point data.
- Supports date, country, and product filters, plus CSV downloads for transactions, RFM results, and forecasts.

The baseline forecast is not an AI model, does not provide prediction intervals,
and is evaluated only on the selected transaction data. The inactivity flag is
not a trained churn model. No inventory optimization is claimed because the
selected data has no stock-on-hand, lead-time, or reorder-point fields.

## Data selection and provenance

The main source used during development is the public UCI Online Retail II
workbook, stored locally at `data/raw/online_retail_II.xlsx`. It has
two worksheets and 1,067,371 transaction lines spanning 2009-12-01 through
2011-12-09, with Invoice, StockCode, Description, Quantity, InvoiceDate,
Price, Customer ID, and Country fields. The workbook contains missing customer
IDs, repeated rows, returns/negative quantities, and zero prices. Cleaning
counts are shown in the dashboard.

`data/reference/RetailPulse_Cleaned_Dataset.csv` is a small presentation-style
aggregation with repeated year/month/quarter fields and currency-prefixed
strings. It is kept for reference, not used as the analytics source. Original
project notes and the Power BI file are organized under `docs/reference/` and
`dashboards/source/`.

The repository includes `data/sample/online_retail_sample.csv`, a compact
systematic sample derived from the real workbook for a demo deployment. The
full workbook remains under `data/raw/` and is excluded from Git.
See [data/README.md](data/README.md) for regeneration details.

## Run locally (Windows PowerShell)

Python 3.10 or newer is recommended.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

The app starts with the included demo sample. Upload a CSV or Excel workbook
from the sidebar to analyze another source. The expected transaction fields
are invoice, invoice date, quantity, and unit price; product, customer, and
country fields are optional. Common Online Retail II column names are accepted.
CSV files are parsed and cleaned in chunks, with duplicate rows checked across
chunk boundaries. Excel worksheets are combined before cleaning. The cleaned
transactions are retained for interactive filtering and customer analysis, so
very large data still requires enough memory for the final cleaned table and
dashboard calculations; convert very large workbooks to CSV for chunked input.

Run tests:

```powershell
python -m pytest
```

## Project layout

```text
app.py
.streamlit/config.toml
src/
  analytics.py
  data_pipeline.py
data/
  raw/             # Local source workbook; excluded from Git
  reference/       # Local reference export; excluded from Git
  sample/          # Small derived demo CSV
docs/reference/    # Original planning notes and proposal
dashboards/source/ # Local Power BI source file
reports/           # Project report
scripts/
  build_demo_sample.py
tests/
```

The dark theme uses Streamlit's supported `.streamlit/config.toml` settings;
the dashboard avoids CSS overrides that can make text and backgrounds clash.
See [reports/PROJECT_REPORT.md](reports/PROJECT_REPORT.md) for the measured
evaluation and project limitations.

## Dataset and cleaning limitations

- Rows with invalid dates, missing invoices, nonnumeric values, returns or
  other nonpositive quantities, and nonpositive prices are omitted from sales
  analytics. Exact duplicate input rows are dropped.
- Revenue is calculated as positive quantity × listed unit price. The source
  price is GBP; no currency conversion or tax treatment is applied.
- Missing customer IDs remain usable for sales metrics but are excluded from
  customer-level RFM outputs.
- The demo sample is not a substitute for the complete two-year workbook.
- Product descriptions and countries are used as supplied; there is no product,
  store, promotion, or inventory master-data join.

## Deployment

### Streamlit Community Cloud

Create an empty GitHub repository, then run these commands from the project
root in PowerShell, replacing `YOUR_USERNAME` and `YOUR_REPO`:

```powershell
git init
git status --short
git check-ignore -v data/raw/online_retail_II.xlsx data/reference/RetailPulse_Cleaned_Dataset.csv dashboards/source/retailpulse_powerbi.pbix.zip
git add .
git status --short
git commit -m "Build RetailPulse analytics MVP"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

Before `git add`, confirm local raw/reference data, Power BI binaries, and
secrets are not staged; `.gitignore` excludes them. The small derived demo CSV
is intended to be committed. In Streamlit Community Cloud, create an app from
the pushed repository, choose `app.py` as the entrypoint, and deploy. The
committed demo sample is used by default. Uploaded files are processed by the
running app and are not written into the repository.

### Docker

```powershell
docker build -t retailpulse .
docker run --rm -p 8501:8501 retailpulse
```

The Docker image uses the included demo sample. No external services or
credentials are required.

## ZIDIO submission checklist

Suggested screenshots:

1. Executive overview with sales KPIs and the daily trend.
2. Sales analytics with monthly sales and country ranking.
3. Demand forecast including holdout MAE/RMSE/MAPE and forecast horizon.
4. Customer RFM segments and inactivity-risk indicator.
5. Inventory limitation page showing the data needed to enable that analysis.
6. Data-quality report.

For a short demo video, show the overview, apply a filter, navigate through
sales, forecasting, and customer analytics, then show the data-quality and
inventory limitation. State clearly that the forecast is a baseline and churn
risk is rule-based. For a separate reflection/feedback video, cover the data
cleaning decisions, what worked, the limits of the small sample, and the next
steps needed for inventory data and validated models. These videos and any
public deployment must be created separately; this project does not claim they
have already been published or submitted.

## Future work

Acquire a suitable inventory snapshot with valid SKU/store keys and lead times;
compare stronger forecasting models against the baseline using rolling
backtests; develop a defensible churn target from longitudinal customer history;
add model monitoring only after a model and reference data are available.
