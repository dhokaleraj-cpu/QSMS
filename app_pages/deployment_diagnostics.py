from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess

import pandas as pd
import streamlit as st

from core.config import get_settings
from core.ui import page_header, stage_section, portal_table

BUILD = "41410-PO-SHIPTO-MASTER-LOGIN-REQUISITIONER"
ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
        return (result.stdout or result.stderr or "").strip()
    except Exception as exc:
        return f"Unavailable: {exc}"


def _has(path: str, token: str) -> bool:
    try:
        return token in (ROOT / path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False


def _sha(path: str) -> str:
    try:
        return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
    except Exception:
        return "-"


def render() -> None:
    settings = get_settings()
    page_header(
        "Deployment Diagnostics",
        "Live runtime proof for version, Git commit and requested QCMS feature files",
        "Admin",
    )
    st.success(f"LIVE RUNTIME · QCMS v{settings.version} · BUILD {BUILD}")

    with stage_section("A", "LIVE RUNTIME SOURCE", key="deployment_diag_runtime"):
        head = _git("rev-parse", "HEAD")
        branch = _git("branch", "--show-current") or "detached / Streamlit runtime"
        rows = [
            {"Check": "QCMS Version", "Value": settings.version},
            {"Check": "Build", "Value": BUILD},
            {"Check": "Runtime root", "Value": str(ROOT)},
            {"Check": "Git HEAD", "Value": head or "Unavailable"},
            {"Check": "Git branch", "Value": branch},
            {"Check": "Git origin", "Value": _git("remote", "get-url", "origin") or "Unavailable"},
            {"Check": "Streamlit main file", "Value": "streamlit_app.py"},
            {"Check": "Runtime host", "Value": os.environ.get("HOSTNAME", "-")},
        ]
        portal_table(pd.DataFrame(rows), hide_index=True, width="stretch", height=320)
        proof_path = ROOT / "STREAMLIT_DEPLOY_TARGET_PROOF_v4.14.10.txt"
        if proof_path.exists():
            st.code(proof_path.read_text(encoding="utf-8", errors="ignore"), language="text")
        else:
            st.warning("Deployment target proof file is not present in this runtime. The v4.14.10 updater creates it before the Git commit/push.")

    checks = [
        ("MetLAB direct edit", "app_pages/metlab_report.py", "Select Existing MetLAB Report to Edit"),
        ("Dimensional direct edit", "app_pages/dimensional_report.py", "Select Existing Dimensional Report to Edit"),
        ("RMTC direct edit", "app_pages/rmtc_pages.py", "Select Existing RMTC to Edit"),
        ("Opening Stock module", "streamlit_app.py", "Opening Stock & Import"),
        ("Opening Stock import/export", "app_pages/supply_chain.py", "OPENING STOCK IMPORT / EXPORT UTILITY"),
        ("Part multiple grades", "app_pages/part_master.py", "part_material_grade_links"),
        ("Supplier lead time", "app_pages/part_master.py", "Lead Time (Days)"),
        ("Customer Order attachments", "app_pages/supply_chain.py", "CUSTOMER ORDER ATTACHMENT"),
        ("PO full price history", "core/supply_chain_service.py", "price_history_snapshot"),
        ("PO section-bar crash fix", "app_pages/supply_chain.py", "section_bar,"),
        ("Forgot password", "core/auth.py", "Forgot Password"),
        ("Next-stage notification routing", "app_pages/email_settings.py", "NEXT-STAGE RESPONSIBILITY ROUTING"),
        ("Module email templates", "app_pages/email_settings.py", "MODULE EMAIL TEMPLATES"),
        ("Automatic overdue email schedules", "app_pages/email_settings.py", "AUTOMATIC OPEN / OVERDUE REPORT EMAILS"),
        ("Email PDF/document attachments", "core/notification_service.py", "attachment_manifest"),
        ("Supplier notification addresses", "core/master_definitions.py", "notification_emails"),
        ("PO Ship-To master selector", "app_pages/supply_chain.py", "SHIP-TO ADDRESS · MASTER CONTROLLED"),
        ("PO login employee requisitioner", "app_pages/supply_chain.py", "Requisitioner (Logged-in Employee)"),
    ]
    with stage_section("B", "REQUESTED FEATURE PROOF", key="deployment_diag_features"):
        data = []
        for label, path, token in checks:
            ok = _has(path, token)
            data.append({"Feature": label, "Runtime file": path, "Status": "ACTIVE" if ok else "MISSING"})
        portal_table(pd.DataFrame(data), hide_index=True, width="stretch", height=430)
        if all(r["Status"] == "ACTIVE" for r in data):
            st.success("All requested feature markers are present in the source currently running this Streamlit process.")
        else:
            st.error("This Streamlit process is not running the complete controlled release source. Use the Git HEAD above to compare with the deployment updater output.")

    with stage_section("C", "CONTROLLED FILE HASHES", key="deployment_diag_hashes"):
        hash_rows = [
            {"File": p, "SHA-256": _sha(p)}
            for p in (
                "streamlit_app.py",
                "app_pages/metlab_report.py",
                "app_pages/dimensional_report.py",
                "app_pages/supply_chain.py",
                "app_pages/part_master.py",
            )
        ]
        portal_table(pd.DataFrame(hash_rows), hide_index=True, width="stretch", height=300)
        st.caption("These hashes prove exactly which application files the live Streamlit runtime loaded from its deployed repository checkout.")
