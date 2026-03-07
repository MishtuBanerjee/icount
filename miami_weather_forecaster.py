#!/usr/bin/env python3
"""
Miami Weather Forecaster using NOAA National Weather Service data.

Fetches a 2-week window of historical observations from KMIA (Miami
International Airport) and a 3-day forecast from the NWS API, then
prints a formatted report.

Data source: https://api.weather.gov  (no API key required)
"""

import sys
import requests
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MIAMI_LAT = 25.7617
MIAMI_LON = -80.1918
MIAMI_STATION = "KMIA"          # Miami International Airport ASOS station
HISTORY_DAYS = 14
FORECAST_PERIODS = 6            # 3 days × 2 periods (day + night)

NWS_BASE = "https://api.weather.gov"
HEADERS = {
    "User-Agent": "MiamiWeatherForecaster/1.0 (github.com/MishtuBanerjee/icount)",
    "Accept": "application/geo+json",
}

# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------

def c_to_f(c):
    return round(c * 9 / 5 + 32, 1) if c is not None else None

def ms_to_mph(ms):
    return round(ms * 2.237, 1) if ms is not None else None

def mm_to_in(mm):
    return round(mm * 0.0394, 3) if mm is not None else 0.0

def pa_to_inhg(pa):
    return round(pa * 0.0002953, 2) if pa is not None else None

# ---------------------------------------------------------------------------
# NWS API calls
# ---------------------------------------------------------------------------

def _get(url, params=None, timeout=20):
    resp = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def get_gridpoint():
    """Return (gridId, gridX, gridY) for Miami coordinates."""
    data = _get(f"{NWS_BASE}/points/{MIAMI_LAT},{MIAMI_LON}")
    p = data["properties"]
    return p["gridId"], p["gridX"], p["gridY"]


def get_observations(station_id, days=HISTORY_DAYS):
    """Return raw observation GeoJSON features for the past *days* days."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    data = _get(
        f"{NWS_BASE}/stations/{station_id}/observations",
        params={
            "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end":   end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "limit": 500,
        },
        timeout=30,
    )
    return data.get("features", [])


def get_forecast(grid_id, grid_x, grid_y):
    """Return forecast period list from NWS gridpoint forecast."""
    data = _get(f"{NWS_BASE}/gridpoints/{grid_id}/{grid_x},{grid_y}/forecast")
    return data.get("properties", {}).get("periods", [])

# ---------------------------------------------------------------------------
# Data processing
# ---------------------------------------------------------------------------

def parse_observations(features):
    """
    Aggregate raw hourly observations into per-day buckets.
    Returns dict keyed by 'YYYY-MM-DD'.
    """
    daily = {}
    for feat in features:
        p = feat.get("properties", {})
        ts_str = p.get("timestamp")
        if not ts_str:
            continue

        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        day = ts.strftime("%Y-%m-%d")

        bucket = daily.setdefault(day, {
            "temps_f": [],
            "dewpoints_f": [],
            "humidities": [],
            "wind_speeds_mph": [],
            "precip_in": 0.0,
            "descriptions": [],
        })

        temp_c     = (p.get("temperature")            or {}).get("value")
        dew_c      = (p.get("dewpoint")               or {}).get("value")
        humidity   = (p.get("relativeHumidity")       or {}).get("value")
        wind_ms    = (p.get("windSpeed")              or {}).get("value")
        precip_mm  = (p.get("precipitationLastHour")  or {}).get("value")
        desc       = p.get("textDescription", "").strip()

        if temp_c   is not None: bucket["temps_f"].append(c_to_f(temp_c))
        if dew_c    is not None: bucket["dewpoints_f"].append(c_to_f(dew_c))
        if humidity is not None: bucket["humidities"].append(humidity)
        if wind_ms  is not None: bucket["wind_speeds_mph"].append(ms_to_mph(wind_ms))
        if precip_mm and precip_mm > 0:
            bucket["precip_in"] += mm_to_in(precip_mm)
        if desc:
            bucket["descriptions"].append(desc)

    return daily


def daily_summary(bucket):
    """Collapse a day's bucket into summary scalars."""
    temps  = bucket["temps_f"]
    winds  = bucket["wind_speeds_mph"]
    hums   = bucket["humidities"]
    descs  = bucket["descriptions"]

    def avg(lst): return round(sum(lst) / len(lst), 1) if lst else None

    most_common_desc = (
        max(set(descs), key=descs.count) if descs else "N/A"
    )

    return {
        "high_f":    round(max(temps), 1) if temps else None,
        "low_f":     round(min(temps), 1) if temps else None,
        "avg_f":     avg(temps),
        "humidity":  avg(hums),
        "wind_mph":  avg(winds),
        "precip_in": round(bucket["precip_in"], 2),
        "desc":      most_common_desc,
    }


def temperature_trend(summaries):
    """
    Least-squares slope of average daily temperature over the window.
    Returns degrees °F per day (positive = warming, negative = cooling).
    """
    dates = sorted(summaries)
    avgs  = [summaries[d]["avg_f"] for d in dates if summaries[d]["avg_f"] is not None]
    n = len(avgs)
    if n < 2:
        return None
    x_mean = (n - 1) / 2
    y_mean = sum(avgs) / n
    num = sum((i - x_mean) * (avgs[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return num / den if den else 0.0

# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

W = 76  # display width

def hr(char="="):
    return char * W


def _wrap(text, indent=18, width=W):
    """Simple word-wrap for detail lines."""
    words = text.split()
    lines, line = [], " " * indent
    for word in words:
        if len(line) + len(word) + 1 > width:
            lines.append(line)
            line = " " * indent + word + " "
        else:
            line += word + " "
    if line.strip():
        lines.append(line)
    return "\n".join(lines)


def display_historical(summaries):
    dates = sorted(summaries)
    print()
    print(hr())
    print(f"  MIAMI HISTORICAL WEATHER — PAST {len(dates)} DAYS  ({MIAMI_STATION})")
    print(hr())
    precip_hdr = 'Precip"'
    hdr = f"{'Date':<12}{'High°F':<9}{'Low°F':<8}{'Avg°F':<8}{'RH%':<7}{'Wind mph':<11}{precip_hdr:<9}Conditions"
    print(hdr)
    print(hr("-"))
    for day in dates:
        s = summaries[day]
        print(
            f"{day:<12}"
            f"{str(s['high_f']) if s['high_f'] is not None else 'N/A':<9}"
            f"{str(s['low_f'])  if s['low_f']  is not None else 'N/A':<8}"
            f"{str(s['avg_f'])  if s['avg_f']  is not None else 'N/A':<8}"
            f"{str(s['humidity']) + '%' if s['humidity'] is not None else 'N/A':<7}"
            f"{str(s['wind_mph']) if s['wind_mph'] is not None else 'N/A':<11}"
            f"{s['precip_in']:<9}"
            f"{s['desc'][:25]}"
        )


def display_two_week_summary(summaries):
    highs  = [s["high_f"]    for s in summaries.values() if s["high_f"]  is not None]
    lows   = [s["low_f"]     for s in summaries.values() if s["low_f"]   is not None]
    avgs   = [s["avg_f"]     for s in summaries.values() if s["avg_f"]   is not None]
    precip = sum(s["precip_in"] for s in summaries.values())
    slope  = temperature_trend(summaries)

    if slope is not None:
        if slope >  0.3:
            trend = f"Warming  (+{slope:.2f}°F/day)"
        elif slope < -0.3:
            trend = f"Cooling  ({slope:.2f}°F/day)"
        else:
            trend = f"Stable   ({slope:+.2f}°F/day)"
    else:
        trend = "N/A"

    print()
    print(hr())
    print("  2-WEEK SUMMARY")
    print(hr("-"))
    if highs:
        print(f"  Period High:        {max(highs):.1f}°F")
        print(f"  Period Low:         {min(lows):.1f}°F")
        print(f"  Average Daily Temp: {sum(avgs)/len(avgs):.1f}°F")
    print(f"  Total Precipitation:{precip:.2f} inches")
    print(f"  Temperature Trend:  {trend}")
    print(hr())


def display_forecast(periods):
    print()
    print(hr())
    print("  MIAMI 3-DAY FORECAST  (NOAA / NWS)")
    print(hr())
    for period in periods[:FORECAST_PERIODS]:
        name          = period.get("name", "")
        temp          = period.get("temperature")
        unit          = period.get("temperatureUnit", "F")
        wind_speed    = period.get("windSpeed", "N/A")
        wind_dir      = period.get("windDirection", "")
        short         = period.get("shortForecast", "N/A")
        detail        = period.get("detailedForecast", "")
        precip_obj    = period.get("probabilityOfPrecipitation") or {}
        precip_pct    = precip_obj.get("value")

        print(f"\n  {name}")
        print(f"  {'─' * (W - 4)}")
        print(f"  {'Temperature:':<17}{temp}°{unit}")
        if precip_pct is not None:
            print(f"  {'Precip chance:':<17}{precip_pct}%")
        print(f"  {'Wind:':<17}{wind_speed} {wind_dir}".rstrip())
        print(f"  {'Conditions:':<17}{short}")
        if detail:
            print(_wrap(detail, indent=19, width=W))
    print()
    print(hr())

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    now_str = datetime.now().strftime("%Y-%m-%d  %H:%M:%S  local")
    print()
    print(hr())
    print(f"  MIAMI WEATHER FORECASTER")
    print(f"  Data source : NOAA National Weather Service  (api.weather.gov)")
    print(f"  Report time : {now_str}")
    print(hr())

    # --- gridpoint --------------------------------------------------------
    print("\n  [1/3] Resolving NWS grid for Miami …")
    try:
        grid_id, grid_x, grid_y = get_gridpoint()
        print(f"        Office {grid_id}  grid ({grid_x}, {grid_y})")
    except Exception as exc:
        print(f"  ERROR: {exc}")
        sys.exit(1)

    # --- historical observations ------------------------------------------
    print(f"\n  [2/3] Fetching {HISTORY_DAYS}-day observations from {MIAMI_STATION} …")
    try:
        features  = get_observations(MIAMI_STATION, days=HISTORY_DAYS)
        raw_daily = parse_observations(features)
        summaries = {day: daily_summary(raw_daily[day]) for day in sorted(raw_daily)}
        print(f"        {len(features)} hourly records  →  {len(summaries)} days")
    except Exception as exc:
        print(f"  ERROR: {exc}")
        sys.exit(1)

    display_historical(summaries)
    display_two_week_summary(summaries)

    # --- 3-day forecast ---------------------------------------------------
    print(f"\n  [3/3] Fetching 3-day NWS forecast …")
    try:
        periods = get_forecast(grid_id, grid_x, grid_y)
        print(f"        {len(periods)} forecast periods available")
    except Exception as exc:
        print(f"  ERROR: {exc}")
        sys.exit(1)

    display_forecast(periods)
    print("  Source: NOAA National Weather Service — api.weather.gov\n")


if __name__ == "__main__":
    main()
