import os
import base64
import logging
import requests

logger = logging.getLogger(__name__)

SHOPIFY_STORE = os.environ["SHOPIFY_STORE"]          # e.g. your-store.myshopify.com
SHOPIFY_TOKEN = os.environ["SHOPIFY_ADMIN_TOKEN"]    # Admin API access token
API_VERSION = os.environ.get("SHOPIFY_API_VERSION", "2024-10")

BASE_URL = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}"

HEADERS = {
    "X-Shopify-Access-Token": SHOPIFY_TOKEN,
    "Content-Type": "application/json",
}


def get_product_images_by_sku(sku: str) -> list[dict]:
    """Find Shopify product images for a given SKU using direct SKU search."""
    url = f"{BASE_URL}/products.json"
    params = {
        "fields": "id,variants,images",
        "limit": 10,
    }
    
    response = requests.get(url, headers=HEADERS, params=params)
    response.raise_for_status()
    
    # Use GraphQL-style variant search instead
    variant_url = f"{BASE_URL}/variants.json"
    variant_params = {
        "fields": "id,sku,product_id",
        "limit": 250,
    }
    
    response = requests.get(variant_url, headers=HEADERS, params=variant_params)
    response.raise_for_status()
    variants = response.json().get("variants", [])
    
    product_id = None
    for variant in variants:
        if (variant.get("sku") or "").strip() == sku:
            product_id = variant["product_id"]
            break
    
    if not product_id:
        logger.warning(f"No Shopify variant found for SKU: {sku}")
        return []
    
    images_url = f"{BASE_URL}/products/{product_id}/images.json"
    img_response = requests.get(images_url, headers=HEADERS)
    img_response.raise_for_status()
    images = img_response.json().get("images", [])
    
    return [{"src": img["src"], "alt": img.get("alt") or ""} for img in images]

def _get_bundle_product_id(bundle_sku: str) -> str | None:
    """Find the Shopify product ID for the bundle by its SKU."""
    url = f"{BASE_URL}/variants.json"
    params = {"fields": "id,sku,product_id", "limit": 250}
    response = requests.get(url, headers=HEADERS, params=params)
    response.raise_for_status()
    variants = response.json().get("variants", [])

    for variant in variants:
        if variant.get("sku", "").strip() == bundle_sku:
            return variant["product_id"]

    return None


def upload_images_to_bundle(
    bundle_sku: str,
    bottle_image: bytes,
    bottle_filename: str,
    box_image: bytes,
    box_filename: str,
) -> None:
    """Upload bottle and box images to the Shopify bundle product."""
    product_id = _get_bundle_product_id(bundle_sku)
    if not product_id:
        raise ValueError(f"Bundle product not found in Shopify for SKU: {bundle_sku}")

    images_url = f"{BASE_URL}/products/{product_id}/images.json"

    for image_bytes, filename in [
        (bottle_image, bottle_filename),
        (box_image, box_filename),
    ]:
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "image": {
                "attachment": encoded,
                "filename": filename,
            }
        }
        response = requests.post(images_url, json=payload, headers=HEADERS)
        response.raise_for_status()
        logger.info(f"Uploaded {filename} to Shopify product {product_id}")
