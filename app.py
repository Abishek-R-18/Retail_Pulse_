"""RetailPulse: compact, evidence-based retail analytics dashboard."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.analytics import customer_rfm, forecast_demand, sales_summary
from src.data_pipeline import load_transactions

ROOT = Path(__file__).resolve().parent
SAMPLE_PATH = ROOT / "data" / "sample" / "online_retail_sample.csv"

st.set_page_config(
    page_title="RetailPulse | Retail Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(show_spinner="Loading and validating transactions...")
def _load_path(path: str) -> tuple[pd.DataFrame, dict[str, int]]:
    return load_transactions(path)


@st.cache_data(show_spinner="Loading and validating uploaded transactions...")
def _load_upload(content: bytes, filename: str) -> tuple[pd.DataFrame, dict[str, int]]:
    return load_transactions(BytesIO(content), filename=filename)


def _money(value: float) -> str:
    return f"£{value:,.2f}"


def _render_overview(data: pd.DataFrame) -> None:
    st.subheader("Executive overview")
    summary = sales_summary(data)
    first, last = summary["first_date"], summary["last_date"]
    st.caption(
        f"Cleaned positive sales from {first} to {last}. Revenue is quantity × listed unit price "
        "and is denominated in the source dataset's currency (GBP for Online Retail II)."
    )
    first_row = st.columns(2)
    first_row[0].metric("Sales value", _money(float(summary["revenue"])))
    first_row[1].metric("Units sold", f"{int(summary['units']):,}")
    second_row = st.columns(2)
    second_row[0].metric("Orders", f"{int(summary['orders']):,}")
    second_row[1].metric("Identified customers", f"{int(summary['customers']):,}")

    daily = (
        data.assign(Date=data["InvoiceDate"].dt.normalize())
        .groupby("Date", as_index=False)["Revenue"]
        .sum()
    )
    st.plotly_chart(
        px.line(daily, x="Date", y="Revenue", title="Daily sales value"),
        width="stretch",
        alt="Line chart of cleaned sales value by date.",
    )
    products = (
        data.groupby("Description", dropna=True)["Quantity"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .sort_values()
        .rename("Units")
        .reset_index()
    )
    if not products.empty:
        st.plotly_chart(
            px.bar(products, x="Units", y="Description", orientation="h", title="Top 10 products by units"),
            width="stretch",
            alt="Horizontal bar chart of the ten products with the most units sold.",
        )


def _render_sales(data: pd.DataFrame) -> None:
    st.subheader("Sales analytics")
    daily = (
        data.assign(Date=data["InvoiceDate"].dt.normalize())
        .groupby("Date", as_index=False)
        .agg(Revenue=("Revenue", "sum"), Units=("Quantity", "sum"), Orders=("Invoice", "nunique"))
    )
    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            px.line(daily, x="Date", y="Revenue", title="Sales value over time"),
            width="stretch",
            alt="Line chart showing sales value over time.",
        )
    with right:
        monthly = daily.assign(Month=daily["Date"].dt.to_period("M").astype(str)).groupby(
            "Month", as_index=False
        )["Revenue"].sum()
        st.plotly_chart(
            px.bar(monthly, x="Month", y="Revenue", title="Monthly sales value"),
            width="stretch",
            alt="Bar chart showing sales value by month.",
        )

    if "Country" in data and data["Country"].notna().any():
        countries = data.groupby("Country", dropna=True)["Revenue"].sum().nlargest(15).reset_index()
        st.plotly_chart(
            px.bar(countries, x="Revenue", y="Country", orientation="h", title="Top countries by sales value"),
            width="stretch",
            alt="Horizontal bar chart showing the top countries by sales value.",
        )
    st.download_button(
        "Download filtered transaction lines",
        data.to_csv(index=False).encode("utf-8"),
        file_name="retailpulse_filtered_transactions.csv",
        mime="text/csv",
    )


def _render_forecast(data: pd.DataFrame) -> dict[str, object] | None:
    st.subheader("Demand forecasting")
    st.info(
        "This is an evaluated rolling-mean baseline, not a trained AI model. "
        "It forecasts total daily units and does not provide uncertainty intervals."
    )
    horizon = st.slider("Forecast horizon (days)", min_value=7, max_value=60, value=30)
    try:
        result = forecast_demand(data, horizon=horizon)
    except ValueError as error:
        st.warning(str(error))
        return None
    metrics = result["metrics"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Holdout MAE (units/day)", f"{metrics['mae']:,.1f}")
    c2.metric("Holdout RMSE (units/day)", f"{metrics['rmse']:,.1f}")
    c3.metric(
        "Holdout MAPE",
        f"{metrics['mape']:.1f}%" if metrics["mape"] is not None else "Not defined",
    )
    evaluation = result["evaluation"]
    historical = result["history"].rename("Actual").reset_index()
    actual_forecast = pd.concat(
        [
            historical.assign(Series="Historical demand").rename(columns={"Actual": "Units"}),
            result["forecast"].rename(columns={"Forecast": "Units"}).assign(Series="Baseline forecast"),
        ],
        ignore_index=True,
    )
    st.plotly_chart(
        px.line(actual_forecast, x="Date", y="Units", color="Series", title="Daily demand and baseline forecast"),
        width="stretch",
        alt="Line chart of observed daily demand and the rolling-mean forecast.",
    )
    st.caption(f"Chronological evaluation: last {metrics['holdout_days']} days held out from fitting.")
    st.dataframe(
        evaluation,
        width="stretch",
        hide_index=True,
        alt="Chronological holdout demand values and baseline forecasts.",
    )
    st.download_button(
        "Download forecast",
        result["forecast"].to_csv(index=False).encode("utf-8"),
        file_name="retailpulse_demand_forecast.csv",
        mime="text/csv",
    )
    return result


def _render_customers(data: pd.DataFrame) -> None:
    st.subheader("Customer RFM and inactivity risk")
    threshold = st.slider("Inactivity threshold (days)", min_value=30, max_value=365, value=90, step=15)
    rfm = customer_rfm(data, inactivity_days=threshold)
    if rfm.empty:
        st.warning("No identified customer IDs are available for customer analytics.")
        return
    st.caption(
        "Segments use transparent rules over recency, invoice frequency, and sales value. "
        "The inactivity flag is a rule-based risk indicator, not a trained churn prediction."
    )
    counts = rfm["Segment"].value_counts().rename_axis("Segment").reset_index(name="Customers")
    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            px.bar(counts, x="Segment", y="Customers", title="RFM segment sizes"),
            width="stretch",
            alt="Bar chart showing customer counts by RFM segment.",
        )
    with right:
        st.plotly_chart(
            px.scatter(
                rfm,
                x="RecencyDays",
                y="Monetary",
                color="Segment",
                hover_data=["Frequency"],
                title="Customer recency and spend",
            ),
            width="stretch",
            alt="Scatter plot of customer recency and monetary value by RFM segment.",
        )
    risks = rfm["InactivityRisk"].value_counts()
    st.metric("Customers past inactivity threshold", f"{int(risks.get('Inactive threshold reached', 0)):,}")
    st.dataframe(
        rfm,
        width="stretch",
        hide_index=True,
        alt="Customer RFM metrics and rule-based inactivity indicator.",
    )
    st.download_button(
        "Download customer RFM report",
        rfm.to_csv(index=False).encode("utf-8"),
        file_name="retailpulse_customer_rfm.csv",
        mime="text/csv",
    )


def _render_quality(data: pd.DataFrame, report: dict[str, int]) -> None:
    st.subheader("Data quality and evaluation")
    st.caption("Cleaning preserves the source file and excludes invalid dates, returns/negative quantities, and nonpositive prices from sales analytics.")
    st.dataframe(
        pd.DataFrame([{"Check": key.replace("_", " ").title(), "Rows": value} for key, value in report.items()]),
        width="stretch",
        hide_index=True,
        alt="Transaction data-quality cleaning counts.",
    )
    st.write("Retained columns:", ", ".join(data.columns))


def _render_inventory() -> None:
    st.subheader("Inventory analytics")
    st.info(
        "Inventory analysis is unavailable for the transaction data in this app. The selected "
        "Online Retail II source has no on-hand stock, lead-time, or reorder-point fields. "
        "No stockout probabilities or reorder recommendations are inferred from sales alone."
    )
    st.markdown(
        "To support this analysis, provide a separate inventory snapshot with product/SKU keys, "
        "on-hand quantities, snapshot dates, and either lead times or validated reorder points. "
        "Store identifiers are also needed for store-level inventory."
    )


def main() -> None:
    st.title("RetailPulse")
    st.caption(
        "Customer analytics and demand insights grounded in retail transactions. "
        "The default source is a systematic 1-in-50 demo sample; displayed results reflect "
        "the currently loaded data, not the full workbook."
    )

    with st.sidebar:
        st.header("Data")
        uploaded = st.file_uploader("Upload transactions (CSV or Excel)", type=["csv", "xlsx"])
        page = st.radio(
            "Dashboard",
            [
                "Executive overview",
                "Sales analytics",
                "Demand forecasting",
                "Customer analytics",
                "Inventory analytics",
                "Data quality",
            ],
        )

    try:
        if uploaded is not None:
            data, quality = _load_upload(uploaded.getvalue(), uploaded.name)
            source_label = uploaded.name
        elif SAMPLE_PATH.exists():
            data, quality = _load_path(str(SAMPLE_PATH))
            source_label = "included real-data demo sample"
        else:
            st.error("No dataset is available. Add the demo CSV under data/sample or upload a CSV/Excel file.")
            st.stop()
    except (OSError, ValueError, pd.errors.ParserError, ImportError) as error:
        st.error(f"Could not load the selected dataset: {error}")
        st.stop()

    st.sidebar.caption(f"Source: {source_label} · {len(data):,} valid sales lines")
    if data.empty:
        st.warning("No valid positive-sale transactions remain after cleaning.")
        st.stop()

    min_date = data["InvoiceDate"].min().date()
    max_date = data["InvoiceDate"].max().date()
    with st.sidebar:
        date_range = st.date_input(
            "Date range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )
        available_countries = sorted(data["Country"].dropna().unique().tolist())
        selected_countries = st.multiselect("Country", available_countries, default=[])
        product_values = sorted(data["Description"].dropna().unique().tolist())
        selected_products = st.multiselect("Product description", product_values, default=[])

    filtered = data
    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        filtered = filtered.loc[
            filtered["InvoiceDate"].dt.date.between(date_range[0], date_range[1])
        ]
    if selected_countries:
        filtered = filtered.loc[filtered["Country"].isin(selected_countries)]
    if selected_products:
        filtered = filtered.loc[filtered["Description"].isin(selected_products)]
    if filtered.empty:
        st.warning("No sales match the selected filters. Adjust the date, country, or product filters.")
        return

    if page == "Executive overview":
        _render_overview(filtered)
    elif page == "Sales analytics":
        _render_sales(filtered)
    elif page == "Demand forecasting":
        _render_forecast(filtered)
    elif page == "Customer analytics":
        _render_customers(filtered)
    elif page == "Inventory analytics":
        _render_inventory()
    else:
        _render_quality(filtered, quality)


if __name__ == "__main__":
    main()
