import os
import re
import asyncio
import logging
from flask import Flask, request, jsonify
from services.airtable import get_bundle_record, mark_bundle_image_created
from services.shopify import get_product_images_by_sku, upload_images_to_bundle
from services.gemini import generate_bundle_image

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)


def classify_images(images: list[dict]) -> tuple[list[str], list[str]]:
    """
    Split Shopify product images into bottle and box lists by alt text.
    - No '- Image N' suffix  → bottle
    - Ends with '- Image 2'  → box
    - Ends with '- Image 3+' → ignored
    """
    bottle_urls = []
    box_urls = []
    suffix_pattern = re.compile(r"- Image (\d+)\s*$", re.IGNORECASE)

    for img in images:
        alt = (img.get("alt") or "").strip()
        match = suffix_pattern.search(alt)
        if not match:
            bottle_urls.append(img["src"])
        elif match.group(1) == "2":
            box_urls.append(img["src"])
        # Image 3, 4, etc. → ignored

    return bottle_urls, box_urls


@app.route("/webhook/bundle-image", methods=["POST"])
def bundle_image_webhook():
    data = request.get_json(force=True)
    record_id = data.get("recordId")

    if not record_id:
        return jsonify({"error": "Missing recordId"}), 400

    logger.info(f"Processing bundle image for record: {record_id}")

    try:
        # 1. Fetch bundle record from Airtable
        record = get_bundle_record(record_id)
        fields = record["fields"]
        bundle_name = fields.get("Bundle name", "").strip()

        if not bundle_name:
            return jsonify({"error": "Bundle name is empty"}), 400

        skus = [
            fields.get("SKU Product 1", ""),
            fields.get("SKU Product 2", ""),
            fields.get("SKU Product 3", ""),
            fields.get("SKU Product 4", ""),
        ]
        skus = [s.strip() for s in skus if s and s.strip()]

        logger.info(f"Bundle: {bundle_name} | SKUs: {skus}")

        # 2. Fetch Shopify product images for each SKU
        all_images = []
        for sku in skus:
            images = get_product_images_by_sku(sku)
            all_images.extend(images)

        if not all_images:
            return jsonify({"error": "No images found in Shopify for given SKUs"}), 404

        # 3. Classify images
        bottle_urls, box_urls = classify_images(all_images)
        logger.info(f"Bottle images: {len(bottle_urls)} | Box images: {len(box_urls)}")

        if not bottle_urls:
            return jsonify({"error": "No bottle images found"}), 404
        if not box_urls:
            return jsonify({"error": "No box images found"}), 404

        # 4. Generate both images via Gemini (run in parallel)
        bottle_filename = f"{bundle_name}.jpg"
        box_filename = f"{bundle_name}2.jpg"

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        bottle_bytes, box_bytes = loop.run_until_complete(
            asyncio.gather(
                generate_bundle_image(bottle_urls, "bottles"),
                generate_bundle_image(box_urls, "boxes"),
            )
        )
        loop.close()

        # 5. Upload both images to Shopify bundle product
        bundle_sku = fields.get("Bundle SKU", "")
        upload_images_to_bundle(
            bundle_sku=bundle_sku,
            bottle_image=bottle_bytes,
            bottle_filename=bottle_filename,
            box_image=box_bytes,
            box_filename=box_filename,
        )

        # 6. Mark as done in Airtable
        mark_bundle_image_created(record_id)

        logger.info(f"Done: {bundle_name}")
        return jsonify({"success": True, "bundle": bundle_name}), 200

    except Exception as e:
        logger.error(f"Error processing record {record_id}: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
