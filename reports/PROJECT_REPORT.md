# RetailPulse Project Report

## Abstract

RetailPulse is a transaction analytics dashboard using the public Online Retail
II dataset. It demonstrates a validated ingestion and cleaning path, sales
summaries, explainable customer RFM/inactivity analysis, and a chronological
evaluation of a simple demand baseline. The application explicitly reports
when a requested business analysis cannot be supported by the available data.

## Objectives

- Provide repeatable cleaning for transaction CSV and Excel files.
- Summarize retail sales by time, product, and country.
- Calculate customer-level recency, invoice frequency, and monetary value.
- Evaluate a simple daily demand forecast without random time-series splits.
- Document limitations and keep the public demo data small.

## Dataset

Development used the UCI Online Retail II Excel workbook at
`data/raw/online_retail_II.xlsx`. The two sheets contain 525,461 and 541,910
rows (1,067,371 total) with dates from 2009-12-01 through 2011-12-09. Columns
include invoice, stock code, description, quantity, invoice date, unit price,
customer ID, and country. Customer IDs and product descriptions have missing
values; the raw data also contains repeated rows, returns/negative quantities,
and zero prices.

The included CSV in `data/sample/` is a systematic sample of every 50th row
from each sheet, derived from this public dataset. It is intended only for
demonstration. A large archive inspected during dataset selection identified
itself as synthetic and was not used as real transaction evidence.

## Methodology

Input column names are standardized against known aliases. Exact duplicate
rows, invalid dates, invalid numeric values, nonpositive quantities/prices,
and missing invoice identifiers are excluded from sale metrics. Sales value
is quantity multiplied by listed unit price. Missing customer identifiers
remain eligible for sales summaries but are excluded from customer analysis.

Customer RFM uses days since last purchase relative to the latest observed
transaction, unique invoice count, and summed sales value. Rules assign
descriptive customer segments and an inactivity flag; neither is a supervised
churn model.

Demand is aggregated into calendar-day unit totals, including zero-sale days.
The baseline forecast is the mean daily demand of the preceding seven days.
The most recent chronological period is held out for MAE, RMSE, and MAPE (MAPE
uses nonzero actual values only). Forecasts have no statistical uncertainty
interval and should not be used as operational ordering recommendations.

## Architecture

- `src/data_pipeline.py`: schema validation, CSV/Excel loading, cleaning, and
  data-quality counts.
- `src/analytics.py`: sales summary, daily demand, baseline forecast/evaluation,
  and customer RFM/risk indicators.
- `app.py`: Streamlit navigation, filters, charts, and report downloads.
- `tests/`: unit tests for pipeline and analytics behavior.
- `data/sample/`: small derived demo data; raw source files are not bundled.

## Results and evaluation

The full workbook was loaded through the project pipeline and produced these
observed results:

| Measure | Observed result |
|---|---:|
| Raw transaction lines | 1,067,371 |
| Exact duplicate lines removed (including across worksheets) | 34,335 |
| Nonpositive quantity lines removed | 22,496 |
| Nonpositive price lines removed | 2,626 |
| Invalid date / numeric lines removed | 0 / 0 |
| Missing invoice identifiers removed | 0 |
| Retained positive-sale lines | 1,007,914 |
| Retained lines missing customer ID | 228,489 |
| Revenue (positive quantity × price) | £20,476,634.02 |
| Units | 11,205,149 |
| Distinct invoices / identified customers | 40,078 / 5,878 |

The seven-day rolling-mean demand baseline was evaluated on the final 30
calendar days of the full workbook, with earlier dates used as its training
history. Observed holdout metrics were MAE **11,806.98 units/day**, RMSE
**17,800.29 units/day**, and MAPE **30.38%** (computed over nonzero actual
days). These values describe this specific historical holdout; they do not
establish general future accuracy. The included demo sample is smaller and
produces different values.

Automated tests cover column validation, data cleaning, empty inputs, chunked
CSV loading, sales summaries, RFM, forecast output, and chronological holdout
behavior. No trained-model accuracy, churn AUC, inventory fill rate, or
production business impact is claimed.

## Limitations

- The selected source has no on-hand inventory, lead-time, or reorder-point
  data; inventory optimization and stockout risk cannot be calculated.
- No valid churn label is present; inactivity is only a rule-based signal.
- The forecast is a simple baseline and can underperform seasonal or learned
  models.
- There are no store or promotion dimensions in the selected source.
- Demo data is a small sample and may not preserve the original population
  proportions or full customer purchase histories.

## Conclusion and future enhancements

The deliverable is a demonstrable, data-grounded analytics MVP. Next steps are
to validate on the full workbook, collect linked inventory and lead-time data,
perform rolling model comparisons, and construct a defensible churn target
before attempting supervised prediction. Deployment, public GitHub publishing,
and submission materials remain the user's actions.
