"""
Process GFW fishing effort data into analysis-ready format.

Pipeline:
  1. Load raw GFW effort CSVs (already filtered to CHN or filter now)
  2. Exclude activity inside China's EEZ (= domestic fishing, not DWF)
  3. Aggregate to 0.1-degree grid by year
  4. Save as Parquet for fast loading
"""

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config
from src.utils.geo import (
    aggregate_effort_grid,
    filter_effort_outside_eez,
    load_eez,
)


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
        # If this is bulk data (all flags), filter to CHN
        if "flag" in df.columns:
            before = len(df)
            df = df[df["flag"] == config.TARGET_FLAG]
            if before != len(df):
                print(f"    Filtered {before} -> {len(df)} rows (CHN only)")
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    print(f"  Total: {len(combined)} rows across {len(csv_files)} files")
    return combined


def extract_year(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure the dataframe has a 'year' column."""
    if "year" in df.columns:
        return df

    # Try to extract from date column
    for date_col in ["date", "time_range", "start_date"]:
        if date_col in df.columns:
            df["year"] = pd.to_datetime(df[date_col]).dt.year
            return df

    # Try from filename patterns embedded in data
    print("  WARNING: No date column found. Cannot assign year.")
    return df


def process():
    """Run the full processing pipeline."""
    print("=== Processing GFW Effort Data ===")

    # Step 1: Load raw data
    print("\n1. Loading raw effort data...")
    effort = load_raw_effort()

    # Step 2: Ensure year column
    print("\n2. Extracting year...")
    effort = extract_year(effort)
    if "year" in effort.columns:
        for year in sorted(effort["year"].unique()):
            count = (effort["year"] == year).sum()
            print(f"    {year}: {count} rows")

    # Step 3: Exclude domestic fishing (inside China's EEZ)
    print("\n3. Filtering out domestic fishing (inside China's EEZ)...")
    try:
        eez = load_eez(simplify_tolerance=0.01)
        before = len(effort)
        effort = filter_effort_outside_eez(effort, eez)
        print(f"    {before} -> {len(effort)} rows (excluded {before - len(effort)} domestic)")
    except FileNotFoundError:
        print("    WARNING: EEZ data not available. Skipping domestic filter.")
        print("    Download EEZ data and re-run for accurate results.")

    # Step 4: Aggregate to grid
    print("\n4. Aggregating to 0.1-degree grid...")
    # Detect column names (GFW uses cell_ll_lat/cell_ll_lon or lat/lon)
    lat_col = "cell_ll_lat" if "cell_ll_lat" in effort.columns else "lat"
    lon_col = "cell_ll_lon" if "cell_ll_lon" in effort.columns else "lon"

    if lat_col not in effort.columns:
        print(f"    WARNING: Cannot find latitude column. Available: {list(effort.columns)}")
        print("    Saving unprocessed data.")
        gridded = effort
    else:
        gridded = aggregate_effort_grid(
            effort,
            lat_col=lat_col,
            lon_col=lon_col,
            resolution=config.GRID_RESOLUTION,
        )
        print(f"    Aggregated to {len(gridded)} grid cells")

    # Step 5: Save
    print("\n5. Saving processed data...")
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    outfile = config.PROCESSED_DIR / "china_dwf_effort.parquet"
    gridded.to_parquet(outfile, index=False)
    print(f"    Saved to {outfile} ({outfile.stat().st_size / 1e6:.1f} MB)")

    # Also save a CSV summary for quick inspection
    summary_file = config.PROCESSED_DIR / "china_dwf_effort_summary.csv"
    if "year" in gridded.columns:
        summary = gridded.groupby("year").agg(
            total_fishing_hours=("fishing_hours", "sum"),
            grid_cells=("fishing_hours", "count"),
        )
        summary.to_csv(summary_file)
        print(f"    Summary saved to {summary_file}")
        print(summary.to_string())

    print("\nDone.")


if __name__ == "__main__":
    process()
