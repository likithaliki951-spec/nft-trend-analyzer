"""Automated tests for multi-format dataset uploads, normalization, and validation."""

import io
import json
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from data_loader import (
    SUPPORTED_EXTENSIONS,
    export_dataframe_as_csv,
    generate_sample_nft_csv,
    get_excel_sheet_names,
    get_file_extension,
    load_uploaded_dataset,
    read_csv_with_fallback,
    read_delimited_text,
    read_json_data,
    read_jsonl_data,
    validate_and_diagnose_dataset,
)


def test_supported_extensions():
    assert ".csv" in SUPPORTED_EXTENSIONS
    assert ".xlsx" in SUPPORTED_EXTENSIONS
    assert ".json" in SUPPORTED_EXTENSIONS
    assert ".jsonl" in SUPPORTED_EXTENSIONS
    assert ".parquet" in SUPPORTED_EXTENSIONS
    assert ".txt" in SUPPORTED_EXTENSIONS


def test_load_csv_dataset():
    csv_bytes = b"sale_date,price_eth,sales_count\n2024-01-01,1.5,10\n2024-01-02,2.0,15\n"
    df, meta = load_uploaded_dataset(csv_bytes, "test_nft.csv")
    assert len(df) == 2
    assert list(df.columns) == ["sale_date", "price_eth", "sales_count"]
    assert meta["extension"] == ".csv"
    assert meta["clean_rows"] == 2


def test_load_excel_dataset():
    sample_df = pd.DataFrame(
        {
            "sale_date": ["2024-01-01", "2024-01-02"],
            "price_eth": [1.5, 2.0],
            "sales_count": [10, 15],
        }
    )
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        sample_df.to_excel(writer, sheet_name="Transactions", index=False)
        sample_df.to_excel(writer, sheet_name="Secondary", index=False)
    excel_bytes = buffer.getvalue()

    sheets = get_excel_sheet_names(excel_bytes)
    assert "Transactions" in sheets
    assert "Secondary" in sheets

    df, meta = load_uploaded_dataset(excel_bytes, "test_portfolio.xlsx", sheet_name="Transactions")
    assert len(df) == 2
    assert "price_eth" in df.columns
    assert meta["sheet_used"] == "Transactions"


def test_load_json_records_and_columns():
    # Record format (array of objects)
    records = [
        {"sale_date": "2024-01-01", "price_eth": 1.2, "sales_count": 5},
        {"sale_date": "2024-01-02", "price_eth": 1.4, "sales_count": 8},
    ]
    json_bytes = json.dumps(records).encode("utf-8")
    df_rec, meta = load_uploaded_dataset(json_bytes, "records.json")
    assert len(df_rec) == 2
    assert meta["clean_rows"] == 2

    # Wrapped API response format ({"data": [...]})
    wrapped = {"data": records, "status": "ok"}
    wrapped_bytes = json.dumps(wrapped).encode("utf-8")
    df_wrap, _ = load_uploaded_dataset(wrapped_bytes, "api_response.json")
    assert len(df_wrap) == 2


def test_load_jsonl_dataset():
    lines = [
        json.dumps({"sale_date": "2024-01-01", "price_eth": 1.1, "likes": 50}),
        json.dumps({"sale_date": "2024-01-02", "price_eth": 1.3, "likes": 75}),
        json.dumps({"sale_date": "2024-01-03", "price_eth": 1.2, "likes": 60}),
    ]
    jsonl_bytes = "\n".join(lines).encode("utf-8")
    df, meta = load_uploaded_dataset(jsonl_bytes, "stream.jsonl")
    assert len(df) == 3
    assert "likes" in df.columns
    assert meta["extension"] == ".jsonl"


def test_load_parquet_dataset():
    sample_df = pd.DataFrame(
        {
            "sale_date": ["2024-01-01", "2024-01-02"],
            "price_eth": [3.5, 4.0],
            "sales_count": [20, 25],
        }
    )
    buffer = io.BytesIO()
    sample_df.to_parquet(buffer, index=False)
    parquet_bytes = buffer.getvalue()

    df, meta = load_uploaded_dataset(parquet_bytes, "market.parquet")
    assert len(df) == 2
    assert meta["extension"] == ".parquet"


def test_load_delimited_text():
    # Tab-delimited text
    tab_bytes = b"sale_date\tprice_eth\tsales_count\n2024-01-01\t2.5\t12\n2024-01-02\t2.8\t18\n"
    df_tab, _ = load_uploaded_dataset(tab_bytes, "data.txt")
    assert len(df_tab) == 2
    assert len(df_tab.columns) == 3

    # Pipe-delimited text
    pipe_bytes = b"sale_date|price_eth|sales_count\n2024-01-01|2.5|12\n2024-01-02|2.8|18\n"
    df_pipe, _ = load_uploaded_dataset(pipe_bytes, "data_pipe.txt")
    assert len(df_pipe) == 2
    assert "price_eth" in df_pipe.columns


def test_empty_or_malformed_files_raise_clear_errors():
    # Empty file
    with pytest.raises(ValueError, match="empty"):
        load_uploaded_dataset(b"", "empty.csv")

    # Unsupported format
    with pytest.raises(ValueError, match="Unsupported file format"):
        load_uploaded_dataset(b"some content", "script.exe")

    # Malformed JSON
    with pytest.raises(ValueError, match="Malformed JSON"):
        load_uploaded_dataset(b"{this is not valid json:", "bad.json")


def test_validate_and_diagnose_dataset_ml_readiness():
    # ML-ready dataset with 14 rows
    dates = pd.date_range("2024-01-01", periods=14, freq="D")
    prices = np.linspace(1.0, 2.5, 14)
    sales = np.random.randint(10, 50, 14)
    df_ready = pd.DataFrame({"sale_date": dates, "price_eth": prices, "sales_count": sales})

    diag = validate_and_diagnose_dataset(df_ready)
    assert diag["ml_ready"] is True
    assert diag["inferred_date_col"] == "sale_date"
    assert diag["inferred_price_col"] == "price_eth"
    assert "ML-Ready" in diag["ml_status_message"]

    # Incomplete dataset without date column
    df_nodate = pd.DataFrame({"item_id": [1, 2, 3], "price_eth": [1.0, 2.0, 3.0]})
    diag_nodate = validate_and_diagnose_dataset(df_nodate)
    assert diag_nodate["ml_ready"] is False
    assert any("date" in w.lower() for w in diag_nodate["warnings"])


def test_generate_sample_nft_csv_and_export():
    sample_csv = generate_sample_nft_csv()
    assert "sale_date" in sample_csv
    assert "price_eth" in sample_csv

    df = pd.read_csv(io.StringIO(sample_csv))
    assert len(df) >= 12
    diag = validate_and_diagnose_dataset(df)
    assert diag["ml_ready"] is True

    exported_bytes = export_dataframe_as_csv(df)
    assert isinstance(exported_bytes, bytes)
    reloaded_df = pd.read_csv(io.BytesIO(exported_bytes))
    assert len(reloaded_df) == len(df)


def test_load_excel_without_openpyxl_raises_graceful_import_error():
    """When openpyxl is not available, loading Excel raises a friendly ImportError."""
    with patch("data_loader.HAS_OPENPYXL", False):
        with pytest.raises(ImportError, match="requires the 'openpyxl' package"):
            load_uploaded_dataset(b"dummy excel bytes", "test.xlsx")


def test_get_excel_sheet_names_without_openpyxl_returns_empty():
    """When openpyxl is not available, sheet inspection returns an empty list without error."""
    with patch("data_loader.HAS_OPENPYXL", False):
        assert get_excel_sheet_names(b"dummy excel bytes") == []


def test_load_parquet_without_pyarrow_raises_graceful_import_error():
    """When pyarrow is missing, loading Parquet raises a friendly ImportError."""
    with patch("pandas.read_parquet", side_effect=ImportError("No module named 'pyarrow'")):
        with pytest.raises(ImportError, match="requires the 'pyarrow' package"):
            load_uploaded_dataset(b"dummy parquet bytes", "test.parquet")
