# Space Ops Room — v0.3

v0.3 is the first version that starts behaving like a monitoring system rather than a static dashboard.

## Added in v0.3

- All three AOIs remain visible simultaneously: Denmark, Baltic, Arctic
- Detailed dark basemaps with actual capitals as reference points
- Stanford GPS Lab GNSS interference data:
  - hourly jamming heatmap cells when available
  - jamming/spoofing event centroids
  - AOI status, confidence and 6h/24h/7d trend
- Persistent history in Supabase
- 24/7 data collection through GitHub Actions
- CelesTrak OMM/GP history for GEO, MILITARY, GPS-OPS and GALILEO
- Conservative rule-based orbital-change candidate detection
- 30-day detailed data retention
- Source health and freshness
- Watch Items prioritise GNSS, spoofing, orbital changes and space weather

## Important limits

- The GNSS layer is ADS-B-derived. It is an interference indicator, not a direct RF measurement.
- A CelesTrak orbital-change candidate is not proof of a manoeuvre, RPO or hostile action.
- Proximity/RPO detection is not implemented yet.
- Satellite pass forecasting and reentry windows remain a later phase.

## Files to upload to the GitHub repository

Replace:
- `app.py`
- `requirements.txt`

Add:
- `collector.py`
- `requirements-collector.txt`
- `supabase_schema.sql`
- `.github/workflows/collect.yml`

The existing `README.md` can be replaced with this one if desired.

## One-time setup

See `SETUP_V0.3.md`.
