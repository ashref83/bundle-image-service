import os
import base64
import logging
import requests

logger = logging.getLogger(__name__)

SHOPIFY_STORE = os.environ["SHOPIFY_STORE"]
SHOPIFY_TOKEN = os.environ["SHOPIFY_ADMIN_TOKEN"]

GRAPHQL_URL = f"https://{SHOPIFY_STORE}/admin/api/2024-10/graphql.json"

HEADERS = {
    "X-Shopify-Access-Token": SHOPIFY_TOKEN,
    "Content-Type": "application/json",
}


def get_product_images_by_sku(sku: str) -> list[dict]:
    """Find Shopify product images by SKU using GraphQL."""
    query = """
    query getProductBySku($query: String!) {
      products(first: 1, query: $query) {
        edges {
          node {
            id
            images(first: 10) {
              edges {
                node {
                  url
                  altText
                }
              }
            }
          }
        }
      }
    }
    """

    variables = {"query": f"sku:{sku}"}
    response = requests.post(
        GRAPHQL_URL,
        json={"query": query, "variables": variables},
        headers=HEADERS,
    )
    response.raise_for_status()
    data = response.json()

    edges = data.get("data", {}).get("products", {}).get("edges", [])
    if not edges:
        logger.warning(f"No Shopify product found for SKU: {sku}")
        return []

    images = edges[0]["node"]["images"]["edges"]
    return [
        {"src": img["node"]["url"], "alt": img["node"].get("altText") or ""}
        for img in images
    ]


def _get_bundle_product_id_graphql(bundle_sku: str) -> str | None:
    """Find the Shopify product GID for the bundle by SKU using GraphQL."""
    query = """
    query getProductBySku($query: String!) {
      products(first: 1, query: $query) {
        edges {
          node {
            id
            legacyResourceId
          }
        }
      }
    }
    """
    variables = {"query": f"sku:{bundle_sku}"}
    response = requests.post(
        GRAPHQL_URL,
        json={"query": query, "variables": variables},
        headers=HEADERS,
    )
    response.raise_for_status()
    data = response.json()

    edges = data.get("data", {}).get("products", {}).get("edges", [])
    if not edges:
        return None

    return edges[0]["node"]["legacyResourceId"]


def upload_images_to_bundle(
    bundle_sku: str,
    bottle_image: bytes,
    bottle_filename: str,
    box_image: bytes,
    box_filename: str,
) -> None:
    """Upload bottle and box images to the Shopify bundle product."""
    product_id = _get_bundle_product_id_graphql(bundle_sku)
    if not product_id:
        raise ValueError(f"Bundle product not found in Shopify for SKU: {bundle_sku}")

    REST_BASE = f"https://{SHOPIFY_STORE}/admin/api/2024-10"
    images_url = f"{REST_BASE}/products/{product_id}/images.json"
    rest_headers = {
        "X-Shopify-Access-Token": SHOPIFY_TOKEN,
        "Content-Type": "application/json",
    }

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
        response = requests.post(images_url, json=payload, headers=rest_headers)
        response.raise_for_status()
        logger.info(f"Uploaded {filename} to Shopify product {product_id}")