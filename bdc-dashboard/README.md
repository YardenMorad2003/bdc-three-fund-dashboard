# BDC Three-Fund Dashboard

Next.js dashboard for the phase-one centralized BDC holdings database.

## Data

The app reads from:

`../output/bdc_5_fund_centralized/bdc_5_fund_holdings.sqlite`

and writes static JSON snapshots to:

- `lib/dashboard-data.json`
- `lib/quarterly-bdc-facts.json`

The quarterly facts exporter also writes:

`../output/three_fund_institutional_model/three_fund_institutional_model.sqlite`

Regenerate the snapshot with:

```bash
npm run data
```

Regenerate only the quarterly facts model with:

```bash
npm run facts
```

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
