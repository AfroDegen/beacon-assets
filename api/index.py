import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from app.crawler import crawl
from app.extractor import extract_images_from_page


class handler(BaseHTTPRequestHandler):

    def send_json(self, status_code: int, payload: dict):
        body = json.dumps(
            payload,
            indent=2,
            ensure_ascii=False
        ).encode("utf-8")

        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()

        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path != "/api/crawl":
            self.send_json(
                404,
                {
                    "error": "Use /api/crawl?url=https://example.com"
                }
            )
            return

        params = parse_qs(parsed.query)
        urls = params.get("url")

        if not urls:
            self.send_json(
                400,
                {
                    "error": "Missing url parameter"
                }
            )
            return

        target_url = urls[0]

        try:
            # ---------------------------------------------
            # 1. Crawl website
            # ---------------------------------------------

            pages = crawl(
                target_url,
                max_pages=25
            )

            # ---------------------------------------------
            # 2. Extract image assets from every page
            # ---------------------------------------------

            assets = []

            for page in pages:
                page_assets = extract_images_from_page(page)
                assets.extend(page_assets)

            # ---------------------------------------------
            # 3. Deduplicate assets across pages
            # ---------------------------------------------

            unique_assets = []
            seen = set()

            for asset in assets:
                asset_url = asset["url"]

                if asset_url in seen:
                    continue

                seen.add(asset_url)
                unique_assets.append(asset)

            # ---------------------------------------------
            # 4. Build response
            # ---------------------------------------------

            response = {
                "site": target_url,
                "page_count": len(pages),
                "asset_count": len(unique_assets),
                "pages": [
                    {
                        "url": page["url"],
                        "final_url": page["final_url"],
                        "status": page["status"],
                        "content_type": page["content_type"],
                        "title": page["title"],
                        "link_count": len(page["links"]),
                    }
                    for page in pages
                ],
                "assets": unique_assets,
            }

            self.send_json(200, response)

        except Exception as exc:
            self.send_json(
                500,
                {
                    "error": str(exc)
                }
            )