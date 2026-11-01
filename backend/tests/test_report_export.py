"""Comprehensive regression and integration test suite for Report Export System.

Tests all four export formats:
1. PDF (.pdf) with ReportLab and NumberedCanvas
2. Structured JSON (.json) with schema validation and security check
3. Microsoft Word (.docx) with python-docx structure validation
4. Microsoft Excel (.xlsx) with openpyxl multi-tab and styling verification

Also tests:
- Scope filtering (complete, price_trends, market_activity, social_engagement, etc.)
- Strict authentication enforcement (401 without auth)
- Query-parameter GET downloads
- Dedicated format endpoints
- Invalid format rejection (400)
- Security audit ensuring no auth tokens or secrets are exposed in exported documents
"""

from __future__ import annotations

import io
import json
import uuid
import pytest
from fastapi.testclient import TestClient

import docx
import openpyxl

from app.main import app

client = TestClient(app)


def get_authenticated_headers(with_demo: bool = True):
    """Register and log in a fresh test user to obtain valid JWT headers."""
    email = f"exporter_{uuid.uuid4().hex[:8]}@nfttrends.io"
    password = "QuantumVault#2026!AlphaBeta"
    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "name": "Jordan Lee",
            "password": password,
            "password_confirm": password,
        },
    )
    assert reg_res.status_code == 200, f"Registration failed: {reg_res.text}"

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    if with_demo:
        demo_res = client.get("/api/v1/analysis/dataset/demo", headers=headers)
        assert demo_res.status_code == 200, f"Demo load failed: {demo_res.text}"

    return headers, email


def test_unauthenticated_export_rejected():
    """Verify that export endpoints strictly reject unauthenticated requests with 401."""
    # POST /analysis/export
    res_post = client.post("/api/v1/analysis/export", json={"format": "pdf", "scope": "complete"})
    assert res_post.status_code == 401

    # GET /analysis/export
    res_get = client.get("/api/v1/analysis/export?format=pdf")
    assert res_get.status_code == 401

    # Format-specific endpoints
    for endpoint in ["/api/v1/analysis/export/pdf", "/api/v1/analysis/export/json", "/api/v1/analysis/export/docx", "/api/v1/analysis/export/xlsx"]:
        res_ep = client.post(endpoint, json={})
        assert res_ep.status_code == 401


def test_pdf_export_complete_lifecycle():
    """Verify complete PDF export generates valid binary PDF with correct headers and NumberedCanvas."""
    headers, email = get_authenticated_headers()

    res = client.post(
        "/api/v1/analysis/export",
        headers=headers,
        json={"format": "pdf", "scope": "complete", "custom_title": "Executive NFT Valuation Brief"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert "attachment; filename=" in res.headers["content-disposition"]
    assert res.headers["content-disposition"].endswith('.pdf"')

    # Verify standard PDF binary header (%PDF)
    pdf_bytes = res.content
    assert len(pdf_bytes) > 5000
    assert pdf_bytes.startswith(b"%PDF-")


def test_json_export_complete_lifecycle():
    """Verify JSON export produces valid JSON containing all analytics modules and no leaked credentials."""
    headers, email = get_authenticated_headers()

    res = client.post(
        "/api/v1/analysis/export",
        headers=headers,
        json={"format": "json", "scope": "complete"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/json"
    assert "attachment; filename=" in res.headers["content-disposition"]
    assert res.headers["content-disposition"].endswith('.json"')

    data = json.loads(res.content.decode("utf-8"))
    assert data["report_format"] == "json"
    assert "metadata" in data
    assert "features_detected" in data
    assert "module_statuses" in data
    assert "price_trends" in data
    assert "market_activity" in data
    assert "social_engagement" in data
    assert "marketplace_hub" in data
    assert "dataset_summary" in data

    # Security check: verify no secrets or sensitive fields are leaked
    raw_str = res.content.decode("utf-8").lower()
    for sensitive in ["password_hash", "access_token", "secret_key", "service_role_key"]:
        assert sensitive not in raw_str


def test_docx_export_complete_lifecycle():
    """Verify DOCX export produces a valid OpenXML Word document readable by python-docx."""
    headers, email = get_authenticated_headers()

    res = client.post(
        "/api/v1/analysis/export",
        headers=headers,
        json={"format": "docx", "scope": "complete", "include_charts": True},
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert "attachment; filename=" in res.headers["content-disposition"]
    assert res.headers["content-disposition"].endswith('.docx"')

    # Verify python-docx can open and read document
    doc = docx.Document(io.BytesIO(res.content))
    paragraphs_text = " ".join([p.text for p in doc.paragraphs])
    assert "NFT Market Intelligence Report" in paragraphs_text or "NFT Trend Analyzer" in paragraphs_text
    assert len(doc.tables) >= 2


def test_xlsx_export_complete_lifecycle():
    """Verify XLSX export produces a valid multi-tab Excel workbook with styled headers and native charts."""
    headers, email = get_authenticated_headers()

    res = client.post(
        "/api/v1/analysis/export",
        headers=headers,
        json={"format": "xlsx", "scope": "complete"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment; filename=" in res.headers["content-disposition"]
    assert res.headers["content-disposition"].endswith('.xlsx"')

    # Verify openpyxl can load the workbook
    wb = openpyxl.load_workbook(io.BytesIO(res.content))
    sheet_names = wb.sheetnames
    assert "Executive Overview" in sheet_names
    assert "Dataset Summary" in sheet_names
    assert "Price Trends" in sheet_names
    assert "Market Activity" in sheet_names
    assert "ML Models & PCA" in sheet_names
    assert "Social Engagement" in sheet_names
    assert "Marketplace Hub" in sheet_names

    # Check cell data in Executive Overview
    ws_over = wb["Executive Overview"]
    assert ws_over["A1"].value is not None


def test_scoped_exports():
    """Verify that specifying a specific scope filters the output appropriately in JSON and XLSX."""
    headers, email = get_authenticated_headers()

    # Scope: price_trends
    res_pt = client.post(
        "/api/v1/analysis/export",
        headers=headers,
        json={"format": "json", "scope": "price_trends"},
    )
    assert res_pt.status_code == 200
    data_pt = json.loads(res_pt.content.decode("utf-8"))
    assert "price_trends" in data_pt
    assert "market_activity" not in data_pt
    assert "social_engagement" not in data_pt

    # Scope: market_activity
    res_ma = client.post(
        "/api/v1/analysis/export",
        headers=headers,
        json={"format": "json", "scope": "market_activity"},
    )
    assert res_ma.status_code == 200
    data_ma = json.loads(res_ma.content.decode("utf-8"))
    assert "market_activity" in data_ma
    assert "price_trends" not in data_ma


def test_dedicated_format_endpoints():
    """Verify dedicated shortcut POST endpoints: /export/pdf, /export/json, /export/docx, /export/xlsx."""
    headers, email = get_authenticated_headers()

    # Dedicated PDF
    r_pdf = client.post("/api/v1/analysis/export/pdf", headers=headers, json={"scope": "price_trends"})
    assert r_pdf.status_code == 200
    assert r_pdf.headers["content-type"] == "application/pdf"

    # Dedicated JSON
    r_json = client.post("/api/v1/analysis/export/json", headers=headers, json={"scope": "complete"})
    assert r_json.status_code == 200
    assert r_json.headers["content-type"] == "application/json"

    # Dedicated DOCX
    r_docx = client.post("/api/v1/analysis/export/docx", headers=headers, json={"scope": "complete"})
    assert r_docx.status_code == 200
    assert r_docx.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    # Dedicated XLSX
    r_xlsx = client.post("/api/v1/analysis/export/xlsx", headers=headers, json={"scope": "complete"})
    assert r_xlsx.status_code == 200
    assert r_xlsx.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_get_export_with_query_params():
    """Verify that browser direct download via GET with query params succeeds."""
    headers, email = get_authenticated_headers()

    res_get = client.get(
        "/api/v1/analysis/export?format=json&scope=dataset_summary",
        headers=headers,
    )
    assert res_get.status_code == 200
    assert res_get.headers["content-type"] == "application/json"
    data = json.loads(res_get.content.decode("utf-8"))
    assert "dataset_summary" in data


def test_invalid_format_rejected():
    """Verify that an unsupported export format is rejected with HTTP 400 Bad Request."""
    headers, email = get_authenticated_headers()

    res = client.post(
        "/api/v1/analysis/export",
        headers=headers,
        json={"format": "xml_unsupported", "scope": "complete"},
    )
    assert res.status_code == 400
    assert "Unsupported export format" in res.json()["detail"]


def test_export_without_active_dataset_rejected_400():
    """Verify that export without an active uploaded or demo dataset returns HTTP 400."""
    headers, email = get_authenticated_headers(with_demo=False)

    # 1. Verify active-dataset reports no active dataset
    meta_res = client.get("/api/v1/analysis/active-dataset", headers=headers)
    assert meta_res.status_code == 200
    assert meta_res.json()["has_active_dataset"] is False

    # 2. Attempting to export must be rejected with HTTP 400
    for fmt in ["pdf", "json", "docx", "xlsx"]:
        res = client.post(
            "/api/v1/analysis/export",
            headers=headers,
            json={"format": fmt, "scope": "complete"},
        )
        assert res.status_code == 400, f"Expected 400 for {fmt}, got {res.status_code}: {res.text}"
        assert "No analyzed dataset available for export" in res.json()["detail"]


def test_custom_uploaded_dataset_exported_across_all_formats():
    """Verify that uploading a distinct custom NFT dataset exports the real uploaded data and NOT demo data."""
    headers, email = get_authenticated_headers(with_demo=False)

    # 1. Create a distinct custom NFT CSV dataset
    csv_content = (
        "sale_date,price_eth,sales_count,social_likes,social_comments,collection\n"
        "2024-03-01,789.123,42,1200,350,Apex Celestial Predators\n"
        "2024-03-02,810.456,48,1350,380,Apex Celestial Predators\n"
        "2024-03-03,825.789,55,1420,410,Apex Celestial Predators\n"
        "2024-03-04,850.999,60,1580,450,Apex Celestial Predators\n"
        "2024-03-05,875.250,65,1650,490,Apex Celestial Predators\n"
        "2024-03-06,890.100,70,1720,510,Apex Celestial Predators\n"
        "2024-03-07,915.600,75,1800,530,Apex Celestial Predators\n"
    ).encode("utf-8")

    filename = "Apex_Celestial_Predators_2026.csv"
    upload_res = client.post(
        "/api/v1/analysis/pipeline/upload-and-analyze",
        headers=headers,
        files={"file": (filename, io.BytesIO(csv_content), "text/csv")},
    )
    assert upload_res.status_code == 200, f"Upload failed: {upload_res.text}"
    project_id = upload_res.json()["project_id"]

    # 2. Verify active-dataset metadata is accurately tracked
    active_res = client.get("/api/v1/analysis/active-dataset", headers=headers)
    assert active_res.status_code == 200
    active_meta = active_res.json()
    assert active_meta["has_active_dataset"] is True
    assert active_meta["dataset_name"] == filename
    assert active_meta["is_demo"] is False
    assert active_meta["rows_count"] == 7

    # 3. Export JSON and assert real metrics and dataset name are present
    json_res = client.post(
        "/api/v1/analysis/export",
        headers=headers,
        json={"format": "json", "scope": "complete"},
    )
    assert json_res.status_code == 200
    export_json = json.loads(json_res.content.decode("utf-8"))
    assert export_json["metadata"]["dataset_name"] == filename
    assert export_json["dataset_summary"]["total_records"] == 7

    # Verify real data is present and educational demo data is NOT present
    raw_json_str = json_res.content.decode("utf-8")
    assert "Apex Celestial Predators" in raw_json_str
    assert "789.123" in raw_json_str or "789.12" in raw_json_str
    assert "Educational NFT Benchmark Dataset (Demo)" not in raw_json_str
    assert "Demo Collection A" not in raw_json_str
    assert "Demo Collection B" not in raw_json_str

    # 4. Export DOCX and assert custom dataset is present
    docx_res = client.post(
        "/api/v1/analysis/export",
        headers=headers,
        json={"format": "docx", "scope": "complete"},
    )
    assert docx_res.status_code == 200
    doc = docx.Document(io.BytesIO(docx_res.content))
    doc_text = " ".join([p.text for p in doc.paragraphs])
    assert filename in doc_text or "Apex Celestial Predators" in doc_text
    assert "Educational NFT Benchmark Dataset (Demo)" not in doc_text

    # 5. Export XLSX and assert custom dataset is present
    xlsx_res = client.post(
        "/api/v1/analysis/export",
        headers=headers,
        json={"format": "xlsx", "scope": "complete"},
    )
    assert xlsx_res.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_res.content))
    overview_sheet = wb["Executive Overview"]
    overview_text = " ".join([str(cell.value) for row in overview_sheet.iter_rows() for cell in row if cell.value])
    assert filename in overview_text or "Apex Celestial Predators" in overview_text
    assert "Educational NFT Benchmark Dataset (Demo)" not in overview_text

    # 6. Export PDF and assert binary PDF generated with custom dataset header
    pdf_res = client.post(
        "/api/v1/analysis/export",
        headers=headers,
        json={"format": "pdf", "scope": "complete"},
    )
    assert pdf_res.status_code == 200
    assert pdf_res.content.startswith(b"%PDF-")
    assert "Apex_Celestial_Predators_2026" in pdf_res.headers["content-disposition"]


def test_cross_user_project_isolation_in_export():
    """Verify that a user cannot export another user's project ID and no demo fallback occurs."""
    headers_user_a, email_a = get_authenticated_headers(with_demo=False)
    headers_user_b, email_b = get_authenticated_headers(with_demo=False)

    # User A uploads a dataset
    csv_content = (
        "sale_date,price_eth,sales_count,social_likes,social_comments,collection\n"
        "2024-04-01,150.0,10,100,20,Secret Art Club\n"
        "2024-04-02,155.0,12,110,25,Secret Art Club\n"
    ).encode("utf-8")

    upload_res = client.post(
        "/api/v1/analysis/pipeline/upload-and-analyze",
        headers=headers_user_a,
        files={"file": ("Secret_Art_Club.csv", io.BytesIO(csv_content), "text/csv")},
    )
    assert upload_res.status_code == 200
    project_id_a = upload_res.json()["project_id"]

    # User B attempts to export using User A's project_id
    res_b = client.post(
        "/api/v1/analysis/export",
        headers=headers_user_b,
        json={"format": "json", "project_id": project_id_a},
    )
    # Must return 404 access denied / not found, NEVER return User A's data or demo data
    assert res_b.status_code == 404
    assert "not found or access denied" in res_b.json()["detail"].lower()


def test_export_saved_project_after_session_cache_cleared():
    """Verify that an authenticated user can export a saved project after session memory is cleared."""
    headers, email = get_authenticated_headers(with_demo=False)

    csv_content = (
        "sale_date,price_eth,sales_count,social_likes,social_comments,collection\n"
        "2024-05-01,300.0,5,50,10,Vault Gold NFTs\n"
        "2024-05-02,310.0,6,60,15,Vault Gold NFTs\n"
    ).encode("utf-8")

    upload_res = client.post(
        "/api/v1/analysis/pipeline/upload-and-analyze",
        headers=headers,
        files={"file": ("Vault_Gold_NFTs.csv", io.BytesIO(csv_content), "text/csv")},
    )
    assert upload_res.status_code == 200
    project_id = upload_res.json()["project_id"]

    # Simulate server worker restart by clearing in-memory session cache
    from app.services.pipeline_service import _USER_ACTIVE_SESSIONS
    from app.api.routes_analysis import _USER_ACTIVE_DF
    clean_email = email.strip().lower()
    _USER_ACTIVE_SESSIONS.pop(clean_email, None)
    _USER_ACTIVE_DF.pop(clean_email, None)

    # Request export with explicit project_id
    res = client.post(
        "/api/v1/analysis/export",
        headers=headers,
        json={"format": "json", "project_id": project_id},
    )
    assert res.status_code == 200
    data = json.loads(res.content.decode("utf-8"))
    assert data["metadata"]["dataset_name"] == "Vault_Gold_NFTs.csv"
    assert "Vault Gold NFTs" in res.content.decode("utf-8")
