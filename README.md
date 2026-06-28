---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: '6a4472e7-d521-4c79-bb03-b2020ac7ae78'
  PropagateID: '6a4472e7-d521-4c79-bb03-b2020ac7ae78'
  ReservedCode1: 'd1cfe45f-604f-4790-a25d-f67eb4426814'
  ReservedCode2: 'd1cfe45f-604f-4790-a25d-f67eb4426814'
---

# Overseas Data Hub v6.0.8

Global Business Intelligence Dashboard — 18 modules, 380+ sources, dual-engine architecture.

## Architecture

- **Engine A (Base)**: GitHub Actions, daily full scan (UTC 00:00 = Beijing 08:00)
  - GNews RSS + 18 module queries + Playwright redirect resolution + full text extraction
  - Incremental SeenIndex dedup + cross-module dedup
- **Engine B (Scout)**: RSSHub + Vercel, real-time targeted fetch (planned)

## Modules (18)

| Type | Module | Output |
|------|--------|--------|
| Scenario | global_business | global_business.json |
| Scenario | finance_global | finance_global.json |
| Theme | tech_industry | tech_industry.json |
| Theme | energy_commodities | energy_commodities.json |
| Theme | geopolitics_risk | geopolitics_risk.json |
| Theme | esg_sustainability | esg_sustainability.json |
| Theme | global_risk | global_risk.json |
| Theme | cross_border_ecommerce | cross_border_ecommerce.json |
| Theme | trade_import_export | trade_import_export.json |
| Theme | chinese_firms_overseas | chinese_firms_overseas.json |
| Region | region_se_asia | se_asia.json |
| Region | region_south_asia | south_asia.json |
| Region | region_middle_east | middle_east.json |
| Region | region_latin_america | latam.json |
| Region | region_africa | africa.json |
| Region | region_europe | europe.json |
| Region | region_cis | cis.json |
| Region | region_east_asia | east_asia.json |

## Data Pipeline

1. **Actions (GitHub)**: `fetch_all.py` → 18 modules → Playwright resolve → Full text → Artifacts
2. **Local**: `download_daily.py` (gh artifact download → merge sync) → `import_to_vault.py` (Obsidian) → `gen_unified_html.py` (HTML report)

## Configuration

All config files in `scripts/config/`:
- `keywords.yaml` — Module keywords + source_authority coefficients
- `classification.yaml` — Category mapping + module defaults
- `source_tier_override.yaml` — Domain-based tier override (A-E)

## Manual Trigger

```bash
# Incremental (daily)
gh workflow run daily-fetch.yml

# Playwright backfill only
gh workflow run daily-fetch.yml -f mode=pw-backfill
```

## Version

v6.0.8 (2026-06-28)