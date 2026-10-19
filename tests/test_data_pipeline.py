import pandas as pd
import pytest

from src.data_pipeline import clean_transactions, load_transactions


def _raw():
    return pd.DataFrame(
        {
            "Invoice": ["A", "A", "B", "C", "D", "E", "F", "G"],
            "StockCode": ["x", "x", "y", "z", "w", "q", "r", "s"],
            "InvoiceDate": [
                "2011-01-01",
                "2011-01-01",
                "2011-01-02",
                "bad date",
                "2011-01-04",
                "2011-01-05",
                "2011-01-06",
                "2011-01-07",
            ],
            "Quantity": [2, 2, -1, 1, "not a number", 1, 1.5, 1],
            "Price": [3.0, 3.0, 4.0, 2.0, 2.0, 0, 2.0, float("inf")],
            "Customer ID": [10, 10, 11, 12, 13, None, 14, 15],
        }
    )


def test_clean_transactions_removes_duplicate_invalid_and_nonpositive_lines():
    cleaned, quality = clean_transactions(_raw())

    assert len(cleaned) == 1
    assert cleaned.iloc[0]["Revenue"] == 6
    assert cleaned.iloc[0]["CustomerID"] == "10"
    assert quality["input_rows"] == 8
    assert quality["duplicate_rows_removed"] == 1
    assert quality["invalid_dates_removed"] == 1
    assert quality["invalid_numeric_rows_removed"] == 3
    assert quality["nonpositive_quantity_rows_removed"] == 1
    assert quality["nonpositive_price_rows_removed"] == 1
    assert quality["missing_invoice_rows_removed"] == 0


def test_missing_required_column_has_actionable_error():
    with pytest.raises(ValueError, match="Missing required transaction columns"):
        clean_transactions(pd.DataFrame({"Invoice": ["A"], "Quantity": [1]}))


def test_empty_csv_is_reported(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("Invoice,InvoiceDate,Quantity,Price\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no transaction rows"):
        load_transactions(path)


def test_csv_loader_parses_across_small_chunks(tmp_path):
    path = tmp_path / "transactions.csv"
    path.write_text(
        "Invoice,InvoiceDate,Quantity,Price,Customer ID\n"
        "A,2024-01-01,2,3.5,12\n"
        "A,2024-01-01,2,3.5,12\n"
        "B,2024-01-02,1,4.0,13\n",
        encoding="utf-8",
    )

    transactions, quality = load_transactions(path, chunksize=1)

    assert len(transactions) == 2
    assert transactions["Revenue"].tolist() == [7.0, 4.0]
    assert quality["retained_rows"] == 2
    assert quality["duplicate_rows_removed"] == 1
