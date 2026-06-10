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
    """
    Find Shopify product images for a given SKU.
    Uses product search by SKU via GraphQL-style REST search.
    """
    # Search products that have this SKU
    url = f"{BASE_URL}/products.json"
    params = {"fields": "id,variants,images", "limit": 250}
    
    page_info = None
    while True:
        if page_info:
            params["page_info"] = page_info
        
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        products = response.json().get("products", [])
        
        for product in products:
            for variant in product.get("variants", []):
                if variant.get("sku", "").strip() == sku:
                    return [
                        {"src": img["src"], "alt": img.get("alt") or ""}
                        for img in product.get("images", [])
                    ]
        
        # Check for next page
        link_header = response.headers.get("Link", "")
        if 'rel="next"' in link_header:
            import re
            match = re.search(r'page_info=([^&>]+).*rel="next"', link_header)
            if match:
                page_info = match.group(1)
                params = {"fields": "id,variants,images", "limit": 250, "page_info": page_info}
            else:
                break
        else:
            break
    
    logger.warning(f"No Shopify variant found for SKU: {sku}")
    return []

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
