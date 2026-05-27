# BDC Three-Fund Dashboard

A static Next.js dashboard for comparing three public business development companies:

- BXSL, Blackstone Secured Lending Fund
- FSK, FS KKR Capital Corp.
- TSLX, Sixth Street Specialty Lending, Inc.

Live site: [yardenmorad2003.github.io/bdc-three-fund-dashboard](https://yardenmorad2003.github.io/bdc-three-fund-dashboard/)

The dashboard is built from holding-level and filing-level data work products. It is meant to make the portfolio, financial, credit quality, liability, and issuer-level comparisons easier to inspect in one place.

## Project Aim

The aim of this project is to transform unclear Excel and PDF filings into a readable, structured database that is easy to query. In that sense, the project is mainly data engineering plus data analysis: collecting messy source material, normalizing it, preserving source context, and turning it into usable tables.

A good example is the portfolio holdings schedule in FSK's 2025 Form 10-K. The source page contains issuer names, footnote markers, industries, interest-rate text, maturity dates, principal amounts, cost, and fair value in a dense filing layout. Before the data can be analyzed properly, that page has to be parsed into rows, the fields have to be normalized, and the source context has to remain traceable.

That processing step also matters for interpretation. For the FSK timeline data, rows marked with footnote `(x)` are treated as unfunded commitments rather than funded holdings. The dashboard keeps those rows in the detailed security table, but excludes them from funded timeline aggregates. In the current timeline export, that produces 1,199 funded security rows and 213 unfunded-commitment rows retained separately.

The usefulness can go beyond the dashboard itself. Once the data is structured and queryable, it can potentially support more advanced data science and machine learning work, including issuer comparison, anomaly detection, portfolio risk screening, trend analysis, and automated source reconciliation.

## What It Covers

The current dashboard scope is intentionally narrow. It covers BXSL, FSK, and TSLX only, with a latest common dashboard period of March 31, 2026.

The app includes views for:

- Portfolio overview and fair value trends
- Latest holdings by fund and period
- Financial snapshots and quarterly fact tables
- Income quality, dividend coverage, and activity metrics
- Non-accruals, issuer watchlists, and deterioration screens
- Cross-fund issuer exposure
- Borrower timeline pages inside the app experience
- Liability stacks, refinancing context, and funding mix
- Methodology notes for source handling and reconciliation

## Design Philosophy

This project is source-first. The goal is not to smooth every number into a single forced answer. When reported presentation totals and schedule-derived holdings totals do not line up, the dashboard keeps those fields separate so the mismatch remains visible.

The same idea applies to issuer matching and schedule rows. The dashboard preserves as-filed holdings rows while adding normalized fields for comparison. This is useful for cross-fund analysis, but it also means source notes and methodology matter.

## Data Sources

The deployed app runs from static JSON snapshots committed in the repository:

- `bdc-dashboard/lib/dashboard-data.json`
- `bdc-dashboard/lib/quarterly-bdc-facts.json`
- `bdc-dashboard/lib/liability-stack.json`
- `bdc-dashboard/lib/company-enrichment.json`

The source generation scripts are included in:

- `bdc-dashboard/scripts/export-dashboard-data.py`
- `bdc-dashboard/scripts/export-quarterly-facts.py`

For reproducibility, the SQLite databases needed to regenerate the public dashboard snapshots are attached to the GitHub Release:

- [Data release 2026-05-27](https://github.com/YardenMorad2003/bdc-three-fund-dashboard/releases/tag/data-2026-05-27)
- Direct asset: [bdc-three-fund-dashboard-databases-2026-05-27.zip](https://github.com/YardenMorad2003/bdc-three-fund-dashboard/releases/download/data-2026-05-27/bdc-three-fund-dashboard-databases-2026-05-27.zip)

The release bundle includes sanitized copies of:

- `output/bdc_5_fund_centralized/bdc_5_fund_holdings.sqlite`
- `output/three_fund_institutional_model/three_fund_institutional_model.sqlite`

The central holdings database contains 10,125 holdings rows, source metadata, QC tables, and the views used by the exporters. Absolute local workbook paths were replaced with `source_workbooks/<filename>` before publication. Raw downloaded PDFs, Excel workbooks, scratch databases, and temporary research folders are still excluded from Git.

To rebuild the committed JSON snapshots from the released databases, unzip the bundle, place the database files back under the paths above, then run:

```bash
cd bdc-dashboard
npm run data
npm run build
```

The committed JSON snapshots are what the public dashboard uses at runtime.

## Important Methodology Notes

- The app currently covers BXSL, FSK, and TSLX only.
- Quarterly facts combine holdings-derived history with filing-level income, dividend, activity, and non-accrual facts where available.
- Reported presentation totals and gross schedule totals stay separate when they have different definitions.
- TSLX Q2 2025 spreadsheet-derived holdings coverage is limited because the relevant holdings spreadsheet was not available in the working data set.
- Some activity fields show `n/a` because the source did not separately disclose that item.
- FSK Q1 2026 dividend coverage uses the quarter-related $0.45 base distribution and $0.48 total distribution, rather than the $0.42 distribution declaration timing line shown in the 3/31/26 column of the Financial Results table.

## Tech Stack

- Next.js
- React
- TypeScript
- Static export via `next build`
- GitHub Pages deployment through GitHub Actions
- Python data export scripts for local regeneration

## Repository Layout

```text
.
|-- .github/workflows/pages.yml
|-- README.md
`-- bdc-dashboard/
    |-- app/
    |-- lib/
    |-- public/
    |-- scripts/
    |-- next.config.mjs
    |-- package.json
    `-- README.md
```

## Running Locally

Install dependencies from the dashboard directory:

```bash
cd bdc-dashboard
npm install
```

Start the local development server:

```bash
npm run dev
```

Build the static site:

```bash
npm run build
```

Preview the static export:

```bash
py -m http.server 3002 --bind 127.0.0.1 --directory out
```

Then open:

```text
http://127.0.0.1:3002
```

## Regenerating Data

The checked-in JSON files are enough to run and deploy the dashboard. To regenerate them from the local research workspace, the upstream SQLite and source files need to exist in the expected local locations.

From `bdc-dashboard`:

```bash
npm run data
```

To regenerate only the quarterly facts layer:

```bash
npm run facts
```

These commands are primarily for the original research environment. A fresh clone of this repository will not have the private local source databases or downloaded source files needed to rebuild the snapshots from scratch.

## GitHub Pages Deployment

The site is deployed with GitHub Actions:

```text
.github/workflows/pages.yml
```

On each push to `master` or `main`, the workflow:

1. Installs Node dependencies.
2. Builds the Next.js static export.
3. Uploads `bdc-dashboard/out` as a Pages artifact.
4. Publishes the artifact to GitHub Pages.

The Next.js config automatically detects GitHub Pages builds and applies the repository base path, so the app works at:

```text
https://yardenmorad2003.github.io/bdc-three-fund-dashboard/
```

## Public Repository Notes

This repository is public so GitHub Pages can host the dashboard. The committed data snapshots and methodology text are public as well. The raw local research folders, source PDFs, Excel files, SQLite outputs, temporary files, and build artifacts are excluded from Git.

The root `.gitignore` intentionally keeps the repository focused on the deployable dashboard app.

## Disclaimer

This project is for research and analysis. It is not investment advice, a recommendation, or a substitute for reading the original filings and source documents.
