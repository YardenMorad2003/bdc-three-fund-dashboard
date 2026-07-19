from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DASHBOARD_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = DASHBOARD_ROOT / "lib" / "bdc-universe.json"
CENTRAL_DB_PATH = (
    WORKSPACE_ROOT
    / "output"
    / "bdc_tracker_centralized"
    / "bdc_tracker_holdings.sqlite"
)
EXPANSION_DB_PATH = (
    WORKSPACE_ROOT
    / "output"
    / "edgartools_bdc_expansion"
    / "edgartools_bdc_expansion_holdings.sqlite"
)

DEFAULT_DEPS = Path(r"C:\tmp\edgartools_deps")
DEPS = Path(os.environ.get("EDGARTOOLS_DEPS", DEFAULT_DEPS))
if DEPS.exists():
    sys.path.insert(0, str(DEPS))

try:
    import edgar
    from edgar.bdc import fetch_bdc_dataset, get_bdc_list
except ImportError as exc:
    raise SystemExit(
        "EdgarTools is not importable. Install edgartools>=5.12 and set "
        "EDGARTOOLS_DEPS when it is outside the active Python environment."
    ) from exc


VERIFIED_FUNDS = {
    1287750: ("ARCC", "Ares Capital Corporation"),
    1379785: ("BBDC", "Barings BDC, Inc."),
    1736035: ("BXSL", "Blackstone Secured Lending Fund"),
    1422183: ("FSK", "FS KKR Capital Corp."),
    1476765: ("GBDC", "Golub Capital BDC, Inc."),
    1396440: ("MAIN", "Main Street Capital Corporation"),
    1655888: ("OBDC", "Blue Owl Capital Corporation"),
    1508655: ("TSLX", "Sixth Street Specialty Lending, Inc."),
}

TRACKER_AUDIT_COHORT = {
    1396440: ("MAIN", "Main Street Capital Corporation"),
    1476765: ("GBDC", "Golub Capital BDC, Inc."),
    1280784: ("HTGC", "Hercules Capital, Inc."),
    17313: ("CSWC", "Capital Southwest Corporation"),
    1370755: ("TCPC", "BlackRock TCP Capital Corp."),
    1379785: ("BBDC", "Barings BDC, Inc."),
    1655050: ("BCSF", "Bain Capital Specialty Finance, Inc."),
    1414932: ("OCSL", "Oaktree Specialty Lending Corporation"),
    1496099: ("NMFC", "New Mountain Finance Corporation"),
    1633336: ("CCAP", "Crescent Capital BDC, Inc."),
    1287032: ("PSEC", "Prospect Capital Corporation"),
}

MANUAL_REGISTRY_EXCEPTIONS = {
    1287750: {
        "name": "ARES CAPITAL CORP",
        "file_number": "814-00663",
        "city": "NEW YORK",
        "state": "NY",
        "is_active": True,
    },
    1508655: {
        "name": "SIXTH STREET SPECIALTY LENDING, INC.",
        "file_number": "814-01054",
        "city": "DALLAS",
        "state": "TX",
        "is_active": True,
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean(value: Any) -> Any:
    if value is None:
        return None
    try:
        if value != value:
            return None
    except TypeError:
        pass
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def verified_rows() -> dict[int, dict[str, Any]]:
    if not CENTRAL_DB_PATH.exists():
        raise FileNotFoundError(CENTRAL_DB_PATH)
    con = sqlite3.connect(CENTRAL_DB_PATH.resolve().as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            select
                fund,
                max(filing_period_end) as latest_period,
                count(*) as all_period_rows,
                sum(case when filing_period_end = '2026-03-31' then 1 else 0 end) as latest_rows,
                sum(case when filing_period_end = '2026-03-31' then fair_value_mm else 0 end) as latest_fair_value_mm
            from holdings
            group by fund
            """
        ).fetchall()
        by_fund = {row["fund"]: dict(row) for row in rows}
        return {
            cik: by_fund[ticker]
            for cik, (ticker, _) in VERIFIED_FUNDS.items()
            if ticker in by_fund
        }
    finally:
        con.close()


def expansion_audit_rows() -> dict[str, dict[str, Any]]:
    if not EXPANSION_DB_PATH.exists():
        return {}
    con = sqlite3.connect(EXPANSION_DB_PATH.resolve().as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        result: dict[str, dict[str, Any]] = {}
        for ticker, _, _ in (
            (identity[0], cik, identity[1])
            for cik, identity in TRACKER_AUDIT_COHORT.items()
        ):
            rows = con.execute(
                """
                select report_type, filing_period_end, status,
                       residual_fair_value_pct, residual_cost_pct,
                       raw_rows, deduplicated_rows
                from reconciliation
                where fund = ?
                order by filing_period_end, report_type
                """,
                (ticker,),
            ).fetchall()
            by_form = {row["report_type"]: dict(row) for row in rows}
            result[ticker] = {
                "forms": by_form,
                "tested_forms": sorted(by_form),
                "audit_status": (
                    "verified"
                    if ticker in {identity[0] for identity in VERIFIED_FUNDS.values()}
                    else "review"
                ),
            }
        return result
    finally:
        con.close()


def build_universe() -> dict[str, Any]:
    registry = get_bdc_list()
    registry_frame = registry.to_dataframe()
    bulk = fetch_bdc_dataset(2025, 1)
    bulk_frame = bulk.summary_by_company()

    bulk_by_cik: dict[int, dict[str, Any]] = {}
    for cik, group in bulk_frame.groupby("cik"):
        filed = sorted(str(value) for value in group["filed"].dropna().unique())
        forms = sorted(str(value) for value in group["form"].dropna().unique())
        bulk_by_cik[int(cik)] = {
            "name": str(group.iloc[0]["name"]),
            "bulk_soi_fact_rows": int(group["num_investments"].sum()),
            "bulk_forms": forms,
            "bulk_latest_filed": filed[-1] if filed else None,
        }

    registry_by_cik: dict[int, dict[str, Any]] = {}
    for item in registry_frame.to_dict(orient="records"):
        cik = int(item["cik"])
        registry_by_cik[cik] = {key: clean(value) for key, value in item.items()}
    native_registry_ciks = set(registry_by_cik)

    for cik, item in MANUAL_REGISTRY_EXCEPTIONS.items():
        registry_by_cik.setdefault(
            cik,
            {
                **item,
                "cik": cik,
                "last_filing_date": None,
                "last_filing_type": None,
                "manual_registry_exception": True,
            },
        )

    verified = verified_rows()
    expansion_audit = expansion_audit_rows()
    all_ciks = sorted(
        set(registry_by_cik)
        | set(bulk_by_cik)
        | set(VERIFIED_FUNDS)
        | set(TRACKER_AUDIT_COHORT)
    )
    rows = []
    for cik in all_ciks:
        registry_item = registry_by_cik.get(cik, {})
        bulk_item = bulk_by_cik.get(cik, {})
        verified_item = verified.get(cik)
        verified_identity = VERIFIED_FUNDS.get(cik)
        cohort_identity = TRACKER_AUDIT_COHORT.get(cik)
        display_identity = verified_identity or cohort_identity
        audit_item = expansion_audit.get(cohort_identity[0]) if cohort_identity else None

        if verified_item:
            coverage_status = "verified_holdings"
            coverage_label = "Verified holdings"
        elif bulk_item:
            coverage_status = "bulk_soi_available"
            coverage_label = "SEC bulk SOI available"
        else:
            coverage_status = "registry_only"
            coverage_label = "Registry only"

        name = str(
            registry_item.get("name")
            or bulk_item.get("name")
            or (display_identity[1] if display_identity else f"CIK {cik}")
        )
        rows.append(
            {
                "cik": cik,
                "ticker": display_identity[0] if display_identity else None,
                "name": name,
                "file_number": registry_item.get("file_number"),
                "city": registry_item.get("city"),
                "state": registry_item.get("state"),
                "last_filing_date": registry_item.get("last_filing_date"),
                "last_filing_type": registry_item.get("last_filing_type"),
                "is_active": registry_item.get("is_active"),
                "edgartools_registry": cik in native_registry_ciks,
                "manual_registry_exception": bool(
                    registry_item.get("manual_registry_exception")
                ),
                "bulk_period": bulk.period if bulk_item else None,
                "bulk_soi_fact_rows": bulk_item.get("bulk_soi_fact_rows", 0),
                "bulk_forms": bulk_item.get("bulk_forms", []),
                "bulk_latest_filed": bulk_item.get("bulk_latest_filed"),
                "coverage_status": coverage_status,
                "coverage_label": coverage_label,
                "tracker_audit_status": (
                    audit_item.get("audit_status") if audit_item else None
                ),
                "tracker_audit_forms": (
                    audit_item.get("forms") if audit_item else {}
                ),
                "verified_latest_period": (
                    verified_item.get("latest_period") if verified_item else None
                ),
                "verified_latest_rows": (
                    int(verified_item.get("latest_rows") or 0) if verified_item else 0
                ),
                "verified_latest_fair_value_mm": (
                    round(float(verified_item.get("latest_fair_value_mm") or 0), 6)
                    if verified_item
                    else None
                ),
            }
        )

    status_order = {
        "verified_holdings": 0,
        "bulk_soi_available": 1,
        "registry_only": 2,
    }
    rows.sort(
        key=lambda item: (
            status_order[item["coverage_status"]],
            0 if item["is_active"] is True else 1,
            item["name"].upper(),
        )
    )

    return {
        "meta": {
            "generated_at_utc": utc_now(),
            "edgartools_version": getattr(edgar, "__version__", "unknown"),
            "registry_entities": len(registry_frame),
            "universe_entities": len(rows),
            "active_registry_entities": sum(
                1 for row in rows if row["is_active"] is True
            ),
            "verified_funds": len(verified),
            "expansion_cohort_funds": len(TRACKER_AUDIT_COHORT),
            "expansion_cohort_verified": sum(
                1 for item in expansion_audit.values() if item["audit_status"] == "verified"
            ),
            "expansion_cohort_review": sum(
                1 for item in expansion_audit.values() if item["audit_status"] == "review"
            ),
            "bulk_period": bulk.period,
            "bulk_companies": bulk.num_companies,
            "bulk_soi_entries": bulk.num_soi_entries,
            "bulk_available_periods_note": (
                "EdgarTools currently lists SEC bulk BDC datasets through 2025 Q1. "
                "Verified local holdings continue through 2026 Q1."
            ),
        },
        "rows": rows,
        "limitations": [
            "SEC bulk SOI row counts are tagged fact rows, not canonical security counts.",
            "Bulk availability means the company appears in the quarterly SEC extract; it does not mean its detail has passed the tracker reconciliation gates.",
            "The requested 11-fund expansion cohort is audited form by form. MAIN, GBDC, and BBDC passed both latest-form checks; the other eight remain review-only because their detailed XBRL did not reconcile or was incomplete.",
            "ARCC and TSLX are included as manual registry exceptions because EdgarTools 5.42.0 does not resolve them in the current BDC registry even though their filings are available by CIK.",
        ],
    }


def main() -> None:
    if not os.environ.get("EDGAR_IDENTITY"):
        raise SystemExit("Set EDGAR_IDENTITY before querying SEC EDGAR.")
    payload = build_universe()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT_PATH.relative_to(DASHBOARD_ROOT)}")
    print(
        f"Universe {payload['meta']['universe_entities']} entities; "
        f"{payload['meta']['verified_funds']} verified; "
        f"{payload['meta']['bulk_companies']} in {payload['meta']['bulk_period']} bulk data"
    )


if __name__ == "__main__":
    main()
