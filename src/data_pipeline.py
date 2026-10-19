"""Loading, schema validation, and cleaning for retail transactions."""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO, Iterable

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = {"invoice", "invoicedate", "quantity", "price"}

_ALIASES = {
    "invoice": "Invoice",
    "invoiceno": "Invoice",
    "invoicenumber": "Invoice",
    "stockcode": "StockCode",
    "productcode": "StockCode",
    "description": "Description",
    "product": "Description",
    "quantity": "Quantity",
    "invoicedate": "InvoiceDate",
    "date": "InvoiceDate",
    "price": "Price",
    "unitprice": "Price",
    "customerid": "CustomerID",
    "customer": "CustomerID",
    "country": "Country",
}


def _key(value: object) -> str:
    return "".join(character for character in str(value).casefold() if character.isalnum())


def standardize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Rename known column variants to the canonical Online Retail schema."""
    renamed: dict[object, str] = {}
    for column in frame.columns:
        name = _ALIASES.get(_key(column))
        if name:
            if name in renamed.values():
                raise ValueError(f"Multiple input columns map to {name!r}.")
            renamed[column] = name
    result = frame.rename(columns=renamed).copy()
    missing = sorted({"Invoice", "InvoiceDate", "Quantity", "Price"} - set(result.columns))
    if missing:
        raise ValueError(
            "Missing required transaction columns: "
            + ", ".join(missing)
            + ". Expected invoice, date, quantity, and unit price fields."
        )
    return result


def clean_transactions(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Return valid positive-sale lines and auditable cleaning counts."""
    frame = standardize_columns(raw)
    quality = {
        "input_rows": int(len(frame)),
        "duplicate_rows_removed": int(frame.duplicated().sum()),
        "missing_customer_ids": 0,
        "invalid_dates_removed": 0,
        "invalid_numeric_rows_removed": 0,
        "nonpositive_quantity_rows_removed": 0,
        "nonpositive_price_rows_removed": 0,
        "missing_invoice_rows_removed": 0,
        "missing_descriptions": 0,
    }
    frame = frame.drop_duplicates().copy()

    frame["InvoiceDate"] = pd.to_datetime(frame["InvoiceDate"], errors="coerce")
    quality["invalid_dates_removed"] = int(frame["InvoiceDate"].isna().sum())
    frame = frame.loc[frame["InvoiceDate"].notna()].copy()

    for column in ("Quantity", "Price"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    quantities = frame["Quantity"].to_numpy(dtype="float64")
    prices = frame["Price"].to_numpy(dtype="float64")
    invalid_numeric = (
        frame["Quantity"].isna()
        | frame["Price"].isna()
        | ~np.isfinite(quantities)
        | ~np.isfinite(prices)
        | (quantities != np.floor(quantities))
        | (quantities >= float(2**63))
        | ~np.isfinite(quantities * prices)
    )
    quality["invalid_numeric_rows_removed"] = int(invalid_numeric.sum())
    frame = frame.loc[~invalid_numeric].copy()

    quality["nonpositive_quantity_rows_removed"] = int((frame["Quantity"] <= 0).sum())
    frame = frame.loc[frame["Quantity"] > 0].copy()
    quality["nonpositive_price_rows_removed"] = int((frame["Price"] <= 0).sum())
    frame = frame.loc[frame["Price"] > 0].copy()

    invoice_missing = frame["Invoice"].isna() | frame["Invoice"].astype("string").str.strip().eq("")
    quality["missing_invoice_rows_removed"] = int(invoice_missing.sum())
    frame = frame.loc[~invoice_missing].copy()

    if "CustomerID" in frame.columns:
        quality["missing_customer_ids"] = int(frame["CustomerID"].isna().sum())
        customer_ids = frame["CustomerID"].astype("string").str.strip()
        frame["CustomerID"] = customer_ids.str.replace(r"\.0$", "", regex=True)
        frame.loc[customer_ids.isna() | customer_ids.eq(""), "CustomerID"] = pd.NA
    else:
        quality["missing_customer_ids"] = int(len(frame))
        frame["CustomerID"] = pd.NA

    for column in ("StockCode", "Description", "Country"):
        if column not in frame.columns:
            frame[column] = pd.NA
    quality["missing_descriptions"] = int(frame["Description"].isna().sum())
    frame["Invoice"] = frame["Invoice"].astype("string").str.strip()
    frame["StockCode"] = frame["StockCode"].astype("string").str.strip()
    frame["Description"] = frame["Description"].astype("string").str.strip()
    frame["Country"] = frame["Country"].astype("string").str.strip()
    frame["Revenue"] = frame["Quantity"] * frame["Price"]
    frame["Quantity"] = frame["Quantity"].astype("int64")

    quality["retained_rows"] = int(len(frame))
    return frame.reset_index(drop=True), quality


def _clean_batches(
    batches: Iterable[pd.DataFrame], *, deduplicate_input: bool = False
) -> tuple[pd.DataFrame, dict[str, int]]:
    report_keys = (
        "input_rows",
        "duplicate_rows_removed",
        "invalid_dates_removed",
        "invalid_numeric_rows_removed",
        "nonpositive_quantity_rows_removed",
        "nonpositive_price_rows_removed",
        "missing_invoice_rows_removed",
        "missing_descriptions",
    )
    quality = {key: 0 for key in report_keys}
    cleaned_batches = []
    seen_hashes: set[int] = set()
    for batch in batches:
        if batch.empty:
            continue
        if deduplicate_input:
            hashes = pd.util.hash_pandas_object(batch, index=False)
            duplicates = hashes.isin(seen_hashes) | hashes.duplicated()
            quality["duplicate_rows_removed"] += int(duplicates.sum())
            seen_hashes.update(int(value) for value in hashes.loc[~duplicates])
            batch = batch.loc[~duplicates]
            if batch.empty:
                continue
        cleaned, batch_quality = clean_transactions(batch)
        for key in report_keys:
            if key != "duplicate_rows_removed":
                quality[key] += batch_quality[key]
        cleaned_batches.append(cleaned)
    if not cleaned_batches:
        raise ValueError("The selected file contains no transaction rows.")

    combined = pd.concat(cleaned_batches, ignore_index=True)
    cross_batch_duplicates = int(combined.duplicated().sum())
    combined = combined.drop_duplicates().reset_index(drop=True)
    quality["duplicate_rows_removed"] += cross_batch_duplicates
    quality["missing_customer_ids"] = int(combined["CustomerID"].isna().sum())
    quality["missing_descriptions"] = int(combined["Description"].isna().sum())
    quality["retained_rows"] = int(len(combined))
    return combined, quality


def load_transactions(
    source: str | Path | BinaryIO,
    *,
    filename: str | None = None,
    chunksize: int = 100_000,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Load CSV or Excel transactions; CSV input is parsed incrementally."""
    source_name = filename or str(getattr(source, "name", source))
    suffix = Path(source_name).suffix.casefold()

    if suffix == ".csv":
        if chunksize < 1:
            raise ValueError("chunksize must be a positive integer.")
        with pd.read_csv(
            source, chunksize=chunksize, encoding="utf-8-sig", dtype="string"
        ) as reader:
            return _clean_batches(reader, deduplicate_input=True)
    elif suffix == ".xlsx":
        sheets = pd.read_excel(source, sheet_name=None)
        if not sheets:
            raise ValueError("The Excel workbook contains no worksheets.")
        return clean_transactions(pd.concat(sheets.values(), ignore_index=True))
    else:
        raise ValueError("Unsupported file type. Upload a CSV or Excel workbook.")
