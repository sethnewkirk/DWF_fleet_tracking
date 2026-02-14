"""
Download Natural Earth basemap data and EEZ boundaries.

Natural Earth data is public domain and requires no registration.
Marine Regions EEZ data requires free registration at marineregions.org.
"""

import io
import sys
import zipfile
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config


NATURAL_EARTH_DATASETS = {
    "land": config.NATURAL_EARTH_LAND_URL,
    "ocean": config.NATURAL_EARTH_OCEAN_URL,
    "coastline": config.NATURAL_EARTH_COASTLINE_URL,
    "countries": config.NATURAL_EARTH_COUNTRIES_URL,
    "graticules": config.NATURAL_EARTH_GRATICULES_URL,
    "bathymetry": config.NATURAL_EARTH_BATHYMETRY_URL,
}


def download_and_extract_zip(url: str, dest_dir: Path, label: str) -> bool:
    """Download a zip file and extract to dest_dir. Returns True on success."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    print(f"  Downloading {label}...")
    try:
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  FAILED: {e}")
        return False

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        zf.extractall(dest_dir)
    print(f"  Extracted to {dest_dir}")
    return True


def download_natural_earth():
    """Download all Natural Earth datasets."""
    print("=== Downloading Natural Earth Data ===")
    success = 0
    for name, url in NATURAL_EARTH_DATASETS.items():
        dest = config.NATURAL_EARTH_DIR / name
        if dest.exists() and any(dest.glob("*.shp")):
            print(f"  {name}: already downloaded, skipping")
            success += 1
            continue
        if download_and_extract_zip(url, dest, name):
            success += 1

    print(f"\n{success}/{len(NATURAL_EARTH_DATASETS)} Natural Earth datasets ready.")
    return success == len(NATURAL_EARTH_DATASETS)


def download_eez():
    """
    Download Marine Regions EEZ v12.

    This requires registration at marineregions.org. If the direct download
    fails (authentication required), prints instructions for manual download.
    """
    print("\n=== Downloading EEZ Boundaries ===")
    dest = config.EEZ_DIR
    if dest.exists() and any(dest.glob("*.shp")):
        print("  EEZ data already downloaded, skipping")
        return True

    dest.mkdir(parents=True, exist_ok=True)

    # Try the direct download (may fail without auth cookies)
    try:
        resp = requests.get(config.EEZ_DOWNLOAD_URL, timeout=120, allow_redirects=True)
        if resp.status_code == 200 and len(resp.content) > 1_000_000:
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                zf.extractall(dest)
            print(f"  Extracted to {dest}")
            return True
    except Exception:
        pass

    print("  Direct download requires authentication.")
    print("  Manual steps:")
    print("    1. Register at https://www.marineregions.org/register.php")
    print("    2. Download 'World EEZ v12' from https://www.marineregions.org/downloads.php")
    print(f"    3. Extract the zip contents to: {dest}")
    return False


if __name__ == "__main__":
    download_natural_earth()
    download_eez()
