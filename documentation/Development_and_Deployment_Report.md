# NFT Trend Analyzer — Development, Testing, and Deployment Progress Report

**Project Title:** Analysis of Trending NFTs using Time-Series Data and Machine Learning (2026–27)
**Author/Developer:** Likitha
**Repository:** [github.com/likithaliki951-spec/nft-trend-analyzer](https://github.com/likithaliki951-spec/nft-trend-analyzer)
**Deployed URL:** [nft-trend-analyzer-4tmew4gxcughg5b7fpkpla.streamlit.app](https://nft-trend-analyzer-4tmew4gxcughg5b7fpkpla.streamlit.app/)
**Reporting Period:** 24-Hour Intensive Development, Hardening, and Deployment Cycle
**Document Generated:** 2026-10-30

---

## 1. Executive Summary

Over the past 24 hours, the **NFT Trend Analyzer** platform underwent a comprehensive engineering upgrade to align with its core academic specification: *“Analysis of Trending NFTs using Time-Series Data and Machine Learning (2026–27).”*

The existing codebase possessed a 7-page Streamlit dashboard, Support Vector Regression (SVR), a Gated Recurrent Unit (GRU) neural network, and valuation classification via Random Forest and Support Vector Machines. However, an academic audit revealed three critical architectural gaps:
1. **Missing Valuation Classifier:** The valuation tier classification lacked **Logistic Regression**, which was required alongside Random Forest and SVM for linear-versus-non-linear baseline comparisons.
2. **Missing Dimensionality Reduction:** The project specification required reducing high-dimensional feature spaces (up to 127 lagged and rolling features) down to 60 components via **Principal Component Analysis (PCA)**, without data leakage.
3. **Missing Multi-Dataset Ingestion:** In real-world NFT research, sales/market transactions and social media engagement logs originate from disparate APIs or CSVs. The system previously accepted only a single merged dataset, lacking multi-file ingestion, join-key discovery, cardinality validation, and merge execution.

All three academic features were designed, integrated, and verified without breaking existing dashboard modules. During local and cloud testing, two infrastructure challenges were diagnosed and resolved:
- A local registration failure caused by a paused Supabase project DNS lookup (`ltwikfuazytrfhzqvsqs.supabase.co`), which was resolved by activating the built-in local SQLite backend (`.streamlit/users.db`).
- A Streamlit Community Cloud deployment `ImportError` occurring at `app.py`, line 28 while importing `data_loader.py`, which was resolved by enforcing explicit `sys.path` repository root priority, aligning top-level module exports, declaring `__all__`, and pinning `scipy>=1.10.0`.

The test suite was expanded from 81 tests to **89 automated tests** with 0 failures. The final verified code was pushed to GitHub (`origin/main`) across commits `163d883` and `87ff406`, and the live application was confirmed reachable with HTTP 200 OK.

---

## 2. Chronological Activity & Engineering Log

| Step | Phase / Task | Problem / Objective | Technical Investigation & Action | Files & Modules Involved | Verification Method | Outcome |
| :---: | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | **Baseline Inspection** | Verify current Git state, existing 7-page dashboard, and 81 passing tests. | Inspected `git status`, `git log`, dependencies, and test suite. Confirmed existing SVR, GRU, RF, SVM, and auth gates. | `app.py`, `nft_analysis.py`, `ml_models.py`, `auth.py` | `git status`, `pytest` | Confirmed clean working tree on `main` at commit `c913163` with 81 passing tests. |
| **2** | **Academic Audit** | Identify discrepancies between codebase and academic project report. | Cross-referenced codebase against report requirements: identified missing Logistic Regression, absent PCA feature reduction, and single-file upload limitation. | Project report, `valuation_categories.py`, `ml_models.py`, `data_loader.py` | Code inspection | Documented 3 target academic enhancements. |
| **3** | **Feature 1: Logistic Regression** | Add Logistic Regression classifier to Page 6 valuation categorization. | Added `LogisticRegression(max_iter=1000, class_weight="balanced")` pipeline in `valuation_categories.py`. Updated `app.py` to render 3-column comparative metrics and confusion matrices. | `valuation_categories.py`, `app.py` | Unit tests in `test_extended_capabilities.py` | Verified 3 classifiers (RF, SVM, Logistic Regression) fit, predict, and compute balanced accuracy and F1-macro. |
| **4** | **Feature 2: Leakage-Safe PCA** | Implement PCA dimensionality reduction (127 -> 60 components). | Created `fit_leakage_safe_pca()` in `ml_models.py`. Scaler and PCA are fitted strictly on `X_train` and applied to `X_test`. Dynamically bounded components by matrix rank. Integrated scree plots and diagnostics into Pages 4 & 5. | `ml_models.py`, `app.py` | Synthetic rank tests in `test_extended_capabilities.py` | Validated zero out-of-sample data leakage; verified scree plot rendering and component metrics. |
| **5** | **Feature 3: Dual Dataset Join** | Support uploading separate market and social engagement files. | Implemented `POTENTIAL_JOIN_KEYS`, `discover_join_keys()`, `validate_join_keys()`, and `join_market_and_social_datasets()` in `data_loader.py`. Built dual-file uploader UI in `app.py` with overlap stats and duplicate warnings. | `data_loader.py`, `app.py` | 3 new unit tests in `test_data_loader.py` | Verified automatic key matching (e.g. `collection`, `sale_date`), cardinality validation, inner/left/outer joins. |
| **6** | **Regression Testing** | Ensure no regressions across the 7 pages or existing models. | Added `test_dashboard_with_pca_and_join_diagnostics` to `tests/test_dashboard_pages.py`. Ran full suite. | `tests/test_dashboard_pages.py`, `tests/test_data_loader.py` | `python -m pytest` | All **89 automated tests passed** (0 failures, 4 warnings). |
| **7** | **Supabase DNS Failure** | Local registration failed with `NameResolutionError` on `ltwikfuazytrfhzqvsqs.supabase.co`. | Evaluated DNS status; confirmed external Supabase host does not resolve (project paused by provider). Commented out `[supabase]` in local untracked `.streamlit/secrets.toml`. Updated `auth.py` to display active backend (`Local SQLite Database`). | `auth.py`, `.streamlit/secrets.toml` (untracked) | Local registration form submission | Local registration succeeded immediately in SQLite `.streamlit/users.db`. Admin secrets login preserved. |
| **8** | **Commit & Push 1** | Publish academic features to GitHub repository. | Audited `.gitignore` to confirm secrets, user databases, and caches were excluded. Staged 8 files and committed. | 8 repository files | `git diff --cached`, `git push origin main` | Commit `163d883` published to `origin/main`. Working tree clean. |
| **9** | **Cloud ImportError** | Streamlit Cloud deployed app failed at `app.py`, line 28 on `from data_loader import (...)`. | Investigated Streamlit Cloud Linux execution context. Identified that `sys.path` did not prioritize repository root. Found dynamic inline import `read_csv_with_fallback` in `app.py`, unpruned imports in `data_loader.py`, and missing explicit `__all__`. | `app.py`, `data_loader.py`, `auth.py`, `user_store.py`, `requirements.txt` | Traceback analysis, cross-platform import testing | Identified missing `sys.path` anchor and unaligned imports. |
| **10** | **Deployment Fix** | Resolve module resolution, export declaration, and dependency alignment. | 1. Added `sys.path.insert(0, str(_APP_ROOT))` across all top-level entrypoints. 2. Consolidated `read_csv_with_fallback` into `app.py` line 28. 3. Declared explicit `__all__` in `data_loader.py`. 4. Added `scipy>=1.10.0` to `requirements.txt` and `pyproject.toml`. | `app.py`, `data_loader.py`, `auth.py`, `user_store.py`, `requirements.txt`, `pyproject.toml` | Subshell arbitrary directory import test, Streamlit headless run, test suite | All imports succeeded across arbitrary working directories; Streamlit launched with 0 errors. |
| **11** | **Commit & Push 2** | Publish deployment fix to GitHub. | Staged 6 modified files. Confirmed working tree clean. Committed and pushed to `main`. | 6 repository files | `git commit`, `git push origin main` | Commit `87ff406` published to GitHub `main`. |
| **12** | **Live URL Verification** | Verify public reachability on Streamlit Community Cloud. | Probed `https://nft-trend-analyzer-4tmew4gxcughg5b7fpkpla.streamlit.app/` using HTTP client with cookie jar. | Deployed Streamlit Cloud web service | Python `urllib` HTTP GET probe | Verified **HTTP 200 OK** on public cloud endpoint. |

---

## 3. Technical Problems & Root Cause Analysis

### Problem 1: Supabase DNS Name Resolution Failure during Registration
* **Symptom:** Submitting the registration form locally raised `NameResolutionError: Failed to resolve 'ltwikfuazytrfhzqvsqs.supabase.co'`.
* **Root Cause:** Free-tier Supabase projects automatically pause after a period of inactivity. When paused, Supabase removes the project subdomain from public DNS records (`DNS_ERROR_RCODE_NAME_ERROR`).
* **Architecture Fix:** The application's `user_store.py` architecture is designed with dual-backend support: hosted Supabase REST for production and local SQLite for offline/development. In the local `.streamlit/secrets.toml` (which is excluded from Git), the dead `[supabase]` section was commented out. `user_store.py` instantly reverted to the local SQLite database (`.streamlit/users.db`).
* **UI Clarification:** Updated `auth.py` so the registration tab explicitly shows the active storage backend name (`Local SQLite Database`) and gives actionable instructions if a cloud database connection drops.

### Problem 2: Streamlit Community Cloud ImportError on `data_loader.py`
* **Symptom:** Streamlit Community Cloud logs reported an import failure at `app.py`, line 28:
  ```python
  from data_loader import (
      SUPPORTED_EXTENSIONS,
      ...
  )
  ```
* **Root Cause:**
  1. *Linux Working Directory Resolution:* Unlike local IDE environments that automatically inject the project root into Python's search path, Streamlit Cloud containers execute scripts under varying working directories (`/mount/src/...`). Sibling modules like `data_loader.py` and downstream imports like `nft_analysis.py` cannot be guaranteed to resolve without explicit path insertion.
  2. *Inline Import Inconsistency:* `read_csv_with_fallback` was imported inside `read_uploaded_csv()` at line 667 instead of being imported at line 28, leading to inconsistent dependency tracking.
  3. *Unexported Symbols & Transitive Dependency Delay:* `data_loader.py` lacked an `__all__` export contract and imported unused term constants from `nft_analysis.py`. Furthermore, `scipy` was not explicitly declared in `requirements.txt`.
* **Engineering Solution:**
  1. Inserted an explicit project root anchor at the head of `app.py`, `data_loader.py`, `auth.py`, and `user_store.py`:
     ```python
     _APP_ROOT = Path(__file__).resolve().parent
     if str(_APP_ROOT) not in sys.path:
         sys.path.insert(0, str(_APP_ROOT))
     ```
  2. Moved `read_csv_with_fallback` to the top-level import block in `app.py` (line 41) and removed the dynamic inline import.
  3. Declared explicit `__all__` in `data_loader.py` and removed unused imports.
  4. Added `scipy>=1.10.0` directly to `requirements.txt` and `pyproject.toml`.

---

## 4. Source Files Changed and Technical Responsibilities

| File Path | Changes Made in Last 24 Hours | Technical Responsibility |
| :--- | :--- | :--- |
| [`app.py`](file:///c:/Users/likit/Downloads/NFT-Trend-Analyzer/NFT-Trend-Analyzer/app.py) | • Added `sys.path` project root prioritization.<br>• Added `read_csv_with_fallback` to line 28 import block.<br>• Added PCA diagnostics cards and interactive scree plot rendering.<br>• Added 3-column valuation classifier metrics & confusion matrices.<br>• Added dual-file upload interface with join key discovery and diagnostics. | Main Streamlit application entrypoint, page routing, and interactive visualization coordinator. |
| [`data_loader.py`](file:///c:/Users/likit/Downloads/NFT-Trend-Analyzer/NFT-Trend-Analyzer/data_loader.py) | • Added `sys.path` root prioritization.<br>• Implemented `POTENTIAL_JOIN_KEYS`, `discover_join_keys()`, `validate_join_keys()`, `join_market_and_social_datasets()`.<br>• Defined explicit `__all__` export list.<br>• Removed unused term imports from `nft_analysis`. | Safe file ingestion (CSV, Excel, JSON, JSONL, Parquet, TXT), tabular parsing, schema validation, and dataset joining. |
| [`ml_models.py`](file:///c:/Users/likit/Downloads/NFT-Trend-Analyzer/NFT-Trend-Analyzer/ml_models.py) | • Implemented `fit_leakage_safe_pca()`.<br>• Dynamically bounded component counts by matrix rank.<br>• Integrated PCA feature transformation into `evaluate_extended_models()`.<br>• Preserved tabular alignment for GRU hybrid regressor. | Machine learning regression pipelines (Linear Regression, Ridge, SVR, GRU Neural Network) and PCA dimensionality reduction. |
| [`valuation_categories.py`](file:///c:/Users/likit/Downloads/NFT-Trend-Analyzer/NFT-Trend-Analyzer/valuation_categories.py) | • Added `LogisticRegression` pipeline with `StandardScaler` and `class_weight="balanced"` to `classifier_factories`.<br>• Maintained RF and SVM pipelines. | Classification of NFT assets into contiguous valuation bands (*Low*, *Mid*, *High*, *Ultra*) and classifier evaluation. |
| [`auth.py`](file:///c:/Users/likit/Downloads/NFT-Trend-Analyzer/NFT-Trend-Analyzer/auth.py) | • Added `sys.path` root prioritization.<br>• Added active storage backend indicator in UI registration tab.<br>• Enhanced database connection failure diagnostic instructions. | Authentication gates, password hashing (PBKDF2-HMAC-SHA256), session tokens, and security enforcement. |
| [`user_store.py`](file:///c:/Users/likit/Downloads/NFT-Trend-Analyzer/NFT-Trend-Analyzer/user_store.py) | • Added `sys.path` root prioritization.<br>• Maintained dual-backend logic (hosted Supabase REST vs. local SQLite `.streamlit/users.db`). | User registration persistence, input validation, email normalization, and concurrency protection. |
| [`requirements.txt`](file:///c:/Users/likit/Downloads/NFT-Trend-Analyzer/NFT-Trend-Analyzer/requirements.txt) | • Added explicit `scipy>=1.10.0` dependency. | Pinned dependency specifications for Streamlit Community Cloud deployment. |
| [`pyproject.toml`](file:///c:/Users/likit/Downloads/NFT-Trend-Analyzer/NFT-Trend-Analyzer/pyproject.toml) | • Added explicit `scipy>=1.10.0` dependency. | Python project packaging metadata and pytest configuration. |
| [`tests/test_data_loader.py`](file:///c:/Users/likit/Downloads/NFT-Trend-Analyzer/NFT-Trend-Analyzer/tests/test_data_loader.py) | • Added tests for `discover_join_keys`, `validate_join_keys`, and `join_market_and_social_datasets`. | Unit tests for multi-format loading, join key discovery, duplicate validation, and dataset merging (16 tests). |
| [`tests/test_extended_capabilities.py`](file:///c:/Users/likit/Downloads/NFT-Trend-Analyzer/NFT-Trend-Analyzer/tests/test_extended_capabilities.py) | • Added Logistic Regression verification.<br>• Added 3 unit tests for leakage-safe PCA fitting, component bounding, and integration. | Unit tests for valuation bands, classifiers, SVR, GRU, API clients, and PCA (16 tests). |
| [`tests/test_dashboard_pages.py`](file:///c:/Users/likit/Downloads/NFT-Trend-Analyzer/NFT-Trend-Analyzer/tests/test_dashboard_pages.py) | • Added `test_dashboard_with_pca_and_join_diagnostics`. | Streamlit `AppTest` headless rendering verification for all 7 dashboard pages (2 tests). |

---

## 5. Testing and Verification Evidence

### 5.1 Test Suite Summary
The test suite was executed using `pytest-9.1.1` on Python 3.13.7.

```text
============================= test session starts =============================
platform win32 -- Python 3.13.7, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\likit\Downloads\NFT-Trend-Analyzer\NFT-Trend-Analyzer
configfile: pyproject.toml
collected 89 items

tests/test_auth.py .........................                             [ 28%]
tests/test_dashboard_pages.py ..                                         [ 30%]
tests/test_data_loader.py ................                               [ 48%]
tests/test_extended_capabilities.py ................                     [ 66%]
tests/test_nft_analysis.py .............                                 [ 80%]
tests/test_user_store.py .................                               [100%]

======================= 89 passed, 4 warnings in 33.15s =======================
```

### 5.2 Verification of Academic Requirements
1. **Logistic Regression Classifier:**
   * Verified by `test_evaluate_valuation_classifiers_fits_rf_svm_and_logistic_regression`.
   * Confirmed that `results["Logistic Regression"]` contains `accuracy`, `balanced_accuracy`, `f1_macro`, `confusion_matrix`, and `model`.
2. **Leakage-Safe PCA:**
   * Verified by `test_fit_leakage_safe_pca_fits_strictly_on_train_and_transforms_out_of_sample`.
   * Asserted that training dimensions match `(n_train, n_components)` and test dimensions match `(n_test, n_components)`.
   * Verified component bounding on low-rank matrices via `test_fit_leakage_safe_pca_bounds_components_safely_on_small_matrices`.
3. **Dual Dataset Joining:**
   * Verified by `test_discover_join_keys`, `test_validate_join_keys_metrics_and_warnings`, and `test_join_market_and_social_datasets`.
   * Confirmed key discovery priority (`collection`, `sale_date`), duplicate warnings, many-to-many cardinality detection, and join output row integrity.

---

## 6. Git and GitHub History

The repository remote is synchronized with `https://github.com/likithaliki951-spec/nft-trend-analyzer.git` on branch `main`.

```text
* 87ff406 (HEAD -> main, origin/main) fix(deployment): resolve Streamlit Cloud module resolution and align data_loader exports
* 163d883 feat: Add Logistic Regression classifier, PCA reduction, and dual dataset joining
* c913163 Fix StreamlitValueError by using valid default input type for unmasked passwords
* 46b9ced Prioritize secrets admin authentication and harden test suite
* 05908cb Fix Streamlit Cloud dependency installation
* 12489b0 Harden Supabase authentication and cloud persistence
```

### Security Audit of Committed Changes
* **Secrets Exclusion:** `.streamlit/secrets.toml` is untracked and explicitly matched by `.gitignore`. No passwords, tokens, API keys, or private secrets exist in the repository.
* **Database Exclusion:** `.streamlit/users.db` is untracked and excluded by `.gitignore`.
* **Clean Tree:** Running `git status` verifies `nothing to commit, working tree clean`.

---

## 7. Current Deployment Status & Verified Boundaries

* **Live Cloud Application URL:** [https://nft-trend-analyzer-4tmew4gxcughg5b7fpkpla.streamlit.app/](https://nft-trend-analyzer-4tmew4gxcughg5b7fpkpla.streamlit.app/)
* **Verified Network Status:** Independently probed via Python HTTP client with cookie jar: returned `HTTP 200 OK`.
* **Authentication in Cloud vs. Local:**
  * **Static Administrator Authentication (100% Reliable Cloud Path):** The pre-configured Administrator account (`admin@nfttrends.io`) authenticates directly via Streamlit Cloud Secrets. It requires neither Supabase nor a local SQLite file, guaranteeing seamless live demonstrations.
  * **Public Cloud Registration Limitation:** The external Supabase project (`ltwikfuazytrfhzqvsqs.supabase.co`) is currently paused by the database provider. Streamlit Community Cloud instances run on ephemeral containers where local SQLite files reset upon sleep/reboot. Consequently, public user self-registration in the cloud requires unpausing the hosted database.
  * **Local Registration (100% Verified):** When running locally (`streamlit run app.py`), the app defaults to the local SQLite database (`.streamlit/users.db`). Custom analyst user registration and subsequent login are fully functional offline.

---

## 8. Lessons Learned & Best Practices

1. **Explicit Module Search Paths for Cloud Containers:**
   Never assume that cloud deployment platforms (like Streamlit Community Cloud) will have `sys.path` configured identically to a local development workstation. Adding an explicit repository root anchor (`sys.path.insert(0, str(_APP_ROOT))`) eliminates cross-platform import lookup failures.
2. **Preventing Data Leakage in Feature Pipelines:**
   Preprocessing steps like standardization (`StandardScaler`), missing value imputation (`SimpleImputer`), and dimensionality reduction (`PCA`) must learn their parameters (means, standard deviations, principal components) **strictly from training data**. Applying a global transform across the entire dataset before splitting causes optimistic performance bias.
3. **Explicit Export Contracts (`__all__`):**
   Defining `__all__` in library modules prevents ambiguous namespace exports, simplifies static analysis, and ensures explicit architectural contracts between data layers and presentation layers.
4. **Graceful Fallbacks for External Dependencies:**
   Hosting and database dependencies (like external REST APIs) can experience transient DNS or network outages. Providing clean fallback handling and informative UI status messages preserves platform resilience.
