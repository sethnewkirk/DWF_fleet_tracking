"""
Process GFW fishing effort data into analysis-ready format.

Pipeline:
  1. Load raw GFW effort CSVs (from 4Wings API, already filtered to CHN)
  2. Normalize column names
  3. Exclude activity inside China's domestic waters (lat 18-42, lon 105-130)
  4. Aggregate to 0.1-degree grid by year
  5. Save as Parquet for fast loading
  6. Process AIS gap events and encounters into mappable DataFrames
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config


# Column name mapping from GFW 4Wings API to internal names
COLUMN_MAP = {
    "Lat": "lat",
    "Lon": "lon",
    "Time Range": "time_range",
    "Flag": "flag",
    "Geartype": "geartype",
    "Vessel IDs": "vessel_count",
    "Apparent Fishing Hours": "fishing_hours",
    # Also handle bulk download column names
    "cell_ll_lat": "lat",
    "cell_ll_lon": "lon",
}


def load_raw_effort() -> pd.DataFrame:
    """Load all raw effort CSVs from the GFW effort directory."""
    csv_files = sorted(config.GFW_EFFORT_DIR.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(
            f"No CSV files found in {config.GFW_EFFORT_DIR}. "
            "Run download_gfw_effort.py first."
        )

    frames = []
    for f in csv_files:
        print(f"  Loading {f.name}...")
        df = pd.read_csv(f)
        # Normalize column names
        df = df.rename(columns=COLUMN_MAP)
        # Filter to CHN if needed (bulk data)
        if "flag" in df.columns:
            before = len(df)
            df = df[df["flag"] == config.TARGET_FLAG]
            if before != len(df):
                print(f"    Filtered {before} -> {len(df)} rows (CHN only)")
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    print(f"  Total: {len(combined):,} rows across {len(csv_files)} files")
    return combined


def extract_year(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure the dataframe has a 'year' column."""
    if "year" in df.columns:
        return df

    # 4Wings API returns time_range as "YYYY-MM" for monthly resolution
    if "time_range" in df.columns:
        df["year"] = df["time_range"].str[:4].astype(int)
        return df

    for date_col in ["date", "start_date"]:
        if date_col in df.columns:
            df["year"] = pd.to_datetime(df[date_col]).dt.year
            return df

    print("  WARNING: No date column found. Cannot assign year.")
    return df


def exclude_domestic_waters(df: pd.DataFrame) -> pd.DataFrame:
    """
    Exclude fishing effort that falls within China's domestic waters.

    Uses a conservative bounding box for China's coastal EEZ:
    lat 18-42, lon 105-130 (covers Bohai, Yellow, East China, South China seas).

    This is a fast geometric filter. For precise EEZ-based filtering,
    use filter_effort_outside_eez() with Marine Regions data.
    """
    domestic = (
        (df["lat"] >= 18) & (df["lat"] <= 42) &
        (df["lon"] >= 105) & (df["lon"] <= 130)
    )
    excluded = domestic.sum()
    print(f"    Excluded {excluded:,} domestic rows (China coastal waters)")
    return df[~domestic].copy()


def aggregate_effort(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate fishing effort by grid cell, year, and geartype."""
    # Data from 4Wings at LOW resolution is already on 0.1-degree grid
    group_cols = ["lat", "lon"]
    if "year" in df.columns:
        group_cols.append("year")
    if "geartype" in df.columns:
        group_cols.append("geartype")

    agg = df.groupby(group_cols, as_index=False).agg(
        fishing_hours=("fishing_hours", "sum"),
        vessel_count=("vessel_count", "sum"),
    )
    return agg


def process_gap_events() -> pd.DataFrame | None:
    """Process AIS gap events into a mappable DataFrame."""
    gap_file = config.GFW_API_DIR / "ais_gap_events.json"
    if not gap_file.exists():
        print("  No AIS gap events file found.")
        return None

    with open(gap_file) as f:
        events = json.load(f)

    rows = []
    for e in events:
        gap_info = e.get("gap", {})
        off_pos = gap_info.get("offPosition", {})
        on_pos = gap_info.get("onPosition", {})
        vessel = e.get("vessel", {})

        rows.append({
            "event_id": e.get("id"),
            "start": e.get("start"),
            "end": e.get("end"),
            "lat": e.get("position", {}).get("lat"),
            "lon": e.get("position", {}).get("lon"),
            "off_lat": float(off_pos.get("lat", 0)),
            "off_lon": float(off_pos.get("lon", 0)),
            "on_lat": float(on_pos.get("lat", 0)),
            "on_lon": float(on_pos.get("lon", 0)),
            "duration_hours": gap_info.get("durationHours", 0),
            "distance_km": float(gap_info.get("distanceKm", 0)),
            "intentional": gap_info.get("intentionalDisabling", False),
            "vessel_name": vessel.get("name"),
            "vessel_flag": vessel.get("flag"),
            "vessel_ssvid": vessel.get("ssvid"),
        })

    df = pd.DataFrame(rows)
    df["year"] = pd.to_datetime(df["start"]).dt.year

    # Filter to intentional disabling only for mapping
    intentional = df[df["intentional"] == True]
    print(f"  AIS gap events: {len(df):,} total, {len(intentional):,} intentional")

    return intentional


def process_encounter_events() -> pd.DataFrame | None:
    """Process encounter events into a mappable DataFrame."""
    enc_file = config.GFW_API_DIR / "transshipment_events.json"
    if not enc_file.exists():
        print("  No encounter events file found.")
        return None

    with open(enc_file) as f:
        events = json.load(f)

    rows = []
    for e in events:
        vessel = e.get("vessel", {})
        encounter = e.get("encounter", {})
        encountered_vessel = encounter.get("vessel", {})

        rows.append({
            "event_id": e.get("id"),
            "start": e.get("start"),
            "end": e.get("end"),
            "lat": e.get("position", {}).get("lat"),
            "lon": e.get("position", {}).get("lon"),
            "encounter_type": encounter.get("type"),
            "median_distance_km": encounter.get("medianDistanceKilometers"),
            "potential_risk": encounter.get("potentialRisk", False),
            "vessel_name": vessel.get("name"),
            "vessel_flag": vessel.get("flag"),
            "encountered_vessel_name": encountered_vessel.get("name"),
            "encountered_vessel_flag": encountered_vessel.get("flag"),
            "distance_from_shore_km": e.get("distances", {}).get("startDistanceFromShoreKm"),
        })

    df = pd.DataFrame(rows)
    df["year"] = pd.to_datetime(df["start"]).dt.year

    # Focus on carrier-fishing encounters (likely transshipment)
    carrier_types = ["carrier-fishing", "fishing-carrier"]
    transshipment = df[df["encounter_type"].isin(carrier_types)]
    print(f"  Encounter events: {len(df):,} total, {len(transshipment):,} carrier-fishing")

    return df


def process():
    """Run the full processing pipeline."""
    print("=== Processing GFW Effort Data ===")

    # Step 1: Load raw data
    print("\n1. Loading raw effort data...")
    effort = load_raw_effort()

    # Step 2: Extract year
    print("\n2. Extracting year...")
    effort = extract_year(effort)
    if "year" in effort.columns:
        for year in sorted(effort["year"].unique()):
            count = (effort["year"] == year).sum()
            hours = effort[effort["year"] == year]["fishing_hours"].sum()
            print(f"    {year}: {count:,} rows, {hours:,.0f} fishing hours")

    # Step 3: Exclude domestic fishing
    print("\n3. Filtering out domestic fishing...")
    before = len(effort)
    effort = exclude_domestic_waters(effort)
    print(f"    {before:,} -> {len(effort):,} rows (DWF only)")

    # Step 4: Aggregate
    print("\n4. Aggregating by grid cell + year + geartype...")
    gridded = aggregate_effort(effort)
    print(f"    {len(gridded):,} aggregated rows")

    # Step 5: Save
    print("\n5. Saving processed data...")
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    outfile = config.PROCESSED_DIR / "china_dwf_effort.parquet"
    gridded.to_parquet(outfile, index=False)
    print(f"    Effort: {outfile} ({outfile.stat().st_size / 1e6:.1f} MB)")

    # Summary
    if "year" in gridded.columns:
        summary = gridded.groupby("year").agg(
            total_fishing_hours=("fishing_hours", "sum"),
            grid_cells=("fishing_hours", "count"),
            vessels=("vessel_count", "sum"),
        )
        summary_file = config.PROCESSED_DIR / "china_dwf_effort_summary.csv"
        summary.to_csv(summary_file)
        print(f"\n    DWF Effort Summary:")
        print(summary.to_string())

    # Step 6: Process events
    print("\n6. Processing AIS gap events...")
    gaps = process_gap_events()
    if gaps is not None and len(gaps) > 0:
        gap_file = config.PROCESSED_DIR / "ais_gaps_intentional.parquet"
        gaps.to_parquet(gap_file, index=False)
        print(f"    Saved: {gap_file}")

    print("\n7. Processing encounter events...")
    encounters = process_encounter_events()
    if encounters is not None and len(encounters) > 0:
        enc_file = config.PROCESSED_DIR / "encounters.parquet"
        encounters.to_parquet(enc_file, index=False)
        print(f"    Saved: {enc_file}")

    print("\nDone.")


if __name__ == "__main__":
    process()
