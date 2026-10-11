# Analysis of Trending NFTs Using Time-Series Data and Machine Learning

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A research-oriented analytics, machine-learning benchmarking, and valuation categorization dashboard for Non-Fungible Token (NFT) transaction datasets. Built with Python and Streamlit, this application features a professional login portal, leak-free chronological time-series analysis, cross-metric social engagement correlations, multi-model price forecasting (Linear Regression, Random Forest, SVR, and pure-NumPy GRU Hybrid), and live marketplace intelligence.

> [!IMPORTANT]
> **Authentication Guard**: All seven dashboard pages and dataset processing pipelines are protected behind a secure login barrier. Unauthenticated requests are halted at execution start (`st.stop()`) and cannot inspect uploaded CSV files, model artifacts, or private market metrics.

---

## Visual Direction & Interface Design

The dashboard uses a research-grade dark theme:
- **Palette**: Deep charcoal/navy background (`#0b0f19`), secondary slate cards (`#131b2e`), with subtle violet (`#8b5cf6`) and electric-blue (`#38bdf8`) accents.
- **KPI Metrics**: Restrained cards displaying key performance indicators, summary statistics, and data-quality notices.
- **Interactive Visualizations**: Unified Plotly dark theme with subtle gridlines, dark tooltip overlays, and high-contrast trace colors.
- **Layout**: Fully responsive layout designed for desktop terminals and smaller screens with sidebar navigation and a persistent session indicator.

---

## 🔒 Authentication & Access Control

The authentication architecture (`auth.py`) is designed for production readiness without requiring paid external subscription plans (such as Supabase):

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
   Render Dark Login Card                     ▼
   (Email / Password or SSO)         Allow Dashboard Access
            │                        (All 7 Analysis Pages)
            ▼
        st.stop()
```

### Security Specifications
1. **Password Hashing (NIST SP 800-63B)**: Passwords are never stored in plaintext. Passwords use PBKDF2-HMAC-SHA256 with 600,000 iterations and a cryptographically unique 16-byte random salt per user.
2. **Cryptographic Session Tokens**: Active sessions are signed using HMAC-SHA256 with a secret key (`cookie_secret`), payload expiration timestamp, and random nonce. Verified using constant-time comparison (`hmac.compare_digest`) to prevent timing attacks.
3. **Session Expiration**: Expired tokens are invalidated automatically, displaying a user-friendly expiration notice and requiring re-authentication.
4. **Single Sign-On (OIDC)**: Compatible with Streamlit's native OpenID Connect (`st.login()` / `st.user`) when configured in secrets.
5. **Zero-Data Leakage**: The entire dashboard (sidebar, navigation, file uploader, charts, and models) is halted with `st.stop()` prior to script execution if the user is unauthenticated.

### Production Credentials via Streamlit Secrets
User accounts are defined in Streamlit secrets (`[credentials.users]`). If secrets are not yet configured, the app displays a clear setup message instructing the administrator to configure credentials, rather than permitting unauthorized or unverified guest access.

To configure your administrator account, see the [Streamlit Secrets Configuration](#streamlit-secrets-configuration) section below.

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

## Streamlit Secrets Configuration

To configure production user accounts, API keys, or custom cookie secrets:

### 1. Local Development (`.streamlit/secrets.toml`)
Copy the provided template:
```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Generate a secure password hash for your analyst account:
```bash
python -c "import auth; print(auth.hash_password('YOUR_PASSWORD_HERE'))"
```

Paste the hash into `.streamlit/secrets.toml`:
```toml
[auth]
cookie_secret = "your-custom-random-32-byte-hex-string"

[credentials.users."analyst@yourfirm.com"]
name = "Lead Analyst"
role = "senior_researcher"
password_hash = "pbkdf2_sha256$600000$..."

OPENSEA_API_KEY = "your-opensea-api-key"
COINGECKO_API_KEY = "your-coingecko-demo-key"
```

> [!NOTE]
> `.streamlit/secrets.toml` is strictly ignored by `.gitignore` and will never be committed to GitHub.

---

## Installation & Local Development

> [!NOTE]
> **Localhost vs. Public Deployment**: `http://localhost:8501` is a local development address accessible only on your machine. To access the dashboard over the public internet, deploy the repository to Streamlit Community Cloud.

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
python -m streamlit run app.py
```
Open `http://localhost:8501` in your browser.

---

## Streamlit Community Cloud Public Deployment

Deploy your application publicly to Streamlit Community Cloud:

1. **Verify Git Status**:
   Ensure confidential datasets in `private_data/` and local `secrets.toml` are not tracked:
   ```bash
   git status
   ```

2. **Commit and Push**:
   ```bash
   git add .gitignore app.py auth.py nft_analysis.py ml_models.py valuation_categories.py api_clients.py requirements.txt pyproject.toml tests/ .streamlit/config.toml .streamlit/secrets.toml.example README.md
   git commit -m "Deploy public login-protected NFT Trend Analyzer"
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
   - Click **Deploy!**

4. **Public Access URL**:
   Streamlit Community Cloud generates a public URL:
   ```text
   https://<your-app-name>.streamlit.app
   ```
   Users visiting this URL will see the branded login portal. After entering their credentials, the full 7-page dashboard is unlocked.

---

## Automated Test Suite

The test suite validates password hashing, HMAC session tokens, unauthenticated access blocking, login flow, session expiration, OIDC SSO, data cleaning, numeric parsing, chronological ML pipelines, SVR, GRU sequences, and full headless AppTest page rendering:

```bash
python -m pytest -v
```

**Results: 40 passed tests** across unit functions and Streamlit `AppTest` harnesses.

---

## Project Structure

```
NFT-Trend-Analyzer/
├── app.py                            # Streamlit entry point, authentication gate, and 7 interactive pages
├── auth.py                           # NIST SP 800-63B PBKDF2 hashing, HMAC session tokens, access control
├── nft_analysis.py                   # Data cleaning, KPI calculation, feature engineering, and base ML
├── ml_models.py                      # SVR, pure-NumPy GRU Hybrid sequence model, multi-model evaluation
├── valuation_categories.py           # NFT valuation tiers, Random Forest & Calibrated SVC classifiers
├── api_clients.py                    # CoinGecko ETH/USD rates and OpenSea API v2 integration with TTL cache
├── requirements.txt                  # Python dependencies (Streamlit, Pandas, NumPy, Scikit-learn, Plotly, Requests)
├── pyproject.toml                    # Pytest configuration and project metadata
├── .streamlit/
│   ├── config.toml                   # Dark theme configuration (charcoal background, violet accent)
│   └── secrets.toml.example          # Template for production credentials and API keys
├── tests/
│   ├── test_auth.py                  # Unit tests for password hashing, session tokens, AppTest auth gates (11 tests)
│   ├── test_extended_capabilities.py # Unit tests for GRU, SVR, classifiers, and API clients (13 tests)
│   ├── test_nft_analysis.py          # Unit tests for data cleaning, parsing, metrics, and models (13 tests)
│   └── test_dashboard_pages.py       # Streamlit AppTest headless render verification for all 7 pages (1 test)
├── .gitignore                        # Git ignore rules protecting private_data/, CSVs, and secrets.toml
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
