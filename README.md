# Analysis of Trending NFTs Using Time-Series Data and Machine Learning

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A research-oriented analytics and machine-learning benchmarking dashboard for exploring Non-Fungible Token (NFT) transaction datasets. Built with Python and Streamlit, this application provides leak-free chronological time-series analysis, cross-metric social engagement correlations, and machine-learning price forecasting.

> [!NOTE]
> This application does **not** connect to live marketplace APIs (such as OpenSea or LooksRare) or live social-media scrapers. It operates strictly on user-supplied CSV files held in-memory during the active browser session. The built-in demonstration dataset is generated synthetically and is explicitly labeled throughout the interface.

---

## Visual Direction & Interface Design

The dashboard is built with a research-grade dark theme:
- **Palette**: Deep charcoal/navy background (`#0b0f19`), secondary slate containers (`#131b2e`), with subtle violet (`#8b5cf6`) and electric-blue (`#38bdf8`) accents.
- **KPI Metrics**: Restrained, accessible cards displaying key performance indicators, summary statistics, and data-quality notices.
- **Interactive Visualizations**: Unified Plotly dark theme with subtle gridlines, dark tooltip overlays, and high-contrast trace colors.
- **Layout**: Fully responsive layout designed for both desktop analysis and mobile/smaller screens with an intuitive sidebar navigation.

---

## Core Dashboard Pages

### 1. 📊 Market Overview
- **Record Diagnostics**: Total valid records, columns, duplicate rows dropped, and empty rows cleaned.
- **Asset Identification**: Automatic detection of token IDs, asset names, or collection columns to report unique asset counts.
- **Price Diagnostics**: Average and median NFT prices for the mapped price field.
- **Trading Volume Validation**: Direct summation of volume fields or price $\times$ sales estimation where mathematically supported; explicitly indicates "Unsupported" when the dataset lacks transaction counts or volume metrics.
- **Data Quality Alerts**: Automated warning banners for high missingness rates (>10%) and negative price anomalies.
- **Field Inspection Table**: Summary of detected data types, missing percentages, and sample records.

### 2. ⏱️ Time-Series Analysis
- **Metric Selection**: Dynamic dropdown allowing time-series analysis of prices, sales counts, or other numeric fields.
- **Multi-Interval Aggregation**: Aggregate transactions by Daily, Weekly, or Monthly periods.
- **Interactive Date Filtering**: Dual-handle date range slider to isolate specific chronological market windows.
- **Rolling Averages**: Configurable smoothing window (`None`, `7`, `14`, or `30` periods) to observe macro trends.
- **Market Activity Tracking**: Paired bar charts displaying transaction frequency and dataset activity over time.

### 3. 💬 Social-Media Engagement
- **Automatic Column Detection**: Scans dataset headers for engagement metrics (likes, comments, retweets, replies, views, impressions, followers).
- **Temporal Trends**: Multi-metric timeline charts tracking social activity over aggregated intervals.
- **Cross-Metric Correlation**: Scatter plots pairing selected engagement metrics against price or sales metrics, featuring an ordinary least squares (OLS) linear trendline.
- **Correlation Matrix**: Pearson correlation coefficient ($r$) table with sample sizes.
- **Scientific Caveat**: Prominent methodological callout explaining that *correlation does not establish causation*, emphasizing potential confounding factors such as broader market sentiment or reverse causality.

### 4. 🤖 Price Prediction
- **Target Selection**: Flexible dropdown to select the target price column to predict.
- **Leakage-Safe Feature Engineering**:
  - Sequential chronological index.
  - Calendar components: Year, Month, Day of Week, Day of Year, and cyclical harmonic features ($\sin$ and $\cos$ of Month).
  - Target lags: Lag 1 ($t-1$), Lag 2 ($t-2$), and 3-period rolling average.
  - Prior external observations: Lagged versions of sales and social metrics from previous observations only. **Zero same-row future lookahead.**
- **Chronological Evaluation**: Strict 80/20 train/test split preserving temporal order (no shuffled splitting).
- **Dual-Model Comparison**: Fits **Linear Regression** (median imputation + standard scaling) and **Random Forest Regressor** (median imputation + 250 estimators).
- **Feature Importance**: Horizontal bar chart visualizing Random Forest feature weights.
- **Estimate Disclaimer**: Clear research notice explaining that predictions are statistical estimates and do not constitute financial advice.

### 5. 📈 Model Evaluation
- **Visual Metric Benchmarking**: Grouped bar chart comparing Mean Absolute Error (MAE) and Root Mean Squared Error (RMSE) side-by-side.
- **Metric Definitions**: Educational documentation explaining MAE, RMSE, and $R^2$ (including why $R^2$ can be negative for models that underperform a naive mean baseline).
- **Residual Analysis**: Chronological timeline of residuals ($Actual - Predicted$) with a zero baseline to diagnose systematic bias.
- **Prediction Record Table**: Row-by-row table of held-out test dates, actual values, and model predictions.

---

## Data Handling & Security

- **Local & Confidential Data**: The local `private_data/` directory and all `.csv` files are explicitly excluded via `.gitignore` to prevent confidential datasets, environment files, or credentials from ever being committed to GitHub.
- **In-Memory Session Processing**: Uploaded CSV files are processed in-memory using `io.BytesIO` within Streamlit session state and are discarded when the session ends.
- **No Data Fabrication**: Real calculations remain strictly bound to uploaded files. Synthetic values are used only when the explicitly labeled "Synthetic educational demo" mode is activated.
- **Multi-Encoding & Format Support**: Automatic fallback across `utf-8`, `utf-8-sig`, `latin-1`, and `cp1252`, as well as comma, semicolon, and tab delimiters.

---

## CSV Dataset Guidance

The application inspects headers and suggests appropriate mappings. For optimal analysis, supply a CSV with the following fields:

| Analysis Module | Recommended Fields |
| :--- | :--- |
| **Market Overview & Price Trends** | A parseable date/time column (`date`, `timestamp`, `created_at`, `tx_time`) and numeric price column (`price`, `floor_price`, `amount`, `usd_price`). |
| **Asset Tracking** | Identifier column such as `token_id`, `nft_id`, `item_id`, `name`, or `collection`. |
| **Market Activity / Volume** | Transaction or sales count (`sales`, `sale_count`, `transactions`, `trades`) or volume field (`volume`, `volume_usd`). |
| **Social Engagement** | Numeric fields such as `likes`, `comments`, `retweets`, `shares`, `views`, `followers`, or `impressions`. |
| **Predictive Modeling** | At least 12 chronologically ordered records containing valid timestamps and numeric target prices. |

---

## Installation & Local Setup

### Prerequisites
- Python 3.10 or newer
- `pip` package manager

### 1. Clone the Repository
```bash
git clone https://github.com/likithaliki951-spec/nft-trend-analyzer.git
cd nft-trend-analyzer
```

### 2. Create a Virtual Environment
**On Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**On macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Run the Dashboard
```bash
streamlit run app.py
```
Open your web browser and navigate to the local URL (default: `http://localhost:8501`).

---

## Automated Test Suite

The test suite validates data cleaning, numeric parsing, epoch date handling, feature engineering chronology, regression pipelines, and Streamlit page rendering:

```bash
python -m pytest -v
```

All 14 tests run against unit functions and the Streamlit `AppTest` simulation harness.

---

## Streamlit Community Cloud Deployment

To deploy this dashboard on [Streamlit Community Cloud](https://streamlit.io/cloud):

1. **Push to GitHub**:
   Ensure all changes are committed and pushed to your GitHub repository:
   ```bash
   git add .gitignore app.py nft_analysis.py requirements.txt tests/ .streamlit/ README.md
   git commit -m "Deploy modern NFT trend analyzer dashboard"
   git push origin main
   ```
   *(Verify that `private_data/` and confidential CSVs are not staged).*

2. **Connect Streamlit Cloud**:
   - Log in to [share.streamlit.io](https://share.streamlit.io).
   - Click **New app**.
   - Select your repository (`likithaliki951-spec/nft-trend-analyzer`), branch (`main`), and set the main file path to:
     ```text
     app.py
     ```
   - Click **Deploy**.

3. **Verify Deployment**:
   Streamlit Cloud will read `requirements.txt` and `.streamlit/config.toml` automatically, configure the dark theme, and launch the dashboard.

---

## Project Structure

```
NFT-Trend-Analyzer/
├── app.py                      # Streamlit application UI, navigation, and page layouts
├── nft_analysis.py             # Data cleaning, KPI calculation, feature engineering, and ML evaluation
├── requirements.txt            # Python dependencies (Streamlit, Pandas, NumPy, Scikit-learn, Plotly, Pytest)
├── pyproject.toml              # Project configuration and dependency specifications
├── .streamlit/
│   └── config.toml             # Streamlit dark theme configuration (charcoal background, violet accent)
├── tests/
│   ├── test_nft_analysis.py    # Unit tests for data cleaning, parsing, metrics, and models (13 tests)
│   └── test_dashboard_pages.py # Streamlit AppTest headless render verification (1 test)
├── .gitignore                  # Git ignore rules protecting private_data/ and CSVs
└── README.md                   # Project documentation and deployment guide
```

---

## License

This project is open-source and available under the [MIT License](LICENSE).
