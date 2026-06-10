# Overseas Data Hub v3.3

Global Business Intelligence Dashboard — 14 modules, 340+ sources, dual-engine architecture.

## Architecture

- **Engine A (Base)**: GitHub Actions + jsDelivr CDN, daily full scan (UTC 00:00 = Beijing 08:00)
- **Engine B (Scout)**: RSSHub + Vercel, real-time targeted fetch (planned)

## Modules (14)

| Type | Module | Output |
|------|--------|--------|
| Scenario | global_business | global_business.json |
| Scenario | finance_global | finance.json |
| Theme | tech_industry | tech_industry.json |
| Theme | energy_commodities | energy_commodities.json |
| Theme | geopolitics_risk | geopolitics_risk.json |
| Theme | esg_sustainability | esg_sustainability.json |
| Region | region_se_asia | se_asia.json |
| Region | region_south_asia | south_asia.json |
| Region | region_middle_east | middle_east.json |
| Region | region_latin_america | latam.json |
| Region | region_africa | africa.json |
| Region | region_europe | europe.json |
| Region | region_cis | cis.json |
| Region | region_east_asia | east_asia.json |

## CDN Access

```
https://cdn.jsdelivr.net/gh/WOHO99/overseas-data-hub@main/index.json
https://cdn.jsdelivr.net/gh/WOHO99/overseas-data-hub@main/{module}.json
```

## Signal Detection

- Each module has signal keyword group in `scripts/config/keywords.yaml`
- Articles tagged with signal_keywords on match
- `global_signal_alerts` in index.json when same signal word appears >=5 times globally

## Local Test

```bash
cd scripts
pip install -r ../requirements.txt
python fetch_all.py
```

## Manual Trigger

GitHub Actions workflow supports `workflow_dispatch` for on-demand runs.

## Version

v3.3 (2026-06-11)
