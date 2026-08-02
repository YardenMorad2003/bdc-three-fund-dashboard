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
- `lib/free-source-intelligence.json`
- `lib/nport-consensus-marks.json`
- `lib/bdc-equity-positioning.json`

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

Refresh the free external-source layer:

```bash
npm run sources
```

Refresh the two heavier public-market evidence layers separately:

```bash
npm run nport:consensus
npm run positioning
```

Refresh the ARCC filing-update snapshot after loading a new quarter into the centralized holdings database:

```bash
npm run arcc:update
```

The cross-fund comparison views remain aligned to the latest common reporting date. The ARCC update card and ARCC valuation use the fund's newer quarter as soon as it is available.

`nport:consensus` streams the latest SEC quarterly Form N-PORT bulk archive from `.cache/nport-consensus/` and writes compact borrower-level fund consensus marks to `lib/nport-consensus-marks.json`. The raw archive is intentionally ignored by Git. `positioning` refreshes VanEck BIZD holdings, FINRA consolidated short interest, FINRA off-exchange short-sale volume, and SEC fails-to-deliver observations in `lib/bdc-equity-positioning.json`. Run both with `npm run market-evidence`.

The refresh uses official SEC monthly BDC, Form D, and insider-transaction bulk files; issuer-published SRLN/BKLN/FLBL holdings downloads where available; GLEIF; OpenFIGI; and public FRED CSV series. Every provider receives a visible status (`refreshed`, `available_not_refreshed`, `credential_required`, or `error`) in the dashboard. Raw entity, legal, and debt-fact matches remain review candidates and do not overwrite verified issuer identities.

Optional environment variables enable the credentialed free tiers:

- `EDGAR_IDENTITY`: SEC-compliant name and contact identity.
- `MASSIVE_API_KEY`: current BDC closes, dividends, and splits; refreshed closes can replace older static market inputs.
- `COURTLISTENER_API_TOKEN`: quoted-name legal and bankruptcy search for priority issuers.
- `COMPANIES_HOUSE_API_KEY`: UK company search candidates.
- `OPENCORPORATES_API_TOKEN`: global registry search candidates, subject to provider terms.
- `OPENFIGI_API_KEY`: optional; unauthenticated CUSIP mapping works at lower rate limits.
- `BDC_GLEIF_QUERY_LIMIT`, `BDC_REGISTRY_QUERY_LIMIT`, and `BDC_LEGAL_QUERY_LIMIT`: cap provider queries.

The SEC Form 13F information table is implemented but deliberately opt-in because the quarterly bulk file is large:

```bash
npm run sources:heavy-13f
```

PACER is not queried because it can incur fees. CourtListener is the free legal-alert layer, and all matches require docket review.

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
