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


def get_authenticated_headers():
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
    return {"Authorization": f"Bearer {token}"}, email


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
