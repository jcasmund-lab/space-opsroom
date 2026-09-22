# Space Ops Room v0.3 — one-time setup

You only need to do this once.

## 1. Upload the v0.3 files to `space-opsroom`

Replace `app.py` and `requirements.txt`, and add:

- `collector.py`
- `requirements-collector.txt`
- `supabase_schema.sql`
- `.github/workflows/collect.yml`

Do not put these files in the old `Space-update` repository.

## 2. Create a free Supabase project

Create a new Supabase project for Space Ops Room.

In Supabase, open **SQL Editor**, create a new query, paste all of `supabase_schema.sql`, and run it once.

## 3. Copy the two Supabase values

In Supabase project settings/API, note:

- Project URL
- the public anon/publishable key
- the service-role/secret key

The service-role key is sensitive. Never put it in a normal GitHub file.

## 4. Add GitHub Actions secrets

In the `space-opsroom` GitHub repository:

**Settings -> Secrets and variables -> Actions -> New repository secret**

Create:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

Use the project URL and the service-role key.

## 5. Add Streamlit secrets

Open the deployed Space Ops Room in Streamlit Community Cloud:

**Manage app -> Settings -> Secrets**

Paste:

```toml
SUPABASE_URL = "https://YOUR-PROJECT.supabase.co"
SUPABASE_ANON_KEY = "YOUR-PUBLIC-ANON-OR-PUBLISHABLE-KEY"
```

Save.

## 6. Start the collector immediately

In GitHub, open:

**Actions -> Collect Space Ops Data -> Run workflow**

The normal schedule then runs every 15 minutes.

The first CelesTrak run creates a baseline. Orbital change detection can only begin after the next CelesTrak snapshot, at least about two hours later.

## What should happen

Immediately:
- NOAA space weather remains live
- the three AOI maps remain visible

After the first collector run:
- GNSS cells/events should appear if Stanford has data for the current or previous UTC day
- persistent history changes to ONLINE
- source health starts reporting Stanford and CelesTrak

After at least two CelesTrak cycles:
- rule-based orbital-change candidates can begin appearing

## Data cadence

- Screen refresh: 30 seconds
- NOAA collector: every 15 minutes
- Stanford GNSS collector: about hourly
- CelesTrak orbital elements: no more often than every 125 minutes
- Detailed retention: 30 days

The CelesTrak cadence is intentionally conservative and follows its published fair-use guidance that GP data updates roughly every two hours.
