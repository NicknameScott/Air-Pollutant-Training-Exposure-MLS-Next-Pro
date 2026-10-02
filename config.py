"""Central configuration (no network code here; safe to import from BOTH pipelines).
Any value can be overridden with an environment variable (e.g. EXPOSURE_DAYS=7) or a CLI flag."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_RAW = ROOT / "data" / "raw"            # unmodified API responses (audit trail)
DATA_CLEANED = ROOT / "data" / "cleaned"    # output of collect_data.py  (editable)
DATA_ANALYSIS = ROOT / "data" / "analysis"  # output of analyze_data.py  (editable)
OUT_TABLES, OUT_FIGURES, OUT_MODELS = (ROOT / "outputs" / d for d in ("tables", "figures", "models"))


def _env(name, default, cast=str):
    v = os.getenv(name)
    return default if v is None else cast(v)


SEASON = _env("SEASON", 2025, int)
SEASON_ID = _env("SEASON_ID", "MLS-SEA-0001K9")          # MLS id of the 2025 season

# ---- exposure scenario (ASSUMPTIONS - change freely; analysis needs no API calls) ---------------------
EXPOSURE_DAYS = _env("EXPOSURE_DAYS", 5, int)            # days before match; match day itself is EXCLUDED
AWAY_TRAVEL_DAYS = _env("AWAY_TRAVEL_DAYS", 2, int)      # last N pre-match days the AWAY team is assumed to be in the match region
HOME_TEAM_LOCATION_SOURCE = _env("HOME_TEAM_LOCATION_SOURCE", "team_home")   # or "stadium"
EXPOSURE_ORIENTATION = _env("EXPOSURE_ORIENTATION", "home_minus_away")       # or away_minus_home
EXPOSURE_STAT = _env("EXPOSURE_STAT", "avg")             # avg | max | min | sd | avg_dmax   (used for *_difference columns)
SENS_WINDOWS = [3, 5, 7]
SENS_TRAVEL_DAYS = [0, 1, 2, 3]                          # 0 = whole window in own home region
SUPPORTED_WINDOWS = (3, 4, 5, 7)
COLLECTION_BUFFER_DAYS = 10                              # collect environment this many days before the first match

# ---- statistics --------------------------------------------------------------------------------------
MIN_N = 30
VIF_THRESHOLD = 5.0                                      # predictors above this are not entered jointly
CORR_THRESHOLD = 0.8
THERMAL_CONTROL = _env("THERMAL_CONTROL", "heat_index")  # thermal covariate in adjusted pollutant models

# ---- collection: endpoints ----------------------------------------------------------------------------
STATS_API = "https://stats-api.mlssoccer.com"
MATCH_STATS_URL = STATS_API + "/statistics/clubs/matches/{match_id}"
SCHEDULE_URL = STATS_API + ("/matches/seasons/{season_id}?match_date[gte]={start}&match_date[lte]={end}"
                            "&per_page={per_page}&sort=planned_kickoff_time:asc,home_team_name:asc")
COMPETITION_NAME_CONTAINS = "MLS NEXT Pro"
SCHEDULE_START_MD, SCHEDULE_END_MD = "02-15", "12-15"
SCHEDULE_WINDOW_DAYS, SCHEDULE_PER_PAGE = 7, 120
MATCH_PAUSE_S = _env("MATCH_PAUSE_S", 0.4, float)
ASA_BASE = "https://app.americansocceranalysis.com/api/v1"
ASA_LEAGUE = "mlsnp"
AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WEATHER_URL = "https://archive-api.open-meteo.com/v1/archive"
WEATHER_MODEL = _env("WEATHER_MODEL", "era5_land")       # "" -> Open-Meteo best_match (less consistent over time)
ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
GEOCODE_MISSING_STADIUMS = _env("GEOCODE_MISSING_STADIUMS", "1") == "1"
API_PAUSE_S = _env("API_PAUSE_S", 1.0, float)
HTTP_TIMEOUT, HTTP_RETRIES = 60, 5

# MLS stats-endpoint key for each performance metric (verified against a real response)
STAT_FIELDS = {
    "passes_attempted": "passes_sum", "passes_completed": "passes_successful_sum", "fouls": "fouls_sum",
    "fouls_suffered": "fouls_suffered", "yellow_cards": "cards_yellow", "second_yellow_red_cards": "cards_yellow_red",
    "red_cards": "cards_red", "shots": "shots_at_goal_sum", "shots_on_target": "shots_on_target",
    "shots_faced": "shots_faced", "possession": "possession_ratio", "xg": "xG", "goals": "goals",
    "ball_control_phases": "ball_control_phases",
}
