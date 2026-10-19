import pandas as pd
import pytest

from src.analytics import customer_rfm, daily_demand, forecast_demand, sales_summary
from src.data_pipeline import clean_transactions


@pytest.fixture
def transactions():
    raw = pd.DataFrame(
        {
            "Invoice": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"],
            "InvoiceDate": pd.date_range("2024-01-01", periods=10, freq="D"),
            "Quantity": [2, 4, 3, 5, 2, 1, 6, 2, 3, 4],
            "Price": [10.0] * 10,
            "CustomerID": ["1", "1", "2", "2", "1", "3", "3", None, "2", "1"],
            "Description": ["Item"] * 10,
        }
    )
    cleaned, _ = clean_transactions(raw)
    return cleaned


def test_sales_summary_and_daily_demand(transactions):
    summary = sales_summary(transactions)

    assert summary["revenue"] == 320
    assert summary["orders"] == 10
    assert summary["customers"] == 3
    assert len(daily_demand(transactions)) == 10
    assert daily_demand(transactions).iloc[0] == 2


def test_forecast_uses_chronological_holdout_and_returns_baseline_metrics(transactions):
    result = forecast_demand(transactions, horizon=5, test_days=2, window=3)

    assert result["method"] == "3-day rolling-mean baseline"
    assert len(result["evaluation"]) == 2
    assert len(result["forecast"]) == 5
    assert set(result["metrics"]) == {"holdout_days", "mae", "rmse", "mape"}
    assert result["metrics"]["mae"] >= 0


def test_rfm_excludes_unknown_customers_and_marks_inactivity(transactions):
    rfm = customer_rfm(transactions, inactivity_days=5)

    assert set(rfm["CustomerID"]) == {"1", "2", "3"}
    assert {"RecencyDays", "Frequency", "Monetary", "Segment", "InactivityRisk"} <= set(rfm.columns)
    assert rfm["InactivityRisk"].isin(["Recently active", "Inactive threshold reached"]).all()


def test_forecast_rejects_too_little_history(transactions):
    with pytest.raises(ValueError, match="calendar days are needed"):
        forecast_demand(transactions.iloc[:3], window=7)
