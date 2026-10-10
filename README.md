# Analysis of Trending NFTs Using Time-Series Data and Machine Learning

An interactive Streamlit college-project dashboard for exploring NFT datasets supplied as CSV files. It includes a market overview, time-series analysis, social-media engagement analysis, price prediction, and model evaluation.

The application does **not** connect to OpenSea, X/Twitter, or any live data feed. It analyzes only the CSV you upload. The optional built-in demo is generated synthetic data and is labeled as such throughout the dashboard.

## Features

- Upload a CSV and inspect detected columns, types, sample values, missingness, duplicate rows, and empty rows.
- Map date/time, price/target, and sales/activity columns manually when automatic suggestions need adjustment.
- Normalize blank cells, trim whitespace, remove empty rows and exact duplicate rows, and parse common currency-formatted numeric values.
- Plot price trends, sales/activity records, and numeric social-engagement fields when the corresponding data exists.
- Compare Linear Regression and Random Forest on a chronological 80/20 train/test split.
- Engineer calendar features and lagged target/market features. The test period is not shuffled; model inputs use prior observations rather than same-row market/social values.
- Report MAE, RMSE, and R², plus held-out actual-versus-predicted charts and prediction rows.
- Explain which fields or minimum data requirements are missing when a requested analysis cannot be run.

## Requirements

- Python 3.10 or newer
- Dependencies listed in `requirements.txt`

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

Open the local URL printed by Streamlit. In Replit, use the app preview.

## Run tests

```bash
python -m pytest -q
```

The tests exercise data cleaning, numeric parsing, time-feature chronology, model metrics, and insufficient-data handling.

## CSV guidance

The dashboard inspects all columns and suggests common fields by name. You can change its suggestions in the sidebar.

| Analysis | Helpful columns |
| --- | --- |
| Market overview and price trend | A parseable date/time field and numeric price field |
| Sales activity | Date/time plus a sales, transaction, trade, or volume field; without a sales field, only uploaded-row counts are plotted |
| Social engagement | Numeric likes, comments, replies, retweets, shares, views, impressions, followers, mentions, or engagement fields |
| Regression models | At least 12 rows with both a valid date/time value and numeric target |

Missing numeric feature values are imputed inside each model pipeline using training data only. Rows without a valid date or target are excluded from model evaluation. A chronological 80/20 split holds the latest observations out for testing. The comparison is a rolling one-step-ahead evaluation: a prior observed target may be used as the next row's lagged history. Metrics describe only this dataset's held-out period and are not a promised accuracy for future data.

Price and engagement values are not assumed to share a currency or unit. Charts and error metrics use the units present in the selected source columns. R² is a regression metric, not percentage accuracy, and can be negative.

## Project files

- `app.py` — Streamlit dashboard and visualizations
- `nft_analysis.py` — cleaning, column inference, feature engineering, synthetic demo generation, and model evaluation
- `tests/test_nft_analysis.py` — basic automated tests
- `requirements.txt` — Python dependencies
