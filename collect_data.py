"""PIPELINE A - DATA COLLECTION (the ONLY code that touches the network).

    python collect_data.py                   # everything
    python collect_data.py --steps mls,locations,elevation,asa,environment
    python collect_data.py --check-sources   # probe each source, save samples to data/raw/discovery/
    python collect_data.py --refresh         # ignore raw caches
    python collect_data.py --overwrite-edited  # allow replacing hand-edited cleaned CSVs (backups are made)

Writes to data/cleaned/: matches.csv performance.csv team_locations.csv stadiums.csv elevation.csv
daily_environment.csv asa_team_crosswalk.csv collection_quality_report.csv. Does NOT run any statistics."""
import argparse
import logging
import sys
import pandas as pd
import config
from src.common import io_utils


def parse():
    p = argparse.ArgumentParser()
    p.add_argument("--steps", default="mls,locations,elevation,asa,environment")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--overwrite-edited", action="store_true")
    p.add_argument("--check-sources", action="store_true")
    p.add_argument("--season", type=int)
    return p.parse_args()


def check_sources():
    from src.collection import soccer_api, weather, air_quality, elevation
    from src.collection.http_util import get_json
    out = config.DATA_RAW / "discovery"; out.mkdir(parents=True, exist_ok=True)
    tests = {
        "asa_teams": (f"{config.ASA_BASE}/{config.ASA_LEAGUE}/teams", {}),
        "asa_games": (f"{config.ASA_BASE}/{config.ASA_LEAGUE}/games", {"season_name": str(config.SEASON)}),
        "asa_xgoals": (f"{config.ASA_BASE}/{config.ASA_LEAGUE}/games/xgoals", {"season_name": str(config.SEASON)}),
        "openmeteo_weather": (config.WEATHER_URL, {"latitude": 33.75, "longitude": -84.39, "start_date": f"{config.SEASON}-06-01",
                              "end_date": f"{config.SEASON}-06-02", "hourly": "temperature_2m,relative_humidity_2m", "timezone": "auto",
                              **({"models": config.WEATHER_MODEL} if config.WEATHER_MODEL else {})}),
        "openmeteo_air": (config.AQ_URL, {"latitude": 33.75, "longitude": -84.39, "start_date": f"{config.SEASON}-06-01",
                          "end_date": f"{config.SEASON}-06-02", "hourly": "us_aqi,pm2_5,ozone", "timezone": "auto"}),
        "openmeteo_elevation": (config.ELEVATION_URL, {"latitude": "33.75,39.74", "longitude": "-84.39,-104.99"}),
    }
    import json
    for name, (url, params) in tests.items():
        try:
            d = get_json(url, params, allow_404=True)
            (out / f"{name}.json").write_text(json.dumps(d)[:300000])
            if d is None:
                print(f"{name}: 404 (endpoint not found)")
            else:
                df = pd.json_normalize(d if isinstance(d, list) else [d])
                print(f"{name}: OK, {len(d) if isinstance(d, list) else 1} record(s); columns: {list(df.columns)[:14]}")
        except Exception as e:
            print(f"{name}: FAILED - {str(e)[:200]}")
    print(f"Samples saved to {out}")


def main():
    a = parse()
    if a.season:
        config.SEASON = a.season
    for d in (config.DATA_RAW, config.DATA_CLEANED):
        d.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(config.DATA_RAW / "collection.log")])
    log = logging.getLogger("collect")
    if a.check_sources:
        check_sources(); return
    steps = set(a.steps.split(","))
    force = a.overwrite_edited
    from src.collection import mls_next_pro, locations, elevation, soccer_api, environment, quality
    C = config.DATA_CLEANED
    w = lambda df, name: io_utils.write_csv_protected(df, C / name, force)

    # 1. MLS Next Pro matches + performance (raw JSON cached; cleaned tables need team time zones -> uses team table)
    raw_matches = None
    if "mls" in steps:
        raw_matches = mls_next_pro.collect(a.refresh)
        raw_matches.to_pickle(config.DATA_RAW / "mls_matches_parsed.pkl")
    elif (config.DATA_RAW / "mls_matches_parsed.pkl").exists():
        raw_matches = pd.read_pickle(config.DATA_RAW / "mls_matches_parsed.pkl")
    # 2. locations (editable tables; only blanks/new rows are filled)
    if "locations" in steps and raw_matches is not None:
        teams = locations.sync_teams(raw_matches)
        stadiums = locations.sync_stadiums(raw_matches)
    else:
        teams, stadiums = locations.load_teams(), pd.read_csv(locations.STADIUMS_CSV)
    # 3. elevation (Open-Meteo Elevation API, Copernicus GLO-90)
    if "elevation" in steps:
        teams = elevation.fill_elevations(teams, locations.TEAMS_CSV)
        stadiums = elevation.fill_elevations(stadiums, locations.STADIUMS_CSV)
        w(elevation.elevation_table(teams, stadiums), "elevation.csv")
    # matches.csv / performance.csv
    if raw_matches is not None:
        matches, perf = mls_next_pro.to_tables(raw_matches, teams)
        # 4. xG from ASA (optional, best effort)
        if "asa" in steps:
            try:
                asa, asa_teams = soccer_api.fetch_asa(a.refresh)
                if not asa.empty:
                    cw = soccer_api.build_crosswalk(asa_teams, teams)
                    perf = soccer_api.merge_xg(perf, matches, asa, cw)
            except Exception as e:
                log.warning("ASA step failed (xG left missing): %s", str(e)[:300])
        w(matches, "matches.csv"); w(perf, "performance.csv")
    else:
        matches = pd.read_csv(C / "matches.csv"); perf = pd.read_csv(C / "performance.csv")
    # 5. environment (air quality + weather) for every team home location AND every stadium
    if "environment" in steps:
        coords = list(zip(teams.latitude, teams.longitude)) + list(zip(stadiums.latitude, stadiums.longitude))
        first = pd.to_datetime(matches.match_date).min() - pd.Timedelta(days=config.COLLECTION_BUFFER_DAYS)
        last = pd.to_datetime(matches.match_date).max()
        daily = environment.collect_daily(coords, first.date().isoformat(), last.date().isoformat())
        w(daily, "daily_environment.csv")
    else:
        daily = pd.read_csv(C / "daily_environment.csv")
    n_missing = int(raw_matches["stats_missing_for_scheduled"].iloc[0]) if raw_matches is not None else 0
    quality.collection_quality(matches, perf, teams, stadiums, daily, n_stats_missing=n_missing) \
        .to_csv(C / "collection_quality_report.csv", index=False)
    from src.common.data_dictionary import write_dictionary
    write_dictionary(config.ROOT / "data" / "data_dictionary.csv", force)
    log.info("Collection finished. Inspect/edit files in %s, then run: python analyze_data.py", C)


if __name__ == "__main__":
    main()
