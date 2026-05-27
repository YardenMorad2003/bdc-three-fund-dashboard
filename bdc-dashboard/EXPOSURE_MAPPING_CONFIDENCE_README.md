# Exposure Tab Mapping Confidence Handoff

Date: 2026-05-27

This note captures a small UI clarification in the BDC dashboard Exposure tab.

## What changed

- In `app/page.tsx`, the bare `high` / `medium` / `low` pill in the `Company And Sponsor` panel now has the label `Mapping confidence`.
- A short helper sentence clarifies that this confidence score reflects the issuer-to-company/sponsor match, not exposure level or credit risk.
- In `app/globals.css`, small styles were added for the labeled confidence badge and helper note.

## Meaning

`Mapping confidence: high` means the dashboard has strong support for matching the holdings issuer to the displayed company and sponsor enrichment record. It is not a risk rating.
