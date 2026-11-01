# NFT Trend Analyzer — 10-Minute Rapid Viva Voce Revision Sheet
**Essential Formulas, Core Architecture, Code Anchors & Emergency Defense**
*Keep this sheet open or printed 10 minutes before your viva examination.*

---

## 1. Quick Facts & Deployment Anchors (Memorize These)
- **Live URL:** `https://nft-trend-analyzer-4tmew4gxcughg5b7fpkpla.streamlit.app/`
- **GitHub Repository:** `https://github.com/likithaliki951-spec/nft-trend-analyzer.git`
- **Latest Commit:** `87ff406` (*fix(deployment): resolve Streamlit Cloud module resolution and align data_loader exports*)
- **Automated Test Suite:** **89 tests passed**, 0 failed, 4 deprecation warnings (62 Unit/Integration in 14.48s + 27 AppTests in 33.15s).
- **Admin Login:** `admin@nfttrends.io` | `Admin#NFT2026!` (Managed in-memory via Streamlit Cloud Secrets).
- **Core Stack:** Python 3.13 / 3.11, Streamlit 1.28+, Scikit-Learn 1.3+, Pandas 2.0+, SciPy 1.10+, Plotly 5.17+, SQLite / Supabase.
- **Pages (7 Total):** 1. Market Overview, 2. Trend Analysis, 3. Price & Social Correlation, 4. Valuation & Predictions, 5. PCA & Dimensionality, 6. Valuation Categories, 7. Model Comparison.

---

## 2. Core Mathematical Formulas & Theory

### A. Regression Evaluation Metrics (Page 4 & Page 7)
$$\text{MAE} = \frac{1}{n} \sum_{i=1}^n |y_i - \hat{y}_i| \quad \text{(Average absolute pricing error in ETH/USD)}$$
$$\text{RMSE} = \sqrt{\frac{1}{n} \sum_{i=1}^n (y_i - \hat{y}_i)^2} \quad \text{(Penalizes large outlier estimation errors)}$$
$$R^2 = 1 - \frac{\sum (y_i - \hat{y}_i)^2}{\sum (y_i - \bar{y})^2} \quad \text{(Proportion of variance explained by model vs naive mean)}$$

### B. Pearson Correlation Coefficient (Page 3)
$$r = \frac{\sum (x_i - \bar{x})(y_i - \bar{y})}{\sqrt{\sum (x_i - \bar{x})^2 \sum (y_i - \bar{y})^2}} \in [-1.0, +1.0]$$

### C. Principal Component Analysis (PCA) & Scree Plot (Page 5)
- Standardize: $X_{\text{scaled}} = (X - \mu) / \sigma$
- Covariance Matrix: $\Sigma = \frac{1}{n-1} X_{\text{scaled}}^T X_{\text{scaled}} = V \Lambda V^T$
- Projection: $Z = X_{\text{scaled}} V_k$ (where $k \le \min(N-1, P, 60)$)
- Explained Variance Ratio for component $j$: $\lambda_j / \sum_{i=1}^P \lambda_i$

### D. Classification: Logistic Regression & Balanced Class Weight (Page 6)
- Softmax Probability: $P(y=k \mid x) = \frac{e^{w_k^T x}}{\sum_j e^{w_j^T x}}$
- Balanced Weighting: $w_k = \frac{n_{\text{samples}}}{n_{\text{classes}} \times n_{\text{samples}, k}}$
  *(Penalizes rare 'Grail' errors $20\times$ more heavily than majority classes!)*
- Macro $F_1$: $\frac{1}{K} \sum_{k=1}^K F_{1, k}$ *(Unweighted mean of all tier $F_1$ scores; treats rare assets equally!)*

### E. Password Security (Authentication)
$$\text{Key} = \text{PBKDF2-HMAC-SHA256}(\text{Password}, \text{Salt}_{16\text{B}}, \text{iterations}=100000, \text{length}=32\text{B})$$

---

## 3. What Was Built in the Last 24 Hours (Chronological Summary)

```
[Oct 28 22:58] Commit 46b9ced: Prioritized st.secrets admin credentials over external databases.
      │
[Oct 28 23:15] Commit c913163: Fixed StreamlitValueError by changing pwd_type "" to "default".
      │
[Oct 29 ~23:30] Diagnostic: Discovered Supabase DNS failure (paused project); routed local auth to SQLite.
      │
[Oct 30 00:05] Commit 163d883: IMPLEMENTED 3 CORE ACADEMIC REQUIREMENTS:
      ├── 1. Logistic Regression Classifier with StandardScaler & class_weight='balanced'.
      ├── 2. Leakage-Safe PCA (fit strictly on X_train, bounded dynamically to <= 60).
      └── 3. Dual Dataset Upload & Join (schema discovery, key validation, Cartesian guards).
      │
[Oct 30 00:45] Commit 87ff406: FIXED STREAMLIT COMMUNITY CLOUD DEPLOYMENT:
      ├── Added deterministic sys.path.insert(0, str(_APP_ROOT)) across modules.
      ├── Aligned explicit __all__ exports in data_loader.py; moved read_csv_with_fallback to top.
      └── Pinned scipy>=1.10.0 in requirements.txt & pyproject.toml -> HTTP 200 OK verified!
```

---

## 4. Key File Anchors & Function Directory

| Module File | Key Functions / Classes | Core Purpose |
| :--- | :--- | :--- |
| `app.py` | `_APP_ROOT`, `init_session_state()`, `main()` | UI entry point, path anchoring, session state, navigation routing across 7 pages. |
| `data_loader.py` | `discover_join_keys()`, `validate_join_keys()`, `join_market_and_social_datasets()`, `clean_nft_data()` | Schema introspection, duplicate detection, join validation, clean merging, and CSV fallback parsing. |
| `ml_models.py` | `fit_leakage_safe_pca()`, `train_all_models()` | Regression suite (OLS, Ridge, RF, GBDT), PCA training strictly on `X_train`, metric calculation. |
| `valuation_categories.py` | `create_valuation_categories()`, `train_valuation_classifiers()` | 4-tier quantile binning, classifier factories (`Logistic Regression`, `RF`, `SVM`), confusion matrices. |
| `dashboard_pages.py` | `render_market_overview()`, `render_pca_page()`, `render_valuation_categories_page()` | 7 modular presentation views with interactive Plotly WebGL visualizations. |
| `auth.py` | `hash_password()`, `verify_password()`, `authenticate_user()`, `require_authentication()` | PBKDF2-HMAC-SHA256 hashing, secrets-first admin authentication, session RBAC. |
| `user_store.py` | `save_user()`, `get_user_by_email()`, `init_db()` | Local SQLite database (`.streamlit/users.db`) fallback handler. |

---

## 5. Instant Answers to 5 Trap Questions

1. **"Did you fit PCA before or after splitting the data?"**
   *Answer:* "Strictly **after** splitting! In `ml_models.py` (`fit_leakage_safe_pca`), `scaler.fit_transform()` and `pca.fit_transform()` are called exclusively on `X_train`. `X_test` is only processed using `.transform()`. Fitting before splitting would leak test variance into training."

2. **"Why did you use Logistic Regression when you already had Random Forest and SVM?"**
   *Answer:* "To provide a well-calibrated, linear probabilistic baseline. Logistic Regression gives direct class probabilities via the Softmax function, is mathematically transparent, trains in milliseconds, and highlights the performance gain achieved by non-linear models like SVM and RF."

3. **"What happens if two uploaded CSV files have duplicate collection names?"**
   *Answer:* "Our `validate_join_keys()` detects duplicate keys on both sides and raises an explicit UI warning alerting the user of a many-to-many Cartesian product risk before merge execution, preventing container memory exhaustion."

4. **"Why does local registration work but cloud registration asks for admin login?"**
   *Answer:* "Because Streamlit Cloud containers use ephemeral disk storage where local SQLite databases are wiped on container reboots. Cloud user registration requires an active external cloud database (such as Supabase once unpaused), whereas Administrator access uses encrypted Streamlit Cloud Secrets that operate 100% reliably in-memory."

5. **"What was the exact bug on Streamlit Cloud earlier today?"**
   *Answer:* "`ModuleNotFoundError: No module named 'data_loader'`. The Debian container launched Python without the repository directory in `sys.path`. We fixed it in commit `87ff406` by programmatically inserting the parent directory into `sys.path` at the top of `app.py` and exporting an explicit `__all__` manifest."

---
*Good luck with your viva examination! You are fully prepared.*
