# Bundle Image Service

Render webhook service that auto-generates bundle product images via Gemini
and uploads them to Shopify when triggered from Airtable.

## Flow

1. Airtable automation fires when "Create bundle image" is checked
2. Sends `recordId` to this webhook via POST
3. Service fetches SKUs from Airtable, gets product images from Shopify
4. Classifies images: bottle (no suffix) vs box (`- Image 2` suffix)
5. Sends both sets to Gemini in parallel → two composed images
6. Uploads `{bundle_name}.jpg` and `{bundle_name}2.jpg` to Shopify bundle product
7. Checks "Bundle image created" in Airtable

## Environment Variables

| Variable | Description |
|---|---|
| `AIRTABLE_API_KEY` | Airtable personal access token |
| `AIRTABLE_BASE_ID` | Base ID (starts with `app`) |
| `AIRTABLE_TABLE_NAME` | Table name (default: `Bundle offers`) |
| `SHOPIFY_STORE` | e.g. `your-store.myshopify.com` |
| `SHOPIFY_ADMIN_TOKEN` | Shopify Admin API access token |
| `SHOPIFY_API_VERSION` | default: `2024-10` |
| `GEMINI_API_KEY` | Google AI Studio API key |

## Airtable Automation Setup

1. Trigger: **When record matches conditions** → "Create bundle image" is checked
2. Action: **Run a script** or **Send a webhook**
   - Method: `POST`
   - URL: `https://your-render-service.onrender.com/webhook/bundle-image`
   - Body:
     ```json
     { "recordId": "<record_id>" }
     ```

## Image Classification Rules

| Alt text | Classification |
|---|---|
| No `- Image N` suffix | Bottle image → sent to Gemini call 1 |
| Ends with `- Image 2` | Box image → sent to Gemini call 2 |
| Ends with `- Image 3`, `4`, etc. | Ignored |

## Local Development

```bash
pip install -r requirements.txt

export AIRTABLE_API_KEY=...
export AIRTABLE_BASE_ID=...
export SHOPIFY_STORE=...
export SHOPIFY_ADMIN_TOKEN=...
export GEMINI_API_KEY=...

python main.py
```

Test the webhook:
```bash
curl -X POST http://localhost:8000/webhook/bundle-image \
  -H "Content-Type: application/json" \
  -d '{"recordId": "recXXXXXXXXXXXXXX"}'
```

## Deployment on Render

1. Push this folder to a GitHub repo
2. Create a new **Web Service** on Render, connect the repo
3. Render auto-detects `render.yaml` and sets build/start commands
4. Add all env vars marked `sync: false` in the Render dashboard
5. Copy the service URL → paste into your Airtable automation webhook action
