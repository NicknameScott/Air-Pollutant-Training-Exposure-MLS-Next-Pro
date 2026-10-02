"""PIPELINE B - DATA ANALYSIS (never touches the network; imports nothing from src/collection).

    python analyze_data.py                  # analyse data/analysis/analysis_dataset.csv AS IT IS ON DISK (your edits are used).
                                            # If it does not exist yet, it is built first from data/cleaned/.
    python analyze_data.py --rebuild        # rebuild daily_exposure.csv, match_environment.csv, analysis_dataset.csv from
                                            # data/cleaned/ (refuses to overwrite hand-edited files)
    python analyze_data.py --rebuild --overwrite-edited   # ...replace them anyway (timestamped backups are made)
Scenario flags: --window 5 --away-travel-days 2 --orientation away_minus_home --stat avg
Extras: --extra-exposure my_col_difference --extra-outcome my_col --mixed --no-sensitivity --no-figures

Sensitivity (windows x travel x exposures) is rebuilt from data/cleaned/ for the match_ids and OUTCOME values present in
your analysis_dataset.csv, so removed rows / edited outcomes carry through; edits to exposure columns affect only the primary analysis."""
import argparse
import logging
import pandas as pd
import config
from src.common import io_utils
from src.common.variables import ENV_VARS, OUTCOMES
from src.analysis import cleaning, exposure, performance, statistics as st, visualization as viz


def parse():
    p = argparse.ArgumentParser()
    p.add_argument("--rebuild", action="store_true")
    p.add_argument("--overwrite-edited", action="store_true")
    p.add_argument("--window", type=int); p.add_argument("--away-travel-days", type=int)
    p.add_argument("--orientation", choices=["home_minus_away", "away_minus_home"])
    p.add_argument("--stat", choices=["avg", "max", "min", "sd", "avg_dmax"])
    p.add_argument("--extra-exposure", action="append", default=[]); p.add_argument("--extra-outcome", action="append", default=[])
    p.add_argument("--mixed", action="store_true"); p.add_argument("--no-sensitivity", action="store_true")
    p.add_argument("--no-figures", action="store_true")
    return p.parse_args()


def build_datasets(tables, force=False) -> bool:
    """cleaned CSVs -> daily_exposure.csv -> match_environment.csv -> analysis_dataset.csv (primary scenario)."""
    m = tables["matches"]
    perf = performance.add_performance_differences(tables["performance"])
    daily = exposure.build_daily_exposure(m, tables["teams"], tables["stadiums"], tables["daily_environment"],
                                          config.EXPOSURE_DAYS, config.AWAY_TRAVEL_DAYS)
    menv = exposure.aggregate_team_match(daily, tables["teams"], tables["stadiums"], m)
    wide = exposure.to_match_rows(menv)
    base = perf.drop(columns=[c for c in ("match_date",) if c in perf]).merge(
        m[["match_id", "match_date", "stadium_id"]], on="match_id", how="left")
    ds = base.merge(wide, on="match_id", how="left")
    ds["exposure_window_days"], ds["away_travel_days"] = config.EXPOSURE_DAYS, config.AWAY_TRAVEL_DAYS
    ds["exposure_stat"], ds["exposure_orientation"] = config.EXPOSURE_STAT, config.EXPOSURE_ORIENTATION
    d = config.DATA_ANALYSIS
    d_out = daily.copy()
    for c in ("match_date", "exposure_date"):
        d_out[c] = pd.to_datetime(d_out[c]).dt.date
    ok = [io_utils.write_csv_protected(d_out, d / "daily_exposure.csv", force),
          io_utils.write_csv_protected(menv, d / "match_environment.csv", force),
          io_utils.write_csv_protected(ds.assign(match_date=pd.to_datetime(ds.match_date).dt.date), d / "analysis_dataset.csv", force)]
    return all(ok)


def main():
    a = parse()
    for k, attr in (("window", "EXPOSURE_DAYS"), ("away_travel_days", "AWAY_TRAVEL_DAYS"), ("orientation", "EXPOSURE_ORIENTATION"), ("stat", "EXPOSURE_STAT")):
        if getattr(a, k) is not None:
            setattr(config, attr, getattr(a, k))
    if config.EXPOSURE_DAYS not in config.SUPPORTED_WINDOWS:
        raise SystemExit(f"--window must be one of {config.SUPPORTED_WINDOWS}")
    for d in (config.DATA_ANALYSIS, config.OUT_TABLES, config.OUT_FIGURES, config.OUT_MODELS):
        d.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    log = logging.getLogger("analysis")
    ds_path = config.DATA_ANALYSIS / "analysis_dataset.csv"

    tables = None
    if a.rebuild or not ds_path.exists():
        tables = cleaning.load_cleaned()
        log.info("building exposure + analysis datasets from data/cleaned/ (window=%d, away travel=%d)", config.EXPOSURE_DAYS, config.AWAY_TRAVEL_DAYS)
        if not build_datasets(tables, a.overwrite_edited):
            log.warning("some files were protected; continuing with the versions on disk")
    else:
        log.info("using existing %s (not rebuilt; pass --rebuild to regenerate)", ds_path.name)
    df = pd.read_csv(ds_path)
    df["match_date"] = pd.to_datetime(df["match_date"])
    meta = dict(n_matches=len(df), window=int(df.get("exposure_window_days", pd.Series([config.EXPOSURE_DAYS])).iloc[0]),
                travel=int(df.get("away_travel_days", pd.Series([config.AWAY_TRAVEL_DAYS])).iloc[0]),
                orientation=str(df.get("exposure_orientation", pd.Series([config.EXPOSURE_ORIENTATION])).iloc[0]),
                stat=str(df.get("exposure_stat", pd.Series([config.EXPOSURE_STAT])).iloc[0]))
    # performance differences are (re)computed so hand-added/edited home_/away_ columns flow through
    for _, (suffix, diff, _) in OUTCOMES.items():
        if f"home_{suffix}" in df and f"away_{suffix}" in df:
            df[diff] = df[f"home_{suffix}"] - df[f"away_{suffix}"]

    # ---- validation, correlations, VIF --------------------------------------------------------------------
    cleaning.data_quality_report(tables or _try_load(), df)
    exps = st.exposure_columns(df, a.extra_exposure)
    df[exps].corr(method="pearson").to_csv(config.OUT_TABLES / "exposure_correlations_pearson.csv")
    df[exps].corr(method="spearman").to_csv(config.OUT_TABLES / "exposure_correlations_spearman.csv")
    pol = [f"{p}_difference" for p in ("pm25", "pm10", "no2", "o3", "us_aqi") if f"{p}_difference" in df]
    thermal = [f"{v}_difference" for v in ("temperature", "humidity", "temp_humidity_product", "heat_index", "wet_bulb", "apparent_temp") if f"{v}_difference" in df]
    vif_all = st.vif_table(df, [c for c in pol + thermal + ["elevation_gain_difference"] if c in df and df[c].notna().sum() > config.MIN_N]) if exps else pd.DataFrame()
    vif_air = st.vif_table(df, [c for c in pol if c in df])
    vif_all.to_csv(config.OUT_TABLES / "vif_all_exposures.csv", index=False); vif_air.to_csv(config.OUT_TABLES / "vif_air_exposures.csv", index=False)

    # ---- models -----------------------------------------------------------------------------------------------
    res, skipped = st.run_primary(df, meta["window"], f"{meta['travel']}_day(s)_in_match_region" if meta["travel"] else "all_home_region",
                                  a.extra_exposure, a.extra_outcome, a.mixed)
    res.to_csv(config.OUT_TABLES / "analysis_results.csv", index=False)
    skipped.to_csv(config.OUT_TABLES / "model_selection_notes.csv", index=False)

    sens = None
    if not a.no_sensitivity:
        try:
            tables = tables or cleaning.load_cleaned()
            keep = set(df.match_id)
            m = tables["matches"][tables["matches"].match_id.isin(keep)]
            build = lambda w, t: exposure.scenario_differences(m, tables["teams"], tables["stadiums"], tables["daily_environment"], w, t, meta["stat"], meta["orientation"])
            sens = st.run_sensitivity(df, build, config.SENS_WINDOWS, config.SENS_TRAVEL_DAYS, list(ENV_VARS), a.extra_outcome)
            el = [r for x in ("elevation_difference", "elevation_gain_difference") if x in df for oname, y in st.outcome_columns(df, a.extra_outcome).items()
                  for r in st.fit_single(df, oname, y, x, "n/a", "n/a (geographic constant)", models=("ols_team_fe",))]
            sens = pd.concat([sens, pd.DataFrame(el, columns=st.RES_COLS)], ignore_index=True)
            sens.to_csv(config.OUT_TABLES / "sensitivity_results.csv", index=False)
        except SystemExit as e:
            log.warning("sensitivity skipped: %s", e)
    st.write_summary(res, sens, skipped, meta, config.OUT_TABLES / "analysis_summary.txt")

    # ---- figures ------------------------------------------------------------------------------------------------
    if not a.no_figures:
        stat = meta["stat"]
        viz.distributions(df, stat)
        viz.corr_matrix(df, [f"home_{p}_{stat}" for p in ("pm25", "pm10", "no2", "o3", "us_aqi")], "fig_pollutant_correlation_matrix", "Pollutant correlations (home-team window averages, Spearman)")
        viz.corr_matrix(df, exps, "fig_exposure_difference_correlation_matrix", "Exposure-difference correlations (Spearman)")
        viz.env_relationships(df, stat)
        for x, y in viz.PAIRS + [("elevation", "xg")]:
            viz.outcome_scatter(df, "elevation_difference" if x == "elevation" else x, y)
        viz.vif_plot(vif_all, "fig_vif_all_exposures", "VIF of candidate exposure differences")
        viz.forest(res); viz.sensitivity_heatmaps(sens)
    log.info("Done. Tables -> %s ; figures -> %s", config.OUT_TABLES, config.OUT_FIGURES)


def _try_load():
    try:
        return cleaning.load_cleaned()
    except SystemExit:
        raise


if __name__ == "__main__":
    main()
