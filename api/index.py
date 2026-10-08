from http.server import BaseHTTPRequestHandler
import json
from urllib.parse import parse_qs, urlparse

from app.crawler import crawl


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path != "/api/crawl":
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            self.wfile.write(
                json.dumps({
                    "error": "Use /api/crawl?url=https://example.com"
                }).encode("utf-8")
            )

            return

        params = parse_qs(parsed.query)
        urls = params.get("url")

        if not urls:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            self.wfile.write(
                json.dumps({
                    "error": "Missing url parameter"
                }).encode("utf-8")
            )

            return

        try:
            pages = crawl(urls[0], max_pages=25)

            response = {
                "url": urls[0],
                "page_count": len(pages),
                "pages": pages,
            }

            body = json.dumps(
                response,
                indent=2,
                ensure_ascii=False
            ).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()

            self.wfile.write(body)

        except Exception as exc:
            body = json.dumps({
                "error": str(exc)
            }).encode("utf-8")

            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()

            self.wfile.write(body)