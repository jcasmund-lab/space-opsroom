import json
import math
import os
import shutil
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests


SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

HEADERS = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
}

USER_AGENT = "space-opsroom-collector/0.3"

AOIS = {
    "DENMARK": (54.3, 58.2, 7.5, 15.8),
    "BALTIC": (52.0, 61.8, 8.0, 31.5),
    "ARCTIC": (60.0, 90.0, -75.0, 45.0),
}

CELESTRAK_GROUPS = ["GEO", "MILITARY", "GPS-OPS", "GALILEO"]


def now_utc():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat()


def sb_url(table):
    return f"{SUPABASE_URL}/rest/v1/{table}"


def sb_get(table, params=None):
    r = requests.get(sb_url(table), headers=HEADERS, params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()


def sb_upsert(table, rows, on_conflict=None):
    if not rows:
        return
    params = {}
    if on_conflict:
        params["on_conflict"] = on_conflict
    headers = dict(HEADERS)
    headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
    for start in range(0, len(rows), 500):
        chunk = rows[start:start+500]
        r = requests.post(sb_url(table), headers=headers, params=params, json=chunk, timeout=60)
        r.raise_for_status()


def sb_delete_older_than(table, column, days):
    cutoff = iso(now_utc() - timedelta(days=days))
    params = {column: f"lt.{cutoff}"}
    r = requests.delete(sb_url(table), headers=HEADERS, params=params, timeout=30)
    r.raise_for_status()


def set_status(source, detail, rows_written=0):
    sb_upsert(
        "collector_status",
        [{
            "source": source,
            "last_success": iso(now_utc()),
            "detail": detail[:500],
            "rows_written": int(rows_written),
        }],
        "source",
    )


def last_success(source):
    rows = sb_get(
        "collector_status",
        {
            "select": "last_success",
            "source": f"eq.{source}",
            "limit": "1",
        }
    )
    if not rows:
        return None
    try:
        return datetime.fromisoformat(rows[0]["last_success"].replace("Z", "+00:00"))
    except Exception:
        return None


def due(source, minutes):
    last = last_success(source)
    return last is None or (now_utc() - last) >= timedelta(minutes=minutes)


# ============================================================
# NOAA
# ============================================================
def collect_noaa():
    urls = {
        "kp": "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json",
        "scales": "https://services.swpc.noaa.gov/products/noaa-scales.json",
    }
    payload = {}
    for key, url in urls.items():
        r = requests.get(url, timeout=20, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        payload[key] = r.json()

    kp_rows = payload["kp"] or []
    current = kp_rows[-1] if kp_rows else {}
    scales_row = (payload["scales"] or {}).get("0", {})

    def scale(name):
        try:
            return int((scales_row.get(name) or {}).get("Scale") or 0)
        except Exception:
            return 0

    row = {
        "observed_at": current.get("time_tag") or iso(now_utc()),
        "kp": float(current.get("Kp") or 0),
        "g_scale": scale("G"),
        "r_scale": scale("R"),
        "s_scale": scale("S"),
        "source": "NOAA SWPC",
        "collected_at": iso(now_utc()),
    }
    sb_upsert("space_weather", [row], "observed_at")
    set_status("noaa_space_weather", "NOAA SWPC Kp + G/R/S", 1)


# ============================================================
# STANFORD GNSS
# ============================================================
def flatten_dict_lists(obj):
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        out = []
        for value in obj.values():
            if isinstance(value, list):
                out.extend([x for x in value if isinstance(x, dict)])
            elif isinstance(value, dict):
                out.append(value)
        return out
    return []


def h3_center(h3_index):
    try:
        from h3 import h3 as h3_old
        lat, lon = h3_old.h3_to_geo(h3_index)
        return float(lat), float(lon)
    except Exception:
        try:
            import h3
            lat, lon = h3.cell_to_latlng(h3_index)
            return float(lat), float(lon)
        except Exception:
            return None, None


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None


def newest_hourly_heatmap(day_dir):
    dirs = []
    for p in Path(day_dir).iterdir():
        if p.is_dir() and len(p.name) == 4 and p.name.isdigit() and (p / "heatmap.json").exists():
            dirs.append(p)
    if not dirs:
        daily = Path(day_dir) / "heatmap.json"
        return daily if daily.exists() else None, "daily"
    latest = sorted(dirs, key=lambda p: p.name)[-1]
    return latest / "heatmap.json", latest.name


def inside(bounds, lat, lon):
    south, north, west, east = bounds
    return south <= lat <= north and west <= lon <= east


def classify_aoi(score, max_pct, aircraft):
    if aircraft < 10:
        return "UNKNOWN", "LOW"
    if score >= 10 or max_pct >= 20:
        status = "ELEVATED"
    elif score >= 2 or max_pct >= 10:
        status = "WATCH"
    else:
        status = "NORMAL"

    if aircraft >= 100:
        confidence = "HIGH"
    elif aircraft >= 30:
        confidence = "MED"
    else:
        confidence = "LOW"
    return status, confidence


def parse_jamming_cells(data):
    rows = flatten_dict_lists(data)
    out = []
    for r in rows:
        h = r.get("h3Index") or r.get("h3_index")
        if not h:
            continue
        lat, lon = h3_center(h)
        if lat is None:
            continue
        low = r.get("lowQualityCount", r.get("low_quality_count", 0)) or 0
        total = r.get("totalAircraftCount", r.get("total_aircraft_count", 0)) or 0
        try:
            low = int(low)
            total = int(total)
        except Exception:
            continue
        pct = (100.0 * low / total) if total > 0 else 0.0
        out.append({
            "h3_index": str(h),
            "lat": lat,
            "lon": lon,
            "affected_pct": pct,
            "affected_count": low,
            "total_count": total,
        })
    return out


def parse_events(data, mode, data_date):
    rows = flatten_dict_lists(data)
    out = []
    for i, r in enumerate(rows):
        lat = r.get("latitude", r.get("lat"))
        lon = r.get("longitude", r.get("lon"))
        if lat is None or lon is None:
            continue
        start = r.get("startTime", r.get("start_time"))
        end = r.get("endTime", r.get("end_time"))
        key = r.get("eventId") or r.get("id") or f"{mode}:{data_date}:{i}:{float(lat):.3f}:{float(lon):.3f}"
        out.append({
            "mode": mode,
            "event_key": str(key),
            "observed_date": data_date,
            "start_time": start,
            "end_time": end,
            "lat": float(lat),
            "lon": float(lon),
            "collected_at": iso(now_utc()),
            "source": "Stanford GPS Lab",
        })
    return out


def collect_stanford_gnss():
    # The official Stanford downloader currently requires Python <3.12,
    # so this GitHub Action intentionally runs Python 3.11.
    from rfi_fileparser import downloader

    today = now_utc().date()
    date_str = today.strftime("%Y/%m/%d")
    root = Path(tempfile.mkdtemp(prefix="rfi_"))
    old_cwd = Path.cwd()

    all_cells = []
    all_events = []
    snapshot_rows = []

    try:
        os.chdir(root)

        for mode in ("jamming", "spoofing"):
            try:
                downloader.download_files(date_str, date_str, mode)
            except Exception:
                # Current UTC day can be incomplete. Try yesterday as a fallback.
                yday = today - timedelta(days=1)
                ystr = yday.strftime("%Y/%m/%d")
                downloader.download_files(ystr, ystr, mode)

        # Prefer today if present; otherwise yesterday.
        chosen_date = None
        jam_day = None
        for d in [today, today - timedelta(days=1)]:
            p = root / "downloaded_json_files" / "jamming" / d.strftime("%Y/%m/%d")
            if p.exists():
                chosen_date = d
                jam_day = p
                break

        if jam_day:
            heat_path, granularity = newest_hourly_heatmap(jam_day)
            if heat_path:
                cells = parse_jamming_cells(read_json(heat_path))
                if granularity == "daily":
                    observed_at = datetime.combine(chosen_date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=23)
                else:
                    hour = int(granularity[:2])
                    observed_at = datetime.combine(chosen_date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=hour)

                for c in cells:
                    all_cells.append({
                        "mode": "jamming",
                        "observed_at": iso(observed_at),
                        "granularity": "daily" if granularity == "daily" else "hourly",
                        "h3_index": c["h3_index"],
                        "lat": c["lat"],
                        "lon": c["lon"],
                        "affected_pct": c["affected_pct"],
                        "affected_count": c["affected_count"],
                        "total_count": c["total_count"],
                        "collected_at": iso(now_utc()),
                        "source": "Stanford GPS Lab",
                    })

                # AOI summary snapshots.
                for name, bounds in AOIS.items():
                    subset = [c for c in cells if inside(bounds, c["lat"], c["lon"])]
                    total_aircraft = sum(c["total_count"] for c in subset)
                    affected = sum(c["affected_count"] for c in subset)
                    score = 100.0 * affected / total_aircraft if total_aircraft else 0.0
                    max_pct = max([c["affected_pct"] for c in subset], default=0.0)
                    affected_cells = sum(1 for c in subset if c["affected_pct"] >= 2.0)
                    status, confidence = classify_aoi(score, max_pct, total_aircraft)
                    snapshot_rows.append({
                        "observed_at": iso(observed_at),
                        "aoi": name,
                        "mode": "jamming",
                        "score": score,
                        "status": status,
                        "confidence": confidence,
                        "affected_cells": affected_cells,
                        "max_pct": max_pct,
                        "aircraft_count": total_aircraft,
                        "granularity": "daily" if granularity == "daily" else "hourly",
                        "source": "Stanford GPS Lab",
                    })

        # Event centroids for both jamming and spoofing.
        for mode in ("jamming", "spoofing"):
            mode_root = root / "downloaded_json_files" / mode
            for d in [today, today - timedelta(days=1)]:
                day_dir = mode_root / d.strftime("%Y/%m/%d")
                if not day_dir.exists():
                    continue
                event_file = None
                for name in ("events.json", "event.json"):
                    candidate = day_dir / name
                    if candidate.exists():
                        event_file = candidate
                        break
                if event_file:
                    all_events.extend(parse_events(read_json(event_file), mode, d.isoformat()))
                break

        sb_upsert("gnss_cells", all_cells, "mode,observed_at,h3_index")
        sb_upsert("gnss_aoi_snapshots", snapshot_rows, "observed_at,aoi,mode")
        sb_upsert("gnss_events", all_events, "event_key")

        set_status(
            "stanford_gnss",
            f"Stanford GNSS: {len(all_cells)} cells, {len(all_events)} events",
            len(all_cells) + len(all_events),
        )
    finally:
        os.chdir(old_cwd)
        shutil.rmtree(root, ignore_errors=True)


# ============================================================
# CELESTRAK ORBITAL CHANGE DETECTION
# ============================================================
MU_EARTH = 398600.4418  # km^3 / s^2


def semimajor_axis_km(mean_motion_rev_day):
    n = float(mean_motion_rev_day) * 2.0 * math.pi / 86400.0
    if n <= 0:
        return None
    return (MU_EARTH / (n * n)) ** (1.0 / 3.0)


def float_or_none(v):
    try:
        return float(v)
    except Exception:
        return None


def fetch_celestrak_group(group):
    url = "https://celestrak.org/NORAD/elements/gp.php"
    r = requests.get(
        url,
        params={"GROUP": group, "FORMAT": "JSON"},
        headers={"User-Agent": USER_AGENT},
        timeout=45,
    )
    # Important: no automatic retry loop. Respect CelesTrak usage policy.
    r.raise_for_status()
    return r.json()


def previous_latest(group):
    rows = sb_get(
        "latest_orbital_elements",
        {
            "select": "norad_cat_id,object_name,epoch,mean_motion,eccentricity,inclination,semi_major_axis_km,collected_at",
            "group_name": f"eq.{group}",
            "limit": "2000",
        }
    )
    return {str(r["norad_cat_id"]): r for r in rows}


def orbit_class(mean_motion):
    if not mean_motion:
        return "UNKNOWN"
    period_min = 1440.0 / mean_motion
    if period_min >= 1200:
        return "GEO"
    if period_min >= 500:
        return "MEO"
    return "LEO"


def detect_change(prev, cur):
    if not prev:
        return None

    old_a = float_or_none(prev.get("semi_major_axis_km"))
    new_a = float_or_none(cur.get("semi_major_axis_km"))
    old_i = float_or_none(prev.get("inclination"))
    new_i = float_or_none(cur.get("inclination"))
    old_e = float_or_none(prev.get("eccentricity"))
    new_e = float_or_none(cur.get("eccentricity"))

    da = abs(new_a - old_a) if old_a is not None and new_a is not None else 0.0
    di = abs(new_i - old_i) if old_i is not None and new_i is not None else 0.0
    de = abs(new_e - old_e) if old_e is not None and new_e is not None else 0.0

    cls = orbit_class(float_or_none(cur.get("mean_motion")))
    if cls == "GEO":
        a_thr, i_thr, e_thr = 15.0, 0.08, 0.0005
    elif cls == "MEO":
        a_thr, i_thr, e_thr = 20.0, 0.08, 0.0010
    else:
        a_thr, i_thr, e_thr = 25.0, 0.15, 0.0020

    triggers = []
    if da >= a_thr:
        triggers.append(f"Δa {da:.0f} km")
    if di >= i_thr:
        triggers.append(f"Δi {di:.2f}°")
    if de >= e_thr:
        triggers.append(f"Δe {de:.4f}")

    if not triggers:
        return None

    strong = (da >= 3*a_thr) or (di >= 3*i_thr) or (de >= 3*e_thr)
    multi = len(triggers) >= 2
    severity = "ELEVATED" if strong or multi else "WATCH"
    confidence = "HIGH" if multi else "MED"

    return {
        "severity": severity,
        "confidence": confidence,
        "summary": "Candidate orbital change · " + " · ".join(triggers),
        "metrics": {
            "orbit_class": cls,
            "delta_a_km": da,
            "delta_i_deg": di,
            "delta_e": de,
            "threshold_a_km": a_thr,
            "threshold_i_deg": i_thr,
            "threshold_e": e_thr,
        }
    }


def collect_celestrak():
    collected = iso(now_utc())
    total = 0
    event_rows = []
    all_rows = []

    # Download each needed group once per collection cycle, never more often than 2 h.
    for group in CELESTRAK_GROUPS:
        prev_map = previous_latest(group)
        data = fetch_celestrak_group(group)

        for obj in data:
            norad = str(obj.get("NORAD_CAT_ID") or "").strip()
            if not norad:
                continue

            mm = float_or_none(obj.get("MEAN_MOTION"))
            a = semimajor_axis_km(mm) if mm else None

            row = {
                "collected_at": collected,
                "group_name": group,
                "norad_cat_id": norad,
                "object_name": obj.get("OBJECT_NAME") or norad,
                "object_id": obj.get("OBJECT_ID"),
                "epoch": obj.get("EPOCH"),
                "mean_motion": mm,
                "eccentricity": float_or_none(obj.get("ECCENTRICITY")),
                "inclination": float_or_none(obj.get("INCLINATION")),
                "ra_of_asc_node": float_or_none(obj.get("RA_OF_ASC_NODE")),
                "arg_of_pericenter": float_or_none(obj.get("ARG_OF_PERICENTER")),
                "mean_anomaly": float_or_none(obj.get("MEAN_ANOMALY")),
                "bstar": float_or_none(obj.get("BSTAR")),
                "semi_major_axis_km": a,
                "source": "CelesTrak GP/OMM",
            }
            all_rows.append(row)

            change = detect_change(prev_map.get(norad), row)
            if change:
                event_key = f"{norad}:{obj.get('EPOCH')}:orbital-change"
                event_rows.append({
                    "event_key": event_key,
                    "detected_at": collected,
                    "norad_cat_id": norad,
                    "object_name": row["object_name"],
                    "group_name": group,
                    "event_type": "ORBITAL_CHANGE_CANDIDATE",
                    "severity": change["severity"],
                    "confidence": change["confidence"],
                    "summary": change["summary"],
                    "metrics": change["metrics"],
                    "status": "OPEN",
                    "source": "CelesTrak GP/OMM",
                })

        total += len(data)

    sb_upsert("orbital_elements", all_rows, "collected_at,group_name,norad_cat_id")
    sb_upsert("orbital_events", event_rows, "event_key")
    set_status(
        "celestrak_orbits",
        f"CelesTrak: {total} elements across {len(CELESTRAK_GROUPS)} groups; {len(event_rows)} candidates",
        total,
    )


# ============================================================
# HOUSEKEEPING
# ============================================================
def cleanup():
    for table, column in [
        ("space_weather", "collected_at"),
        ("gnss_cells", "collected_at"),
        ("gnss_aoi_snapshots", "observed_at"),
        ("gnss_events", "collected_at"),
        ("orbital_elements", "collected_at"),
        ("orbital_events", "detected_at"),
    ]:
        try:
            sb_delete_older_than(table, column, 30)
        except Exception as exc:
            print(f"cleanup warning {table}: {exc}")


def main():
    errors = []

    try:
        collect_noaa()
        print("NOAA OK")
    except Exception as exc:
        errors.append(f"NOAA: {exc}")
        print(errors[-1])

    if due("stanford_gnss", 55):
        try:
            collect_stanford_gnss()
            print("Stanford GNSS OK")
        except Exception as exc:
            errors.append(f"Stanford GNSS: {exc}")
            print(errors[-1])

    if due("celestrak_orbits", 125):
        try:
            collect_celestrak()
            print("CelesTrak OK")
        except Exception as exc:
            errors.append(f"CelesTrak: {exc}")
            print(errors[-1])

    try:
        cleanup()
    except Exception as exc:
        print(f"cleanup: {exc}")

    if errors:
        raise SystemExit(" | ".join(errors))


if __name__ == "__main__":
    main()
