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
import numpy as np
from catboost import CatBoostRegressor
import matplotlib
matplotlib.use("Agg")           # headless – saves to file instead of displaying
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns

sns.set_theme(
    style="ticks",
    rc={
        "axes.facecolor":  "white",
        "figure.facecolor": "white",
        "axes.edgecolor":  "#333333",
        "axes.linewidth":  0.8,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "xtick.major.size": 5,
        "ytick.major.size": 5,
        "xtick.minor.size": 3,
        "ytick.minor.size": 3,
        "xtick.major.width": 0.8,
        "ytick.major.width": 0.8,
        "axes.grid":       True,
        "grid.color":      "#e5e5e5",
        "grid.linewidth":  0.6,
    },
)
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


def get_hourly_forecast(grid_id, grid_x, grid_y):
    """Return hourly forecast period list from NWS gridpoint hourly forecast."""
    data = _get(f"{NWS_BASE}/gridpoints/{grid_id}/{grid_x},{grid_y}/forecast/hourly")
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
# Tree model: hourly observations → RandomForest temperature forecast
# ---------------------------------------------------------------------------

FEATURE_KEYS = ["hour", "day_of_year", "humidity", "wind_mph", "dewpoint_f"]
TRAIN_DAYS   = 11   # hold out last 3 days of the 14-day window as test set


def parse_hourly_observations(features):
    """
    Convert raw NWS observation GeoJSON features into a flat list of hourly
    records suitable for ML. Records with missing temperature are dropped.
    Sorted chronologically.
    """
    records = []
    for feat in features:
        p      = feat.get("properties", {})
        ts_str = p.get("timestamp")
        if not ts_str:
            continue

        ts       = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        temp_c   = (p.get("temperature")       or {}).get("value")
        dew_c    = (p.get("dewpoint")          or {}).get("value")
        humidity = (p.get("relativeHumidity")  or {}).get("value")
        wind_ms  = (p.get("windSpeed")         or {}).get("value")

        if temp_c is None:
            continue

        records.append({
            "timestamp":  ts,
            "hour":       ts.hour,
            "day_of_year": ts.timetuple().tm_yday,
            "temp_f":     c_to_f(temp_c),
            "dewpoint_f": c_to_f(dew_c)        if dew_c    is not None else np.nan,
            "humidity":   humidity              if humidity is not None else np.nan,
            "wind_mph":   ms_to_mph(wind_ms)    if wind_ms  is not None else np.nan,
        })

    records.sort(key=lambda r: r["timestamp"])
    return records


def _records_to_xy(records):
    X = np.array([[r[k] if not (isinstance(r[k], float) and np.isnan(r[k])) else 0.0
                   for k in FEATURE_KEYS]
                  for r in records], dtype=float)
    y = np.array([r["temp_f"] for r in records], dtype=float)
    return X, y


def build_tree_model(hourly_records):
    """
    Split the 14-day hourly observations into train (first TRAIN_DAYS days)
    and test (last 3 days).  Fit a CatBoostRegressor on the training
    portion and predict on the test portion.

    Returns (timestamps, actuals, predictions) — parallel lists for the
    test window — or empty lists if data is insufficient.
    """
    all_dates = sorted({r["timestamp"].strftime("%Y-%m-%d") for r in hourly_records})
    if len(all_dates) < 4:
        return [], [], []

    # Last 3 calendar days are the test set
    test_start_str = all_dates[-3]
    test_start = datetime.strptime(test_start_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    train = [r for r in hourly_records if r["timestamp"] <  test_start]
    test  = [r for r in hourly_records if r["timestamp"] >= test_start]

    if len(train) < 10 or len(test) < 1:
        return [], [], []

    X_train, y_train = _records_to_xy(train)
    X_test,  y_test  = _records_to_xy(test)
    ts_test = [r["timestamp"] for r in test]

    model = CatBoostRegressor(
        iterations=500,
        learning_rate=0.05,
        depth=6,
        loss_function="RMSE",
        random_seed=42,
        verbose=0,
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    return ts_test, y_test.tolist(), y_pred.tolist()


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
# Forecast-error chart  (tree model predictions vs actual observations)
# ---------------------------------------------------------------------------

def chart_forecast_errors(
    timestamps, actuals, predictions,
    output_path="miami_forecast_error_chart.png",
):
    """
    Two-panel chart:
      Top    – actual °F vs tree-model predicted °F over the 3-day test window
      Bottom – hourly error bars (predicted − actual) with MAE / RMSE annotation
    """
    if not timestamps:
        print("  WARNING: no error data to plot; skipping error chart.")
        return

    miami_tz = timezone(timedelta(hours=-5))
    ts_local = [t.astimezone(miami_tz) for t in timestamps]

    errors = [p - a for p, a in zip(predictions, actuals)]
    mae    = sum(abs(e) for e in errors) / len(errors)
    rmse   = (sum(e ** 2 for e in errors) / len(errors)) ** 0.5
    bias   = sum(errors) / len(errors)

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(13, 8), sharex=True,
        gridspec_kw={"height_ratios": [2, 1]},
    )

    # ── Top: actual vs predicted ──────────────────────────────────────────
    sns.lineplot(x=ts_local, y=actuals,     ax=ax1, color="#e74c3c",
                 linewidth=2, label="Actual °F")
    sns.lineplot(x=ts_local, y=predictions, ax=ax1, color="#2980b9",
                 linewidth=2, linestyle="--", label="CatBoost predicted °F")
    ax1.fill_between(ts_local, actuals, predictions,
                     color="#2980b9", alpha=0.10, label="Error band")
    ax1.set_ylabel("Temperature (°F)", fontsize=9)
    ax1.tick_params(labelsize=8)
    ax1.legend(loc="upper right", fontsize=8)
    ax1.set_title(
        "Miami 3-Day Forecast Error  —  CatBoost Tree Model vs Actual Observations",
        fontsize=11, pad=10,
    )

    # ── Bottom: error bars ────────────────────────────────────────────────
    bar_colors = ["#e74c3c" if e > 0 else "#3498db" for e in errors]
    ax2.bar(ts_local, errors, width=timedelta(hours=0.8),
            color=bar_colors, alpha=0.85, label="Error (pred − actual)")
    ax2.axhline(0, color="#7f8c8d", linewidth=0.9, linestyle="-")
    ax2.set_ylabel("Error (°F)", fontsize=9)
    ax2.tick_params(labelsize=8)
    ax2.legend(loc="upper right", fontsize=8)

    # Metrics as x-axis label
    ax2.set_xlabel(
        f"MAE = {mae:.2f}°F    RMSE = {rmse:.2f}°F    Bias = {bias:+.2f}°F"
        f"    (red = over-predicted, blue = under-predicted)",
        fontsize=8.5,
    )

    # ── Shared x-axis ─────────────────────────────────────────────────────
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%a\n%-I %p", tz=miami_tz))
    ax2.xaxis.set_major_locator(mdates.HourLocator(byhour=[0, 6, 12, 18], tz=miami_tz))
    ax2.tick_params(axis="x", labelsize=7.5)

    # Day-boundary verticals
    if ts_local:
        day0 = ts_local[0].replace(hour=0, minute=0, second=0, microsecond=0)
        for d in range(1, 4):
            boundary = day0 + timedelta(days=d)
            for ax in (ax1, ax2):
                ax.axvline(boundary, color="#bdc3c7", linewidth=0.8, linestyle=":")

    for ax in (ax1, ax2):
        ax.minorticks_on()
        ax.tick_params(which="minor", length=3, width=0.6)
        sns.despine(ax=ax, top=True, right=True)

    fig.autofmt_xdate(rotation=0, ha="center")
    plt.tight_layout(h_pad=0.4)
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Chart saved → {output_path}")
    print(f"  Tree model  MAE={mae:.2f}°F  RMSE={rmse:.2f}°F  Bias={bias:+.2f}°F")


# ---------------------------------------------------------------------------
# Hourly chart
# ---------------------------------------------------------------------------

def parse_hourly_periods(periods, start_dt):
    """
    Filter hourly NWS forecast periods to those at or after *start_dt*
    and within 3 days of it.  Returns parallel lists (timestamps, temps_f,
    precip_pct, wind_mph).
    """
    end_dt = start_dt + timedelta(days=3)
    timestamps, temps, precips, winds = [], [], [], []

    for p in periods:
        ts_str = p.get("startTime", "")
        if not ts_str:
            continue
        ts = datetime.fromisoformat(ts_str)
        # Normalise to UTC-aware for comparison
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts < start_dt or ts >= end_dt:
            continue

        temp = p.get("temperature")
        if p.get("temperatureUnit", "F") == "C" and temp is not None:
            temp = c_to_f(temp)

        precip_obj = p.get("probabilityOfPrecipitation") or {}
        precip = precip_obj.get("value") or 0

        wind_str = p.get("windSpeed", "0 mph").split()[0]
        try:
            wind = float(wind_str)
        except ValueError:
            wind = 0.0

        timestamps.append(ts)
        temps.append(temp)
        precips.append(precip)
        winds.append(wind)

    return timestamps, temps, precips, winds


def chart_forecast_hourly(hourly_periods, output_path="miami_forecast_chart.png"):
    """
    Build a two-panel seaborn/matplotlib chart of the 3-day hourly forecast
    starting at 1 AM today (local Miami time, UTC-5 / ET).

    Top panel:  Temperature °F line
    Bottom panel: Precipitation probability % bars + Wind speed mph line
    """
    # Miami is Eastern Time (UTC-5 standard, UTC-4 DST).  Use a fixed
    # UTC-5 offset as a simple approximation; the NWS timestamps carry
    # their own offset so comparison is still correct.
    miami_tz = timezone(timedelta(hours=-5))
    today_1am = datetime.now(miami_tz).replace(
        hour=1, minute=0, second=0, microsecond=0
    )
    # Convert to UTC for consistent comparison with NWS timestamps
    start_utc = today_1am.astimezone(timezone.utc)

    timestamps, temps, precips, winds = parse_hourly_periods(hourly_periods, start_utc)

    if not timestamps:
        print("  WARNING: no hourly data found for the requested window; skipping chart.")
        return

    # Convert to local Miami time for display
    ts_local = [t.astimezone(miami_tz) for t in timestamps]

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(13, 7), sharex=True,
        gridspec_kw={"height_ratios": [3, 2]},
    )

    # ── Top panel: Temperature ────────────────────────────────────────────
    sns.lineplot(x=ts_local, y=temps, ax=ax1, color="#e74c3c",
                 linewidth=2, markers=True, marker="o", markersize=3,
                 label="Temp °F")
    ax1.fill_between(ts_local, temps, min(t for t in temps if t is not None) - 2,
                     color="#e74c3c", alpha=0.12)

    # Annotate high/low
    valid = [(t, v) for t, v in zip(ts_local, temps) if v is not None]
    if valid:
        max_ts, max_t = max(valid, key=lambda x: x[1])
        min_ts, min_t = min(valid, key=lambda x: x[1])
        ax1.annotate(f"{max_t:.0f}°F", xy=(max_ts, max_t),
                     xytext=(0, 8), textcoords="offset points",
                     color="#c0392b", fontsize=8, ha="center", fontweight="bold")
        ax1.annotate(f"{min_t:.0f}°F", xy=(min_ts, min_t),
                     xytext=(0, -14), textcoords="offset points",
                     color="#2980b9", fontsize=8, ha="center", fontweight="bold")

    ax1.set_ylabel("Temperature (°F)", fontsize=9)
    ax1.tick_params(labelsize=8)
    ax1.legend(loc="upper right", fontsize=8)
    ax1.set_title(
        f"Miami 3-Day Hourly Forecast  —  from 1 AM {today_1am.strftime('%b %d, %Y')}",
        fontsize=12, pad=10,
    )

    # ── Bottom panel: Precip probability bars + wind line ─────────────────
    ax2.bar(ts_local, precips, width=timedelta(hours=0.8),
            color="#2980b9", alpha=0.65, label="Precip prob %")
    ax2.set_ylabel("Precip prob (%)", fontsize=9)
    ax2.set_ylim(0, 105)
    ax2.tick_params(axis="y", labelsize=8)

    ax2b = ax2.twinx()
    sns.lineplot(x=ts_local, y=winds, ax=ax2b, color="#27ae60",
                 linewidth=1.5, linestyle="--", marker="s", markersize=2,
                 label="Wind mph")
    ax2b.set_ylabel("Wind (mph)", color="#27ae60", fontsize=9)
    ax2b.tick_params(axis="y", labelsize=8, colors="#27ae60")

    # Combined legend for bottom panel
    lines1, labels1 = ax2.get_legend_handles_labels()
    lines2, labels2 = ax2b.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, labels1 + labels2,
               loc="upper right", fontsize=8)

    # ── Shared x-axis: day separators + formatting ─────────────────────────
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%a\n%-I %p", tz=miami_tz))
    ax2.xaxis.set_major_locator(mdates.HourLocator(byhour=[0, 6, 12, 18], tz=miami_tz))
    ax2.tick_params(axis="x", labelsize=7.5)

    # Vertical day-boundary lines
    day_start = today_1am.replace(hour=0)
    for d in range(1, 4):
        boundary = day_start + timedelta(days=d)
        for ax in (ax1, ax2):
            ax.axvline(boundary, color="#bdc3c7", linewidth=0.8, linestyle=":")

    for ax in (ax1, ax2):
        ax.minorticks_on()
        ax.tick_params(which="minor", length=3, width=0.6)
        sns.despine(ax=ax, top=True, right=True)
    sns.despine(ax=ax2b, top=True, right=False)  # keep right spine for twin axis

    fig.autofmt_xdate(rotation=0, ha="center")
    plt.tight_layout(h_pad=0.4)
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Chart saved → {output_path}")


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

    # --- tree model: train on first 11 days, evaluate on last 3 ----------
    print(f"\n  [2b/3] Building CatBoost tree model & evaluating 3-day forecast error …")
    try:
        hourly_records = parse_hourly_observations(features)
        ts_test, actuals, predictions = build_tree_model(hourly_records)
        if ts_test:
            print(f"        {len(hourly_records)} hourly obs  →  "
                  f"test window {len(ts_test)} hours")
            chart_forecast_errors(ts_test, actuals, predictions)
        else:
            print("        Insufficient data for tree model evaluation.")
    except Exception as exc:
        print(f"  WARNING: tree model error — {exc}")

    # --- 3-day forecast ---------------------------------------------------
    print(f"\n  [3/3] Fetching 3-day NWS forecast …")
    try:
        periods = get_forecast(grid_id, grid_x, grid_y)
        print(f"        {len(periods)} forecast periods available")
    except Exception as exc:
        print(f"  ERROR: {exc}")
        sys.exit(1)

    display_forecast(periods)

    # --- hourly chart -----------------------------------------------------
    print(f"\n  [4/4] Fetching hourly forecast for chart …")
    try:
        hourly = get_hourly_forecast(grid_id, grid_x, grid_y)
        print(f"        {len(hourly)} hourly periods available")
        chart_forecast_hourly(hourly)
    except Exception as exc:
        print(f"  WARNING: chart not generated — {exc}")

    print("  Source: NOAA National Weather Service — api.weather.gov\n")


if __name__ == "__main__":
    main()
