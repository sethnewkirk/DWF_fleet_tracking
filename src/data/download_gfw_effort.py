"""
Download and extract GFW fishing effort data for Chinese-flagged vessels.

Two strategies:
  1. Preferred: Use GFW Python API to query CHN-only data directly
  2. Fallback:  Download bulk CSVs from Zenodo and filter post-download

The bulk dataset on Zenodo is ~26.3 GB total (all flags, all years).
The API approach avoids this by querying only CHN-flagged effort.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config


def download_via_api() -> bool:
    """
    Use the GFW Python API client to fetch Chinese fishing effort.
    Requires GFW_API_KEY to be set.

    Returns True on success, False if API is unavailable.
    """
    if not config.GFW_API_KEY:
        print("  No GFW API key configured. Set GFW_API_KEY env var or update config.")
        return False

    try:
        # The gfw-api-python-client provides map visualization and 4wings API
        # For gridded effort, we use the 4wings API endpoint
        import requests

        headers = {
            "Authorization": f"Bearer {config.GFW_API_KEY}",
            "Content-Type": "application/json",
        }

        config.GFW_EFFORT_DIR.mkdir(parents=True, exist_ok=True)

        for year in config.YEARS:
            outfile = config.GFW_EFFORT_DIR / f"china_effort_{year}.csv"
            if outfile.exists():
                print(f"  {year}: already downloaded, skipping")
                continue

            print(f"  Fetching {year} fishing effort via API...")

            # Use the datasets API to get fishing effort filtered by flag
            url = f"{config.GFW_API_BASE}/datasets/public-global-fishing-effort:latest/download"
            params = {
                "format": "csv",
                "filters[0]": f"flag in ('{config.TARGET_FLAG}')",
                "date-range": f"{year}-01-01,{year}-12-31",
                "spatial-resolution": "low",  # 0.1 degree
                "temporal-resolution": "yearly",
            }

            try:
                resp = requests.get(url, headers=headers, params=params, timeout=300)
                resp.raise_for_status()

                with open(outfile, "wb") as f:
                    f.write(resp.content)
                print(f"  Saved {outfile} ({len(resp.content) / 1e6:.1f} MB)")

            except requests.RequestException as e:
                print(f"  API request failed for {year}: {e}")
                print("  Will fall back to bulk download.")
                return False

        return True

    except ImportError:
        print("  gfw-api-python-client not installed.")
        return False


def download_bulk_from_zenodo() -> bool:
    """
    Download the full GFW fishing effort v3.0 dataset from Zenodo.

    WARNING: This is ~26.3 GB. We download the fleet-level daily CSV files
    which include flag state, allowing us to filter to CHN post-download.
    """
    import requests

    config.GFW_EFFORT_DIR.mkdir(parents=True, exist_ok=True)

    print("  Downloading bulk data from Zenodo...")
    print("  WARNING: Full dataset is ~26.3 GB. This will take a while.")
    print()
    print("  Alternative: Set GFW_API_KEY to download only Chinese-flagged data.")
    print("  Register at https://globalfishingwatch.org/our-apis/")
    print()

    # The Zenodo dataset contains multiple files. The fleet-level files
    # are organized as yearly CSVs with columns including flag, geartype,
    # cell_ll_lat, cell_ll_lon, fishing_hours, mmsi.
    #
    # For the bulk approach, we need to download the full files and filter.
    # The exact file structure on Zenodo may vary; this attempts the
    # most common layout.

    zenodo_record_id = "14982712"
    api_url = f"https://zenodo.org/api/records/{zenodo_record_id}"

    try:
        resp = requests.get(api_url, timeout=60)
        resp.raise_for_status()
        record = resp.json()
    except requests.RequestException as e:
        print(f"  Failed to fetch Zenodo record metadata: {e}")
        return False

    files = record.get("files", [])
    if not files:
        print("  No files found in Zenodo record.")
        return False

    print(f"  Found {len(files)} files in Zenodo record:")
    for f in files:
        size_mb = f.get("size", 0) / 1e6
        print(f"    {f['key']}: {size_mb:.1f} MB")

    # Download only the fleet-daily files that contain per-vessel data
    # Look for files matching our year range
    downloaded = 0
    for file_info in files:
        fname = file_info["key"]
        # Look for CSV files that might contain our years
        if not fname.endswith(".csv.zip") and not fname.endswith(".csv"):
            continue

        year_match = False
        for year in config.YEARS:
            if str(year) in fname:
                year_match = True
                break

        if not year_match and "fleet" not in fname.lower():
            continue

        outfile = config.GFW_EFFORT_DIR / fname
        if outfile.exists():
            print(f"  {fname}: already downloaded")
            downloaded += 1
            continue

        download_url = file_info["links"]["self"]
        print(f"  Downloading {fname}...")
        try:
            resp = requests.get(download_url, timeout=600, stream=True)
            resp.raise_for_status()
            with open(outfile, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            downloaded += 1
            print(f"  Saved {outfile}")
        except requests.RequestException as e:
            print(f"  Failed: {e}")

    return downloaded > 0


def filter_bulk_to_china(input_path: Path, output_path: Path) -> int:
    """
    Read a bulk CSV (possibly very large) and write only CHN-flagged rows.
    Uses chunked reading to handle multi-GB files.

    Returns number of rows written.
    """
    total_rows = 0
    first_chunk = True

    for chunk in pd.read_csv(input_path, chunksize=500_000):
        china_rows = chunk[chunk["flag"] == config.TARGET_FLAG]
        if len(china_rows) == 0:
            continue
        china_rows.to_csv(
            output_path,
            mode="w" if first_chunk else "a",
            header=first_chunk,
            index=False,
        )
        total_rows += len(china_rows)
        first_chunk = False

    return total_rows


def download_effort():
    """Main entry point: try API first, fall back to bulk download."""
    print("=== Downloading GFW Fishing Effort Data ===")

    if download_via_api():
        print("\nAPI download complete.")
        return True

    print("\nFalling back to Zenodo bulk download...")
    if download_bulk_from_zenodo():
        print("\nBulk download complete. Run process_effort.py to filter to CHN.")
        return True

    print("\nNo data downloaded. Please either:")
    print("  1. Set GFW_API_KEY and re-run, or")
    print("  2. Manually download from https://zenodo.org/records/14982712")
    return False


if __name__ == "__main__":
    download_effort()
