"""Multi-format dataset loading, tabular parsing, normalization, and validation.

Supports CSV, Excel (.xlsx, .xls), JSON, JSON Lines (.jsonl), Parquet, and delimited text (.txt).
Enforces zero-code execution, safe deserialization, and deterministic column normalization.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import sys
from typing import Any

# Ensure project root is prioritized in sys.path for robust Streamlit Community Cloud module resolution
_MODULE_ROOT = Path(__file__).resolve().parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

import numpy as np
import pandas as pd

try:
    import openpyxl  # noqa: F401
    HAS_OPENPYXL = True
except ImportError:
    openpyxl = None  # type: ignore
    HAS_OPENPYXL = False

from nft_analysis import (
    clean_dataframe,
    discover_social_columns,
    infer_column,
    parse_dates,
    parse_numeric,
)

__all__ = [
    "HAS_OPENPYXL",
    "MAX_UPLOAD_BYTES",
    "POTENTIAL_JOIN_KEYS",
    "SUPPORTED_EXTENSIONS",
    "discover_join_keys",
    "export_dataframe_as_csv",
    "generate_sample_nft_csv",
    "get_excel_sheet_names",
    "get_file_extension",
    "join_market_and_social_datasets",
    "load_uploaded_dataset",
    "read_csv_with_fallback",
    "read_delimited_text",
    "read_json_data",
    "read_jsonl_data",
    "validate_and_diagnose_dataset",
    "validate_join_keys",
]

SUPPORTED_EXTENSIONS = (".csv", ".xlsx", ".xls", ".json", ".jsonl", ".parquet", ".txt")
MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB max file upload limit


def get_file_extension(filename: str) -> str:
    """Return lowercase file extension from filename."""
    return Path(filename).suffix.lower()


def get_excel_sheet_names(file_bytes: bytes) -> list[str]:
    """Inspect and return the sheet names in an Excel workbook."""
    if not HAS_OPENPYXL:
        return []
    try:
        excel_file = pd.ExcelFile(io.BytesIO(file_bytes), engine="openpyxl")
        return list(excel_file.sheet_names)
    except Exception:
        try:
            excel_file = pd.ExcelFile(io.BytesIO(file_bytes))
            return list(excel_file.sheet_names)
        except Exception:
            return []


def read_csv_with_fallback(file_bytes: bytes) -> pd.DataFrame:
    """Read CSV bytes with multi-encoding and multi-separator fallback."""
    for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        for sep in (",", ";", "\t", "|"):
            try:
                df = pd.read_csv(io.BytesIO(file_bytes), encoding=encoding, sep=sep)
                if len(df.columns) > 1 or len(file_bytes) < 80:
                    return df
            except (UnicodeDecodeError, pd.errors.ParserError):
                continue
            except Exception:
                continue
    return pd.read_csv(io.BytesIO(file_bytes))


def read_json_data(file_bytes: bytes) -> pd.DataFrame:
    """Parse JSON bytes supporting record arrays, split orientation, and nested tables."""
    # Try standard UTF-8 decoding
    text = ""
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            text = file_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if not text:
        raise ValueError("Could not decode JSON file with standard encodings.")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed JSON syntax: {exc}")

    if isinstance(data, list):
        if not data:
            return pd.DataFrame()
        # Array of objects / records
        if isinstance(data[0], dict):
            return pd.DataFrame(data)
        # Array of primitives or lists
        return pd.DataFrame(data, columns=["value"])

    if isinstance(data, dict):
        # Check if wrapped in common API envelope (data, records, items, results)
        for key in ("data", "records", "items", "results", "nfts", "rows"):
            if key in data and isinstance(data[key], list) and len(data[key]) > 0:
                if isinstance(data[key][0], dict):
                    return pd.DataFrame(data[key])
        # Direct column-oriented dictionary
        try:
            return pd.DataFrame(data)
        except Exception:
            # Flatten dictionary into single row
            return pd.DataFrame([data])

    raise ValueError("Unrecognized JSON tabular structure. Expected an array of record objects.")


def read_jsonl_data(file_bytes: bytes) -> pd.DataFrame:
    """Parse JSON Lines (.jsonl) one line per JSON object."""
    records: list[dict[str, Any]] = []
    lines = io.BytesIO(file_bytes).readlines()
    if not lines:
        return pd.DataFrame()

    for idx, line in enumerate(lines, start=1):
        line_str = line.strip().decode("utf-8", errors="replace")
        if not line_str:
            continue
        try:
            parsed = json.loads(line_str)
            if isinstance(parsed, dict):
                records.append(parsed)
            else:
                records.append({"value": parsed})
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed JSON at line {idx}: {exc}")

    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)


def read_delimited_text(file_bytes: bytes) -> pd.DataFrame:
    """Parse delimited plain text (.txt) files using auto-detected separators."""
    for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        for sep in ("\t", "|", ",", ";"):
            try:
                df = pd.read_csv(io.BytesIO(file_bytes), encoding=encoding, sep=sep)
                if len(df.columns) > 1 and len(df) > 0:
                    return df
            except Exception:
                continue
    # Fallback to standard whitespace/tab separator
    try:
        return pd.read_csv(io.BytesIO(file_bytes), sep=r"\s+", engine="python")
    except Exception as exc:
        raise ValueError(
            "Could not parse text file as delimited tabular data. "
            "Plain text files must use tabs, commas, pipes (|), or semicolons as column separators."
        )


def load_uploaded_dataset(
    file_bytes: bytes,
    filename: str,
    sheet_name: str | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Safely load and normalize uploaded bytes into a pandas DataFrame without code execution.

    Supports:
    - .csv
    - .xlsx, .xls (with optional sheet selection)
    - .json (records, column-arrays, API response envelopes)
    - .jsonl (JSON Lines)
    - .parquet (Apache Parquet binary tabular format)
    - .txt (Delimited plain text tabular records)
    """
    if not file_bytes:
        raise ValueError("Uploaded file is empty (0 bytes).")
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError(f"Uploaded file exceeds maximum size limit ({MAX_UPLOAD_BYTES // (1024 * 1024)} MB).")

    ext = get_file_extension(filename)
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file format '{ext}'. "
            f"Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}."
        )

    raw_df: pd.DataFrame
    sheet_used: str | None = None

    if ext == ".csv":
        raw_df = read_csv_with_fallback(file_bytes)
    elif ext in (".xlsx", ".xls"):
        if not HAS_OPENPYXL:
            raise ImportError(
                "Excel file support requires the 'openpyxl' package. "
                "Please ensure 'openpyxl' is installed or upload your dataset in CSV, JSON, Parquet, or TXT format."
            )
        sheets = get_excel_sheet_names(file_bytes)
        target_sheet = sheet_name if sheet_name and sheet_name in sheets else (sheets[0] if sheets else 0)
        sheet_used = str(target_sheet)
        raw_df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=target_sheet, engine="openpyxl")
    elif ext == ".json":
        raw_df = read_json_data(file_bytes)
    elif ext == ".jsonl":
        raw_df = read_jsonl_data(file_bytes)
    elif ext == ".parquet":
        try:
            raw_df = pd.read_parquet(io.BytesIO(file_bytes))
        except ImportError as exc:
            raise ImportError(
                "Parquet file support requires the 'pyarrow' package. "
                "Please ensure 'pyarrow' is installed or upload your dataset in CSV, Excel, or JSON format."
            ) from exc
        except Exception as exc:
            raise ValueError(f"Could not read Parquet dataset: {exc}")
    elif ext == ".txt":
        raw_df = read_delimited_text(file_bytes)
    else:
        raise ValueError(f"Unsupported format: {ext}")

    if raw_df is None or raw_df.empty and len(raw_df.columns) == 0:
        raise ValueError(f"The uploaded {ext.upper()} file contains no tabular columns or records.")

    # Clean and normalize DataFrame
    cleaned_df, clean_stats = clean_dataframe(raw_df)

    metadata: dict[str, Any] = {
        "filename": filename,
        "extension": ext,
        "size_bytes": len(file_bytes),
        "size_formatted": f"{len(file_bytes) / 1024:.1f} KB" if len(file_bytes) < 1024 * 1024 else f"{len(file_bytes) / (1024 * 1024):.2f} MB",
        "sheet_used": sheet_used,
        "raw_rows": len(raw_df),
        "raw_cols": len(raw_df.columns),
        "clean_rows": len(cleaned_df),
        "clean_cols": len(cleaned_df.columns),
        "cleaning_stats": clean_stats,
    }

    return cleaned_df, metadata


def validate_and_diagnose_dataset(df: pd.DataFrame) -> dict[str, Any]:
    """Inspect dataset schema, infer NFT columns, and diagnose machine-learning readiness."""
    diagnostics: dict[str, Any] = {
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "columns": list(df.columns),
        "inferred_date_col": infer_column(df, "date"),
        "inferred_price_col": infer_column(df, "price"),
        "inferred_sales_col": infer_column(df, "sales"),
        "social_columns": discover_social_columns(df),
        "warnings": [],
        "ml_ready": False,
        "ml_status_message": "",
    }

    date_col = diagnostics["inferred_date_col"]
    price_col = diagnostics["inferred_price_col"]
    sales_col = diagnostics["inferred_sales_col"]

    # 1. Date column diagnostics
    if not date_col:
        diagnostics["warnings"].append(
            "No date or timestamp column detected. Time-series forecasting and rolling averages require a chronological date field."
        )
    else:
        parsed_dates = parse_dates(df[date_col])
        valid_date_count = int(parsed_dates.notna().sum())
        if valid_date_count < len(df) * 0.7:
            diagnostics["warnings"].append(
                f"Date field '{date_col}' contains {(1 - valid_date_count / max(1, len(df))) * 100:.1f}% unparseable or blank timestamps."
            )

    # 2. Price column diagnostics
    if not price_col:
        diagnostics["warnings"].append(
            "No price or valuation target column detected. Price predictions and valuation categorizations require a numeric price field."
        )
    else:
        parsed_prices = parse_numeric(df[price_col])
        valid_price_count = int(parsed_prices.notna().sum())
        if valid_price_count < 12:
            diagnostics["warnings"].append(
                f"Price field '{price_col}' has fewer than 12 valid numeric values, which is insufficient for machine learning."
            )
        neg_count = int((parsed_prices.dropna() < 0).sum())
        if neg_count > 0:
            diagnostics["warnings"].append(
                f"Found {neg_count} negative value(s) in '{price_col}'. NFT prices should typically be non-negative."
            )

    # 3. Overall ML Readiness evaluation
    if date_col and price_col:
        dates = parse_dates(df[date_col])
        prices = parse_numeric(df[price_col])
        valid_both = dates.notna() & prices.notna() & np.isfinite(prices)
        valid_count = int(valid_both.sum())

        if valid_count >= 12:
            diagnostics["ml_ready"] = True
            diagnostics["ml_status_message"] = (
                f"Dataset is ML-Ready: {valid_count} chronological observations with valid dates ('{date_col}') "
                f"and prices ('{price_col}'). All 7 analytical pages are fully enabled."
            )
        else:
            diagnostics["ml_ready"] = False
            diagnostics["ml_status_message"] = (
                f"Partial Dataset: Found only {valid_count} rows with both valid dates and prices. "
                f"At least 12 valid rows are required for ML train/validation benchmarking."
            )
    else:
        diagnostics["ml_ready"] = False
        diagnostics["ml_status_message"] = (
            "Schema Mapping Required: Please use the sidebar to select your date and price target fields."
        )

    return diagnostics


def generate_sample_nft_csv() -> str:
    """Generate a clean CSV string template illustrating the application's expected NFT schema."""
    template_data = [
        "sale_date,price_eth,sales_count,social_likes,social_comments,collection",
        "2024-01-01,1.2500,24,142,28,CyberApes Club",
        "2024-01-02,1.3100,31,168,34,CyberApes Club",
        "2024-01-03,1.2900,19,155,22,CyberApes Club",
        "2024-01-04,1.4500,45,210,48,CyberApes Club",
        "2024-01-05,1.5200,52,240,55,CyberApes Club",
        "2024-01-06,1.4800,38,205,39,CyberApes Club",
        "2024-01-07,1.6000,61,280,63,CyberApes Club",
        "2024-01-08,1.6500,59,295,68,CyberApes Club",
        "2024-01-09,1.5800,42,260,51,CyberApes Club",
        "2024-01-10,1.7200,68,315,74,CyberApes Club",
        "2024-01-11,1.8000,74,350,82,CyberApes Club",
        "2024-01-12,1.7500,65,330,77,CyberApes Club",
        "2024-01-13,1.9200,82,390,95,CyberApes Club",
        "2024-01-14,2.0500,90,420,104,CyberApes Club",
    ]
    return "\n".join(template_data)


def export_dataframe_as_csv(df: pd.DataFrame) -> bytes:
    """Export normalized pandas DataFrame to UTF-8 encoded CSV bytes."""
    return df.to_csv(index=False).encode("utf-8")


# ==============================================================================
# Separate Market & Social Engagement Dataset Joining
# ==============================================================================

POTENTIAL_JOIN_KEYS = (
    "collection",
    "collection_slug",
    "contract_address",
    "contract",
    "token_id",
    "tokenid",
    "permalink",
    "slug",
    "asset_id",
    "name",
    "id",
    "sale_date",
    "date",
    "timestamp",
    "datetime",
)


def discover_join_keys(df_market: pd.DataFrame, df_social: pd.DataFrame) -> list[str]:
    """Identify common join key candidate columns present in both datasets.

    Prioritizes canonical NFT collection, asset, and temporal keys before other common columns.
    """
    if df_market is None or df_social is None or df_market.empty or df_social.empty:
        return []

    market_cols = list(df_market.columns)
    social_cols = list(df_social.columns)

    # 1. Exact matches
    exact_matches = set(market_cols).intersection(set(social_cols))

    # 2. Case-insensitive matches (mapping lower -> original in df_market)
    market_lower_map = {c.lower(): c for c in market_cols}
    social_lower_map = {c.lower(): c for c in social_cols}
    common_lowers = set(market_lower_map.keys()).intersection(set(social_lower_map.keys()))

    discovered: list[str] = []
    # Prioritize POTENTIAL_JOIN_KEYS
    for key in POTENTIAL_JOIN_KEYS:
        k_low = key.lower()
        if k_low in common_lowers:
            actual_col = market_lower_map[k_low]
            if actual_col not in discovered:
                discovered.append(actual_col)

    # Add remaining exact matches
    for col in sorted(exact_matches):
        if col not in discovered:
            discovered.append(col)

    # Add remaining case-insensitive matches
    for k_low in sorted(common_lowers):
        actual_col = market_lower_map[k_low]
        if actual_col not in discovered:
            discovered.append(actual_col)

    return discovered


def validate_join_keys(
    df_market: pd.DataFrame, df_social: pd.DataFrame, join_key: str
) -> dict[str, Any]:
    """Validate schema compatibility, key overlaps, null counts, and many-to-many risks for a proposed join."""
    if df_market is None or df_market.empty:
        raise ValueError("Market dataset is empty or undefined.")
    if df_social is None or df_social.empty:
        raise ValueError("Social dataset is empty or undefined.")

    # Locate column in both DataFrames (case-insensitive fallback if needed)
    market_col = None
    for c in df_market.columns:
        if c == join_key or c.lower() == join_key.lower():
            market_col = c
            break

    social_col = None
    for c in df_social.columns:
        if c == join_key or c.lower() == join_key.lower():
            social_col = c
            break

    if not market_col:
        raise ValueError(f"Join key '{join_key}' was not found in the market dataset columns.")
    if not social_col:
        raise ValueError(f"Join key '{join_key}' was not found in the social dataset columns.")

    # Clean key series safely (trimming whitespace while preserving case)
    m_keys = df_market[market_col].dropna().astype(str).str.strip()
    s_keys = df_social[social_col].dropna().astype(str).str.strip()

    market_nulls = int(df_market[market_col].isna().sum())
    social_nulls = int(df_social[social_col].isna().sum())

    market_total = len(df_market)
    social_total = len(df_social)

    market_uniques = int(m_keys.nunique())
    social_uniques = int(s_keys.nunique())

    market_duplicates = len(m_keys) - market_uniques
    social_duplicates = len(s_keys) - social_uniques

    set_market = set(m_keys.unique())
    set_social = set(s_keys.unique())
    overlap_keys = set_market.intersection(set_social)
    overlap_count = len(overlap_keys)

    market_overlap_pct = (overlap_count / max(1, market_uniques)) * 100.0
    social_overlap_pct = (overlap_count / max(1, social_uniques)) * 100.0

    is_many_to_many = market_duplicates > 0 and social_duplicates > 0

    warnings: list[str] = []
    if overlap_count == 0:
        warnings.append(
            f"Zero matching keys between datasets on '{join_key}'. An inner join will yield an empty table."
        )
    elif market_overlap_pct < 20.0 or social_overlap_pct < 20.0:
        warnings.append(
            f"Low key overlap: only {overlap_count} unique keys match ({market_overlap_pct:.1f}% of market, "
            f"{social_overlap_pct:.1f}% of social)."
        )

    if is_many_to_many:
        warnings.append(
            f"Many-to-many relationship detected: duplicate values of '{join_key}' exist in both datasets "
            f"({market_duplicates} in market, {social_duplicates} in social). "
            f"This may multiply row counts via cartesian expansion."
        )

    if market_nulls > 0:
        warnings.append(f"Market dataset contains {market_nulls} null/missing join keys.")
    if social_nulls > 0:
        warnings.append(f"Social dataset contains {social_nulls} null/missing join keys.")

    return {
        "join_key": join_key,
        "market_column": market_col,
        "social_column": social_col,
        "market_rows": market_total,
        "social_rows": social_total,
        "market_nulls": market_nulls,
        "social_nulls": social_nulls,
        "market_unique_keys": market_uniques,
        "social_unique_keys": social_uniques,
        "market_duplicates": market_duplicates,
        "social_duplicates": social_duplicates,
        "overlap_unique_count": overlap_count,
        "market_overlap_pct": round(market_overlap_pct, 2),
        "social_overlap_pct": round(social_overlap_pct, 2),
        "is_many_to_many": is_many_to_many,
        "warnings": warnings,
    }


def join_market_and_social_datasets(
    df_market: pd.DataFrame,
    df_social: pd.DataFrame,
    join_key: str,
    join_type: str = "inner",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Safely combine separate market/transaction and social engagement datasets into a unified analysis schema.

    Enforces column alignment, strips whitespace on join keys, warns against many-to-many Cartesian explosions,
    and returns comprehensive join diagnostic statistics.
    """
    valid_types = ("inner", "left", "right", "outer")
    join_type_norm = join_type.lower()
    if join_type_norm not in valid_types:
        raise ValueError(f"Invalid join_type '{join_type}'. Supported: {', '.join(valid_types)}.")

    validation = validate_join_keys(df_market, df_social, join_key)
    m_col = validation["market_column"]
    s_col = validation["social_column"]

    # Copy to avoid mutating user DataFrames
    m_df = df_market.copy()
    s_df = df_social.copy()

    # Clean join keys (strip whitespace if object/string type)
    if m_df[m_col].dtype == object or pd.api.types.is_string_dtype(m_df[m_col]):
        m_df[m_col] = m_df[m_col].astype(str).str.strip()
    if s_df[s_col].dtype == object or pd.api.types.is_string_dtype(s_df[s_col]):
        s_df[s_col] = s_df[s_col].astype(str).str.strip()

    # If column names differ in case, align to market column name
    if m_col != s_col:
        s_df = s_df.rename(columns={s_col: m_col})
        effective_key = m_col
    else:
        effective_key = m_col

    # Perform merge with informative suffixes for non-key column overlaps
    joined_df = pd.merge(
        m_df,
        s_df,
        on=effective_key,
        how=join_type_norm,
        suffixes=("_market", "_social"),
    )

    # Clean and normalize merged dataframe
    clean_joined, clean_stats = clean_dataframe(joined_df)

    # Calculate matched records
    m_non_keys = [c for c in m_df.columns if c != effective_key]
    s_non_keys = [c for c in s_df.columns if c != effective_key]

    if m_non_keys and s_non_keys:
        sample_m_col = m_non_keys[0] if m_non_keys[0] in clean_joined.columns else f"{m_non_keys[0]}_market"
        sample_s_col = s_non_keys[0] if s_non_keys[0] in clean_joined.columns else f"{s_non_keys[0]}_social"
        matched_mask = clean_joined[sample_m_col].notna() & clean_joined[sample_s_col].notna()
        matched_count = int(matched_mask.sum())
    else:
        matched_count = len(clean_joined)

    diagnostics: dict[str, Any] = {
        "join_key": effective_key,
        "join_type": join_type_norm,
        "market_rows": len(df_market),
        "social_rows": len(df_social),
        "joined_rows": len(clean_joined),
        "matched_records": matched_count,
        "unmatched_market_records": max(0, len(clean_joined) - matched_count) if join_type_norm in ("left", "outer") else 0,
        "unmatched_social_records": max(0, len(clean_joined) - matched_count) if join_type_norm in ("right", "outer") else 0,
        "market_unique_keys": validation["market_unique_keys"],
        "social_unique_keys": validation["social_unique_keys"],
        "overlap_unique_count": validation["overlap_unique_count"],
        "is_many_to_many": validation["is_many_to_many"],
        "warnings": validation["warnings"],
        "cleaning_stats": clean_stats,
    }

    return clean_joined, diagnostics
