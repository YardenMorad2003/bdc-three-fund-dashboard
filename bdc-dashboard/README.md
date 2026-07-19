# Verified Eight-Fund BDC Dashboard

Next.js dashboard for the centralized ARCC, BBDC, BXSL, FSK, GBDC, MAIN, OBDC, and TSLX holdings database, with an audited EdgarTools/SEC expansion cohort and broader universe directory.

## Data

The app reads from:

`../output/bdc_tracker_centralized/bdc_tracker_holdings.sqlite`

The EdgarTools expansion audit and reconciled source rows are stored in:

`../output/edgartools_bdc_expansion/edgartools_bdc_expansion_holdings.sqlite`

and writes static JSON snapshots to:

- `lib/dashboard-data.json`
- `lib/quarterly-bdc-facts.json`
- `lib/bdc-universe.json`

The quarterly facts exporter also writes:

`../output/three_fund_institutional_model/three_fund_institutional_model.sqlite`

For market-price/NAV facts, the quarterly facts exporter reads:

`../source-docs/bdc_close_raw.csv`

For reproducible local builds, download the database bundle from:

[Data release 2026-05-27](https://github.com/YardenMorad2003/bdc-three-fund-dashboard/releases/tag/data-2026-05-27)

The linked release predates the EdgarTools expansion and provides the original tracker source bundle. Rebuild the expansion database with `extract_edgartools_bdc_cohort.py` before rebuilding the centralized tracker database. The institutional model SQLite is included for inspection, but `npm run data` regenerates it.

Regenerate the snapshot with:

```bash
npm run data
```

Regenerate only the quarterly facts model with:

```bash
npm run facts
```

Regenerate the EdgarTools BDC universe snapshot with an SEC-compliant `EDGAR_IDENTITY` configured:

```bash
npm run universe
```

The universe snapshot combines the current EdgarTools BDC registry with its latest listed SEC bulk BDC dataset. Bulk Schedule of Investments rows are discovery coverage only. MAIN, GBDC, and BBDC passed both latest-form reconciliation gates and joined the original five verified holdings funds. HTGC, CSWC, TCPC, BCSF, OCSL, NMFC, CCAP, and PSEC remain audit-visible but do not feed portfolio analytics because their default detailed extraction was incomplete or did not reconcile. Financials, deterioration, and liabilities remain presentation/filing-enriched for BXSL, FSK, and TSLX.

## Run

```bash
npm install
npm run data
npm run dev
```

If another app already owns port 3000, use the static export:

```bash
npm run build
py -m http.server 3002 --bind 127.0.0.1 --directory out
```

## Deploy To GitHub Pages

This repo includes `.github/workflows/pages.yml`, which builds the static Next.js export and publishes `bdc-dashboard/out` to GitHub Pages.

In GitHub:

1. Open the repository settings.
2. Go to **Pages**.
3. Set **Build and deployment** source to **GitHub Actions**.
4. Push to `main` or `master`, or run the workflow manually from the **Actions** tab.

For project pages, the workflow sets `GITHUB_PAGES=true` during the build. `next.config.mjs` then derives the repository name from `GITHUB_REPOSITORY` and applies the correct base path automatically.
