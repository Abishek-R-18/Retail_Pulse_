"""Traceable retail metrics derived from cleaned transaction lines."""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd


def sales_summary(transactions: pd.DataFrame) -> dict[str, float | int | str | None]:
    if transactions.empty:
        return {
            "revenue": 0.0,
            "units": 0,
            "orders": 0,
            "customers": 0,
            "first_date": None,
            "last_date": None,
        }
    customers = transactions["CustomerID"].nunique() if "CustomerID" in transactions else 0
    return {
        "revenue": float(transactions["Revenue"].sum()),
        "units": int(transactions["Quantity"].sum()),
        "orders": int(transactions["Invoice"].nunique()),
        "customers": int(customers),
        "first_date": transactions["InvoiceDate"].min().strftime("%Y-%m-%d"),
        "last_date": transactions["InvoiceDate"].max().strftime("%Y-%m-%d"),
    }


def daily_demand(transactions: pd.DataFrame) -> pd.Series:
    if transactions.empty:
        return pd.Series(dtype="float64", name="Demand")
    demand = (
        transactions.assign(Date=transactions["InvoiceDate"].dt.normalize())
        .groupby("Date")["Quantity"]
        .sum()
        .sort_index()
    )
    full_index = pd.date_range(demand.index.min(), demand.index.max(), freq="D")
    result = demand.reindex(full_index, fill_value=0).astype(float)
    result.index.name = "Date"
    result.name = "Demand"
    return result


def forecast_demand(
    transactions: pd.DataFrame,
    *,
    horizon: int = 30,
    test_days: int = 30,
    window: int = 7,
) -> dict[str, object]:
    """Evaluate a rolling-mean baseline on the latest holdout and forecast ahead."""
    if horizon < 1 or test_days < 1 or window < 1:
        raise ValueError("horizon, test_days, and window must be positive integers.")
    series = daily_demand(transactions)
    if len(series) < window + 2:
        raise ValueError(f"At least {window + 2} calendar days are needed to forecast.")

    holdout = min(test_days, max(1, len(series) // 5))
    train = series.iloc[:-holdout]
    actual = series.iloc[-holdout:]
    baseline = float(train.tail(window).mean())
    predicted = pd.Series(baseline, index=actual.index, name="Forecast")
    errors = actual.to_numpy(dtype=float) - predicted.to_numpy(dtype=float)
    nonzero_actual = actual.to_numpy(dtype=float) != 0
    metrics: dict[str, float | int | None] = {
        "holdout_days": int(holdout),
        "mae": float(np.mean(np.abs(errors))),
        "rmse": float(np.sqrt(np.mean(np.square(errors)))),
        "mape": (
            float(np.mean(np.abs(errors[nonzero_actual] / actual.to_numpy()[nonzero_actual])) * 100)
            if nonzero_actual.any()
            else None
        ),
    }

    forecast_values = float(series.tail(window).mean())
    forecast_start = pd.Timestamp(series.index[-1]) + timedelta(days=1)
    forecast_index = pd.date_range(forecast_start, periods=horizon)
    forecast = pd.DataFrame(
        {"Date": forecast_index, "Forecast": np.repeat(forecast_values, horizon)}
    )
    evaluation = pd.DataFrame(
        {"Date": actual.index, "Actual": actual.values, "Forecast": predicted.values}
    )
    return {
        "history": series,
        "evaluation": evaluation,
        "forecast": forecast,
        "metrics": metrics,
        "method": f"{window}-day rolling-mean baseline",
    }


def customer_rfm(
    transactions: pd.DataFrame, *, inactivity_days: int = 90
) -> pd.DataFrame:
    """Calculate customer RFM and simple inactivity risk; no trained churn model."""
    if inactivity_days < 1:
        raise ValueError("inactivity_days must be at least one.")
    if transactions.empty or "CustomerID" not in transactions:
        return pd.DataFrame(
            columns=[
                "CustomerID",
                "RecencyDays",
                "Frequency",
                "Monetary",
                "Segment",
                "InactivityRisk",
            ]
        )
    identified = transactions.dropna(subset=["CustomerID"])
    if identified.empty:
        return pd.DataFrame(
            columns=[
                "CustomerID",
                "RecencyDays",
                "Frequency",
                "Monetary",
                "Segment",
                "InactivityRisk",
            ]
        )
    snapshot = pd.Timestamp(identified["InvoiceDate"].max()).normalize() + timedelta(days=1)
    rfm = (
        identified.groupby("CustomerID", observed=True)
        .agg(
            LastPurchase=("InvoiceDate", "max"),
            Frequency=("Invoice", "nunique"),
            Monetary=("Revenue", "sum"),
        )
        .reset_index()
    )
    rfm["RecencyDays"] = (snapshot - rfm["LastPurchase"].dt.normalize()).dt.days
    median_recency = rfm["RecencyDays"].median()
    median_frequency = rfm["Frequency"].median()
    median_monetary = rfm["Monetary"].median()

    def segment(row: pd.Series) -> str:
        if (
            row["RecencyDays"] <= median_recency
            and row["Frequency"] >= median_frequency
            and row["Monetary"] >= median_monetary
        ):
            return "Best customers"
        if row["Frequency"] >= median_frequency and row["RecencyDays"] <= rfm["RecencyDays"].quantile(0.75):
            return "Loyal customers"
        if row["RecencyDays"] >= rfm["RecencyDays"].quantile(0.75):
            return "At risk"
        if row["Frequency"] == 1:
            return "One-time customers"
        return "Regular customers"

    rfm["Segment"] = rfm.apply(segment, axis=1)
    rfm["InactivityRisk"] = np.where(
        rfm["RecencyDays"] >= inactivity_days, "Inactive threshold reached", "Recently active"
    )
    return rfm[
        ["CustomerID", "RecencyDays", "Frequency", "Monetary", "Segment", "InactivityRisk"]
    ].sort_values(["Monetary", "Frequency"], ascending=False, ignore_index=True)
