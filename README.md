# space-opsroom

Space Ops Room — v0.1

First working slice of the Space Operations COP.

What works now

• 16:9-oriented dark operations display
• Automatic 30-second refresh
• Automatic AOI focus rotation: Denmark → Baltic → Arctic
• Live NOAA SWPC:
  • planetary Kp
  • G/R/S scales
  • 6h / 24h / 7d Kp trend
  • near-term Kp forecast
• CelesTrak GPS and Galileo TLE data
• Satellite positions propagated locally on each refresh
• Calm status logic: NORMAL / WATCH / ELEVATED / IMPACT
• Explicit DATA LIMITED / BASELINE labels where the data is not yet sufficient

Important design choice

v0.1 does not pretend that GNSS interference or orbital anomalies are already available.
Those are the next integrations. This keeps the COP trustworthy from the start.

Upload to GitHub

Upload these items to the root of the new space-opsroom repository:

• app.py
• requirements.txt
• .streamlit/config.toml

README.md is optional.

Do not upload these files to the old Space-update repository.

Deploy on Streamlit Community Cloud

Create a new app and select:

• Repository: space-opsroom
• Branch: main
• Main file: app.py

No API keys or secrets are required for v0.1.

Data cadence

• Screen rerender / AOI change: 30 seconds
• NOAA calls: cached for 5 minutes
• CelesTrak GP/TLE calls: cached for 2 hours
• Satellite positions are recalculated locally each screen refresh

Next phase

1. GNSS interference layer for Denmark / Baltic / Arctic
2. Persistent database and 30-day history
3. SDA baseline + manoeuvre/change detection
4. Watch / Follow / Pin workflow
5. AOI-specific NEXT UP
6. Briefing Mode