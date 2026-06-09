import os
import requests

AIRTABLE_API_KEY = os.environ["AIRTABLE_API_KEY"]
AIRTABLE_BASE_ID = os.environ["AIRTABLE_BASE_ID"]
AIRTABLE_TABLE_NAME = os.environ.get("AIRTABLE_TABLE_NAME", "Bundle offers")

BASE_URL = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"

HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    "Content-Type": "application/json",
}


def get_bundle_record(record_id: str) -> dict:
    """Fetch a single bundle record from Airtable by record ID."""
    url = f"{BASE_URL}/{record_id}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()


def mark_bundle_image_created(record_id: str) -> None:
    """Check the 'Bundle image created' checkbox on the Airtable record."""
    url = f"{BASE_URL}/{record_id}"
    payload = {
        "fields": {
            "Bundle image created": True,
        }
    }
    response = requests.patch(url, json=payload, headers=HEADERS)
    response.raise_for_status()
