"""
Load and validate the curated incident database.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config

REQUIRED_COLUMNS = [
    "id", "date", "lat", "lon", "category", "title",
    "description", "country_affected", "source_name", "source_url",
    "severity",
]

VALID_CATEGORIES = [
    "eez_violation",
    "ais_disable",
    "coast_guard_clash",
    "ocean_mapping",
    "transshipment",
    "us_interest",
]


def load_incidents() -> pd.DataFrame:
    """Load and validate the incident database CSV."""
    incidents_file = config.INCIDENTS_DIR / "incidents.csv"
    if not incidents_file.exists():
        raise FileNotFoundError(
            f"Incident database not found at {incidents_file}. "
            "Create it from the template."
        )

    df = pd.read_csv(incidents_file)

    # Validate columns
    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Validate categories
    invalid = set(df["category"].dropna()) - set(VALID_CATEGORIES)
    if invalid:
        print(f"  WARNING: Unknown categories: {invalid}")

    # Validate coordinates
    bad_coords = (
        (df["lat"].abs() > 90) | (df["lon"].abs() > 180)
    )
    if bad_coords.any():
        print(f"  WARNING: {bad_coords.sum()} rows have invalid coordinates")

    # Validate severity
    if "severity" in df.columns:
        bad_sev = ~df["severity"].isin([1, 2, 3])
        if bad_sev.any():
            print(f"  WARNING: {bad_sev.sum()} rows have invalid severity (must be 1-3)")

    print(f"  Loaded {len(df)} incidents:")
    for cat in VALID_CATEGORIES:
        count = (df["category"] == cat).sum()
        if count > 0:
            print(f"    {cat}: {count}")

    return df


def incidents_to_geojson(df: pd.DataFrame) -> dict:
    """Convert incidents DataFrame to GeoJSON for web mapping."""
    features = []
    for _, row in df.iterrows():
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(row["lon"]), float(row["lat"])],
            },
            "properties": {
                col: (row[col] if pd.notna(row[col]) else None)
                for col in df.columns
                if col not in ("lat", "lon")
            },
        }
        features.append(feature)

    return {"type": "FeatureCollection", "features": features}


if __name__ == "__main__":
    try:
        df = load_incidents()
    except FileNotFoundError as e:
        print(e)
