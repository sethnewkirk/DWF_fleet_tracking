"""
Fetch supplementary data from the GFW API.

This module handles data that is NOT available in the bulk Zenodo download:
  - AIS-disabling (gap) events for Chinese-flagged vessels
  - Transshipment encounter events
  - 2025 near-real-time fishing effort

All require a valid GFW API key.
"""

import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config


def _headers() -> dict:
    if not config.GFW_API_KEY:
        raise RuntimeError(
            "GFW_API_KEY not set. Register at "
            "https://globalfishingwatch.org/our-apis/ "
            "and set the GFW_API_KEY environment variable."
        )
    return {
        "Authorization": f"Bearer {config.GFW_API_KEY}",
        "Content-Type": "application/json",
    }


def _paginated_get(url: str, params: dict, max_pages: int = 50) -> list:
    """Fetch paginated results from GFW API."""
    all_results = []
    offset = 0
    limit = 100

    for page in range(max_pages):
        params["offset"] = offset
        params["limit"] = limit

        resp = requests.get(url, headers=_headers(), params=params, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        entries = data.get("entries", data.get("data", []))
        if not entries:
            break

        all_results.extend(entries)
        offset += limit
        print(f"    Page {page + 1}: {len(entries)} results (total: {len(all_results)})")

        # Respect rate limits
        time.sleep(0.5)

        if len(entries) < limit:
            break

    return all_results


def fetch_ais_gap_events():
    """
    Fetch AIS-disabling events for Chinese-flagged vessels.

    These are events where a vessel's AIS transponder goes silent for
    an extended period, often near EEZ boundaries.
    """
    print("=== Fetching AIS Gap Events ===")
    config.GFW_API_DIR.mkdir(parents=True, exist_ok=True)

    outfile = config.GFW_API_DIR / "ais_gap_events.json"
    if outfile.exists():
        print(f"  Already downloaded: {outfile}")
        return

    url = f"{config.GFW_API_BASE}/events"
    all_events = []

    for year in config.YEARS:
        print(f"\n  Fetching gaps for {year}...")
        params = {
            "datasets[0]": "public-global-gaps-events:latest",
            "flags[0]": config.TARGET_FLAG,
            "start-date": f"{year}-01-01",
            "end-date": f"{year}-12-31",
        }

        try:
            events = _paginated_get(url, params)
            print(f"  {year}: {len(events)} gap events")
            all_events.extend(events)
        except requests.RequestException as e:
            print(f"  Failed for {year}: {e}")

    with open(outfile, "w") as f:
        json.dump(all_events, f)
    print(f"\nSaved {len(all_events)} total gap events to {outfile}")


def fetch_transshipment_events():
    """
    Fetch encounter events (potential transshipment) involving Chinese vessels.
    """
    print("\n=== Fetching Transshipment Events ===")
    config.GFW_API_DIR.mkdir(parents=True, exist_ok=True)

    outfile = config.GFW_API_DIR / "transshipment_events.json"
    if outfile.exists():
        print(f"  Already downloaded: {outfile}")
        return

    url = f"{config.GFW_API_BASE}/events"
    all_events = []

    for year in config.YEARS:
        print(f"\n  Fetching encounters for {year}...")
        params = {
            "datasets[0]": "public-global-encounters-events:latest",
            "flags[0]": config.TARGET_FLAG,
            "start-date": f"{year}-01-01",
            "end-date": f"{year}-12-31",
        }

        try:
            events = _paginated_get(url, params)
            print(f"  {year}: {len(events)} encounter events")
            all_events.extend(events)
        except requests.RequestException as e:
            print(f"  Failed for {year}: {e}")

    with open(outfile, "w") as f:
        json.dump(all_events, f)
    print(f"\nSaved {len(all_events)} total encounter events to {outfile}")


if __name__ == "__main__":
    try:
        fetch_ais_gap_events()
        fetch_transshipment_events()
    except RuntimeError as e:
        print(f"\nERROR: {e}")
        print("\nTo use the GFW API:")
        print("  1. Register at https://globalfishingwatch.org/our-apis/")
        print("  2. Set: export GFW_API_KEY='your-key-here'")
        print("  3. Re-run this script")
