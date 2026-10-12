# Analysis of Trending NFTs Using Time-Series Data and Machine Learning

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A research-oriented analytics, machine-learning benchmarking, and valuation categorization dashboard for Non-Fungible Token (NFT) transaction datasets. Built with Python and Streamlit, this application features a professional login portal, leak-free chronological time-series analysis, cross-metric social engagement correlations, multi-model price forecasting (Linear Regression, Random Forest, SVR, and pure-NumPy GRU Hybrid), and live marketplace intelligence.

> [!IMPORTANT]
> **Authentication Guard**: All seven dashboard pages and dataset processing pipelines are protected behind a secure login barrier. Unauthenticated requests are halted at execution start (`st.stop()`) and cannot inspect uploaded files, model artifacts, or private market metrics.

---

## Visual Direction & Interface Design

The dashboard uses a research-grade dark theme:
- **Palette**: Deep charcoal/navy background (`#0b0f19`), secondary slate cards (`#131b2e`), with subtle violet (`#8b5cf6`) and electric-blue (`#38bdf8`) accents.
- **KPI Metrics**: Restrained cards displaying key performance indicators, summary statistics, and data-quality notices.
- **Interactive Visualizations**: Full-container-width Plotly charts with automatic layout responsiveness (`autosize=True`), subtle gridlines, dark tooltip overlays, and high-contrast trace colors.
- **Layout**: Wide layout mode (`layout="wide"`) optimized for multi-resolution desktop research terminals and mobile viewports.

---

## 🔒 Complete Registration & Authentication System

The application features a unified, dual-tab access portal (`auth.py` and `user_store.py`) providing:
1. **Sign In**: Email and password authentication with show/hide password toggle.
2. **Create Account**: Public analyst registration with input validation, password strength enforcement, and duplicate prevention.

```
                   Unauthenticated Visitor
                             │
                             ▼
                 ┌───────────────────────┐
                 │    auth.py Gateway    │
                 │ require_authentication│
                 └───────────┬───────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
   [Invalid / Missing Token]         [Valid Session Token]
            │                                 │
   Render Dark Portal Card                    ▼
   ├─ Tab 1: 🔑 Sign In              Allow Dashboard Access
   ├─ Tab 2: 📝 Create Account       (All 7 Analysis Pages)
   └─ Single Sign-On (OIDC)
            │
            ▼
        st.stop()
```

### Registration Security & Policies
- **Input Validation**: Enforces full display names ($\ge 2$ characters), RFC 5322 email syntax, and matching password confirmations.
- **Password Strength**: Minimum 8 characters with at least one letter and at least one digit or special character.
- **No Role Escalation**: Public registrations are strictly assigned `role='analyst'`; administrator privileges cannot be self-selected.
- **Duplicate Prevention**: Email addresses are normalized (trimmed and lowercased) and verified under a re-entrant thread mutex (`threading.RLock`) and database unique constraint.
- **Generic Login Errors**: Authentication failures return a uniform `"Invalid email address or password"` error to prevent account enumeration.

### Persistent Account Storage Backends
Streamlit Community Cloud operates on ephemeral containers where the local filesystem does not persist across restarts. The user storage layer (`user_store.py`) dynamically detects the active environment:

1. **Persistent Cloud Database (Supabase REST API)**:
   - For Streamlit Community Cloud deployments, configure your Supabase project in Streamlit Secrets.
   - Run the included idempotent migration script [`supabase_migration.sql`](supabase_migration.sql) in your **Supabase Dashboard -> SQL Editor**.
   - The script creates `registered_users`, enables **Row Level Security (RLS)**, and creates a case-insensitive index `idx_registered_users_lower_email` on `LOWER(TRIM(email))`.
   - **Service Role Key vs. Anon Key**: In Streamlit Secrets, configure `[supabase.service_role_key]`. Because Streamlit Community Cloud executes as a secure server-side process, the `service_role` key allows user registration and authentication while bypassing RLS safely. Client-side visitors cannot inspect or download user password hashes via the public anon endpoint (HTTP 401/403).
2. **Local Development Storage (SQLite)**:
   - When Supabase credentials are not configured, the app automatically initializes `.streamlit/users.db`.
   - The UI displays an informative status badge (`💾 Local SQLite Database`) explaining how to enable persistent cloud storage.
   - `.streamlit/users.db` is strictly ignored by `.gitignore`.

### Administrator Accounts via Streamlit Secrets
Pre-configured system administrators defined in `.streamlit/secrets.toml` or Streamlit Cloud Secrets (`[credentials.users]`) take priority over database accounts and cannot be overwritten by registration.


---

## Core Dashboard Pages

### 1. 📊 Market Overview
- **Record Diagnostics**: Total valid records, columns, duplicate rows dropped, and empty rows cleaned.
- **Asset Identification**: Automatic detection of token IDs, asset names, or collection columns to report unique asset counts.
- **Price Diagnostics**: Average and median NFT prices for the mapped price field.
- **Trading Volume Validation**: Direct summation of volume fields or price $\times$ sales estimation where mathematically supported; explicitly indicates "Unsupported" when the dataset lacks transaction counts or volume metrics.
- **Data Quality Alerts**: Automated warning banners for high missingness rates (>10%) and negative price anomalies.

### 2. ⏱️ Time-Series Analysis
- **Metric Selection**: Dynamic dropdown allowing time-series analysis of prices, sales counts, or other numeric fields.
- **Multi-Interval Aggregation**: Aggregate transactions by Daily, Weekly, or Monthly periods.
- **Interactive Date Filtering**: Dual-handle date range slider to isolate specific chronological market windows.
- **Rolling Averages**: Configurable smoothing window (`None`, `7`, `14`, or `30` periods) to observe macro trends.
- **Market Activity Tracking**: Paired bar charts displaying transaction frequency and dataset activity over time.

### 3. 💬 Social-Media Engagement
- **Automatic Column Detection**: Scans dataset headers for engagement metrics (likes, comments, retweets, replies, views, impressions, followers).
- **Temporal Trends**: Multi-metric timeline charts tracking social activity over aggregated intervals.
- **Cross-Metric Correlation**: Scatter plots pairing selected engagement metrics against price or sales metrics, featuring linear trendlines.
- **Correlation Matrix**: Pearson correlation coefficient ($r$) table with sample sizes.
- **Scientific Caveat**: Prominent methodological callout explaining that *correlation does not establish causation*.

### 4. 🤖 Price Prediction
- **Target Selection**: Flexible dropdown to select the target price column to predict.
- **Leakage-Safe Feature Engineering**: Chronological index, calendar harmonics, target lags ($t-1$, $t-2$), 3-period rolling average, and prior external observations with **zero same-row future lookahead**.
- **Four Model Architectures**:
  - **Linear Regression**: Median imputation + standard scaling.
  - **Random Forest Regressor**: 250 ensemble estimators with median imputation.
  - **Support Vector Regressor (SVR)**: RBF kernel with robust feature scaling.
  - **GRU Hybrid Time-Series Regressor**: Pure-NumPy recurrent sequence encoder combined with tabular lag features.
- **Feature Importance**: Horizontal bar chart visualizing Random Forest feature weights.

### 5. 📈 Model Evaluation
- **Visual Metric Benchmarking**: Grouped bar chart comparing Mean Absolute Error (MAE) and Root Mean Squared Error (RMSE) side-by-side.
- **Metric Definitions**: Educational documentation explaining MAE, RMSE, and $R^2$.
- **Residual Analysis**: Chronological timeline of residuals ($Actual - Predicted$) with a zero baseline to diagnose systematic bias.
- **Prediction Record Table**: Row-by-row table of held-out test dates, actual values, and model predictions.

### 6. 🏷️ NFT Valuation Categories
- **Contiguous Non-Overlapping Bands**: `$0–$10`, `$10–$100`, `$100–$1,000`, `$1,000–$10,000`, `$10,000–$100,000`, and `$100,000+`.
- **Zero vs. Unsold Separation**: Distinct handling of verified zero prices versus unobserved sales (`Unsold / No Observed Sale`).
- **Classification Modeling**:
  - **Random Forest Classifier**: Balanced class weighting to handle heavy-tailed NFT market tiers.
  - **Support Vector Classifier (Calibrated SVC)**: RBF kernel with Platt-calibrated posterior probabilities.
- **Interactive Valuation Estimator**: Allows users to input hypothetical feature values and receive predicted valuation categories with probability distributions.

### 7. 🌐 Live Market Intelligence & Currency Hub
- **CoinGecko Integration**: Live spot ETH/USD conversion rate with 5-minute TTL memory caching and fallback estimates.
- **Historical Rate Matching**: Timestamp-based ETH/USD conversion helper for historical transaction records.
- **OpenSea Explorer**: Real-time collection stats retrieval (floor price, total supply, creator, descriptions) using OpenSea API v2.
- **Zero-Key Offline Guarantee**: Functions seamlessly when API keys are omitted or rate-limited, rendering offline demonstration cards without crashing.

---

## 📁 Multi-Format Dataset Ingestion & Validation

The application features a reusable ingestion and normalization pipeline (`data_loader.py`):

| Format | Extensions | Capabilities & Structure |
|---|---|---|
| **CSV** | `.csv` | Multi-encoding fallback (`utf-8`, `latin-1`, `cp1252`) and multi-delimiter autodetection (`,`, `;`, `\t`, `\|`). |
| **Excel** | `.xlsx`, `.xls` | OpenPyXL engine, multi-sheet workbook inspection, and interactive worksheet selector. |
| **JSON** | `.json` | Array of records, column-oriented dictionaries, and wrapped API response payloads (`data`, `records`, `results`). |
| **JSON Lines** | `.jsonl` | Line-by-line streaming JSON object parser with line-number error reporting. |
| **Apache Parquet** | `.parquet` | High-efficiency columnar binary dataset reading via PyArrow. |
| **Delimited Text** | `.txt` | Tab, pipe (`\|`), comma, or semicolon-delimited tabular records. |

### Schema Normalization & Diagnostics
- **Column Normalization**: Cleans whitespace, drops empty columns, and resolves duplicate header names deterministically (`col`, `col_2`).
- **Data Quality Diagnostics**: Automatic KPI reporting for unparseable timestamps, missing value percentages, and negative price anomalies.
- **ML Readiness Verification**: Evaluates whether the dataset contains $\ge 12$ chronological observations with valid dates and numeric prices, reporting actionable guidance in the sidebar.
- **Templates & Export**: One-click download of canonical NFT CSV templates and instant export of cleaned, normalized datasets.

---

## Streamlit Secrets Configuration

To configure production user accounts, database credentials, or external API keys:

### 1. Local Development (`.streamlit/secrets.toml`)
Copy the provided template:
```powershell
Copy-Item .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Generate a secure password hash for an administrator account:
```powershell
python -c "import auth; print(auth.hash_password('YOUR_PASSWORD_HERE'))"
```

Configure `.streamlit/secrets.toml`:
```toml
[auth]
cookie_secret = "your-custom-random-32-byte-hex-string"

[credentials.users."admin@yourfirm.com"]
name = "System Administrator"
role = "admin"
password_hash = "pbkdf2_sha256$600000$..."

# Optional: Persistent Cloud Database for registrations (Supabase)
[supabase]
url = "https://your-project-ref.supabase.co"
key = "your-supabase-anon-or-service-role-key"

OPENSEA_API_KEY = "your-opensea-api-key"
COINGECKO_API_KEY = "your-coingecko-demo-key"
```

> [!NOTE]
> `.streamlit/secrets.toml` is strictly ignored by `.gitignore` and will never be committed to GitHub.

---

## Installation & Local Development

### 1. Clone the Repository
```powershell
git clone https://github.com/likithaliki951-spec/nft-trend-analyzer.git
cd nft-trend-analyzer
```

### 2. Create and Activate Virtual Environment
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
```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Run the Dashboard
```powershell
python -m streamlit run app.py
```
Open `http://localhost:8501` in your browser.

---

## Streamlit Community Cloud Public Deployment

Deploy your application publicly to Streamlit Community Cloud:

1. **Verify Git Status**:
   Ensure confidential datasets in `private_data/` and local `secrets.toml` are not tracked:
   ```powershell
   git status
   ```

2. **Commit and Push**:
   ```powershell
   ```bash
   git add .gitignore app.py auth.py user_store.py data_loader.py nft_analysis.py ml_models.py valuation_categories.py api_clients.py requirements.txt pyproject.toml supabase_migration.sql tests/ .streamlit/config.toml .streamlit/secrets.toml.example README.md
   git commit -m "Hardened cloud authentication: Supabase error handling, rotated secrets, multi-backend persistence"
   git push origin main
   ```

3. **Deploy on Streamlit Community Cloud**:
   - Log in to [share.streamlit.io](https://share.streamlit.io).
   - Click **New app**.
   - Select your repository (`likithaliki951-spec/nft-trend-analyzer`), branch (`main`), and set Main file path to:
     ```text
     app.py
     ```
   - Click **Advanced settings** (or **App settings** -> **Secrets** after creation).
   - Paste your production secrets configuration from `.streamlit/secrets.toml.example`.
   - Ensure you configure a newly rotated 32-byte (64-character hex) cookie secret generated via:
     ```bash
     python -c "import secrets; print(secrets.token_hex(32))"
     ```
   - Click **Deploy!**

---

## Automated Test Suite

The test suite validates password hashing, registration validation, duplicate prevention, SQLite and Supabase persistence, cloud error handling (timeouts, network drops, HTTP 401/403 permission errors, HTTP 500 errors, malformed responses), multi-format file ingestion (CSV, Excel, JSON, JSONL, Parquet, TXT), chronological ML pipelines, SVR, GRU sequences, and full headless AppTest page rendering across all 7 pages:

```powershell
python -m pytest -v
```

**Results: 81 passed tests** across unit functions and Streamlit `AppTest` harnesses with zero failures.

---

## Project Structure

```
NFT-Trend-Analyzer/
├── app.py                            # Streamlit entry point, authentication gate, wide layouts, and 7 interactive pages
├── auth.py                           # NIST SP 800-63B PBKDF2 hashing, HMAC session tokens, access control, login/register UI
├── user_store.py                     # Persistent user storage (Supabase REST API + SQLite local fallback), registration validation
├── supabase_migration.sql            # Idempotent PostgreSQL schema, unique index, and RLS policies for Supabase
├── data_loader.py                    # Multi-format ingestion (CSV, Excel, JSON, JSONL, Parquet, TXT), diagnostics, templates
├── nft_analysis.py                   # Data cleaning, KPI calculation, feature engineering, and base ML
├── ml_models.py                      # SVR, pure-NumPy GRU Hybrid sequence model, multi-model evaluation
├── valuation_categories.py           # NFT valuation tiers, Random Forest & Calibrated SVC classifiers
├── api_clients.py                    # CoinGecko ETH/USD rates and OpenSea API v2 integration with TTL cache
├── requirements.txt                  # Python dependencies (Streamlit, Pandas, NumPy, Scikit-learn, Plotly, Requests, OpenPyXL, PyArrow)
├── pyproject.toml                    # Pytest configuration and project metadata
├── .streamlit/
│   ├── config.toml                   # Dark theme configuration (charcoal background, violet accent)
│   └── secrets.toml.example          # Template for production credentials, database keys, and API keys
├── tests/
│   ├── test_auth.py                  # Unit tests for password hashing, session tokens, rotation, AppTest auth gates (24 tests)
│   ├── test_user_store.py            # Unit tests for registration, Supabase cloud error mock tests, SQLite persistence (17 tests)
│   ├── test_data_loader.py           # Unit tests for CSV, Excel, JSON, JSONL, Parquet, TXT, optional fallbacks (13 tests)
│   ├── test_extended_capabilities.py # Unit tests for GRU, SVR, classifiers, and API clients (13 tests)
│   ├── test_nft_analysis.py          # Unit tests for data cleaning, parsing, metrics, and models (13 tests)
│   └── test_dashboard_pages.py       # Streamlit AppTest headless render verification for all 7 pages (1 test)
├── .gitignore                        # Git ignore rules protecting private_data/, CSVs, *.db, and secrets.toml
└── README.md                         # Comprehensive documentation and deployment guide
```

---

## Security & Limitations

- **Session Isolation**: Streamlit session state is isolated per user browser session. No dataset or credential state is shared across concurrent users.
- **In-Memory CSV Processing**: Uploaded CSV files are held strictly in session memory (`io.BytesIO`) and discarded when the tab or session closes.
- **Single-Host Secrets**: The built-in HMAC session token system uses a cryptographic secret configured in `st.secrets["auth"]["cookie_secret"]`. If not configured, an ephemeral per-process key is generated.
- **No Insecure Storage**: Passwords are never stored in plaintext or basic SHA-1/MD5 hashes. Only salted PBKDF2 hashes with 600,000 rounds are evaluated.

---

## License

This project is open-source and available under the [MIT License](LICENSE).
