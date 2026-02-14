"""
Geospatial utility functions for DWF fleet analysis.
"""

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config


def load_eez(simplify_tolerance: float | None = None) -> gpd.GeoDataFrame:
    """
    Load EEZ boundaries from Marine Regions shapefile.

    Args:
        simplify_tolerance: If set, simplify geometries (degrees).
            Use ~0.01 for full resolution, ~0.1 for web display.
    """
    shp_files = list(config.EEZ_DIR.glob("**/*.shp"))
    if not shp_files:
        raise FileNotFoundError(
            f"No EEZ shapefiles found in {config.EEZ_DIR}. "
            "Download from marineregions.org first."
        )
    # Use the main EEZ polygon file (not boundaries/lines)
    eez_file = None
    for f in shp_files:
        if "eez" in f.stem.lower() and "line" not in f.stem.lower():
            eez_file = f
            break
    if eez_file is None:
        eez_file = shp_files[0]

    gdf = gpd.read_file(eez_file)
    if simplify_tolerance is not None:
        gdf["geometry"] = gdf["geometry"].simplify(simplify_tolerance)
    return gdf


def get_china_eez(eez_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Extract China's EEZ polygon(s) from the full EEZ dataset."""
    # Marine Regions uses ISO_SOV1 or SOVEREIGN1 for the sovereign state
    for col in ["ISO_SOV1", "ISO_TER1", "SOVEREIGN1", "TERRITORY1"]:
        if col not in eez_gdf.columns:
            continue
        mask = eez_gdf[col].str.contains("CHN|China", case=False, na=False)
        if mask.any():
            return eez_gdf[mask]
    raise ValueError("Could not identify China's EEZ in the dataset")


def filter_effort_outside_eez(
    effort_df: pd.DataFrame,
    eez_gdf: gpd.GeoDataFrame,
    lat_col: str = "cell_ll_lat",
    lon_col: str = "cell_ll_lon",
) -> pd.DataFrame:
    """
    Remove fishing effort records that fall within China's EEZ.

    This isolates Distant Water Fishing activity from domestic/coastal fishing.
    """
    china_eez = get_china_eez(eez_gdf)
    china_union = china_eez.union_all()

    # Build points from grid cell centers (offset by half resolution)
    half = config.GRID_RESOLUTION / 2
    points = gpd.GeoSeries(
        [Point(lon + half, lat + half)
         for lat, lon in zip(effort_df[lat_col], effort_df[lon_col])],
        crs="EPSG:4326",
    )
    inside_china = points.within(china_union)
    return effort_df[~inside_china].copy()


def compute_eez_proximity(
    effort_df: pd.DataFrame,
    eez_gdf: gpd.GeoDataFrame,
    lat_col: str = "cell_ll_lat",
    lon_col: str = "cell_ll_lon",
) -> pd.Series:
    """
    Compute approximate distance (degrees) from each effort cell to nearest
    non-Chinese EEZ boundary. Negative values = inside a foreign EEZ.

    Returns a Series aligned with effort_df index.
    """
    # Exclude China's EEZ from the set
    china_eez = get_china_eez(eez_gdf)
    china_idx = china_eez.index
    foreign_eez = eez_gdf.drop(china_idx)
    foreign_union = foreign_eez.union_all()

    half = config.GRID_RESOLUTION / 2
    points = gpd.GeoSeries(
        [Point(lon + half, lat + half)
         for lat, lon in zip(effort_df[lat_col], effort_df[lon_col])],
        crs="EPSG:4326",
    )

    distances = points.distance(foreign_union.boundary)
    inside = points.within(foreign_union)
    # Convention: negative distance = inside foreign EEZ
    distances[inside] = -distances[inside]
    return distances


def aggregate_effort_grid(
    df: pd.DataFrame,
    lat_col: str = "cell_ll_lat",
    lon_col: str = "cell_ll_lon",
    resolution: float = 0.1,
) -> pd.DataFrame:
    """
    Aggregate fishing effort to a coarser grid.

    Snaps lat/lon to the given resolution and sums fishing hours per cell per year.
    """
    df = df.copy()
    df["grid_lat"] = np.floor(df[lat_col] / resolution) * resolution
    df["grid_lon"] = np.floor(df[lon_col] / resolution) * resolution

    group_cols = ["grid_lat", "grid_lon"]
    if "year" in df.columns:
        group_cols.append("year")
    if "geartype" in df.columns:
        group_cols.append("geartype")

    agg = df.groupby(group_cols, as_index=False).agg(
        fishing_hours=("fishing_hours", "sum"),
        vessel_count=("mmsi", "nunique") if "mmsi" in df.columns
        else ("fishing_hours", "count"),
    )
    return agg
