from urllib.parse import urljoin, urlparse, urldefrag
from collections import deque

import requests
from bs4 import BeautifulSoup


USER_AGENT = (
    "Mozilla/5.0 (compatible; BeaconAssets/0.1; "
    "+https://reedstar.store)"
)

DEFAULT_TIMEOUT = 15


def normalize_url(url: str) -> str:
    """
    Normalize a URL for crawling.

    - Removes fragments (#section)
    - Removes trailing slash except for the root
    """
    url, _ = urldefrag(url)

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        return ""

    path = parsed.path or "/"

    if path != "/":
        path = path.rstrip("/")

    normalized = parsed._replace(path=path).geturl()

    return normalized


def is_same_domain(url: str, hostname: str) -> bool:
    """Return True if the URL belongs to the starting hostname."""
    parsed = urlparse(url)

    return (
        parsed.scheme in ("http", "https")
        and parsed.hostname == hostname
    )


def extract_links(html: str, source_url: str, hostname: str) -> list[str]:
    """
    Extract same-domain page links from an HTML document.
    """
    soup = BeautifulSoup(html, "html.parser")

    links = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()

        if not href:
            continue

        absolute_url = urljoin(source_url, href)
        normalized = normalize_url(absolute_url)

        if not normalized:
            continue

        if is_same_domain(normalized, hostname):
            links.add(normalized)

    return sorted(links)


def fetch_page(session: requests.Session, url: str) -> dict:
    """
    Fetch one webpage and return crawl information.
    """
    try:
        response = session.get(
            url,
            timeout=DEFAULT_TIMEOUT,
            allow_redirects=True,
        )

        content_type = response.headers.get("content-type", "")

        if "text/html" not in content_type.lower():
            return {
                "url": url,
                "final_url": response.url,
                "status": response.status_code,
                "content_type": content_type,
                "title": "",
                "links": [],
                "html": "",
            }

        soup = BeautifulSoup(response.text, "html.parser")

        title = ""
        if soup.title:
            title = soup.title.get_text(" ", strip=True)

        return {
            "url": url,
            "final_url": response.url,
            "status": response.status_code,
            "content_type": content_type,
            "title": title,
            "links": [],
            "html": response.text,
        }

    except requests.RequestException as exc:
        return {
            "url": url,
            "final_url": url,
            "status": None,
            "content_type": "",
            "title": "",
            "links": [],
            "html": "",
            "error": str(exc),
        }


def crawl(start_url: str, max_pages: int = 25) -> list[dict]:
    """
    Crawl a website starting from start_url.

    Only same-domain URLs are followed.

    Returns a list of page records.
    """
    start_url = normalize_url(start_url)

    if not start_url:
        raise ValueError("Invalid start URL")

    parsed_start = urlparse(start_url)

    if not parsed_start.hostname:
        raise ValueError("URL has no hostname")

    hostname = parsed_start.hostname

    queue = deque([start_url])
    queued = {start_url}
    visited = set()
    pages = []

    with requests.Session() as session:
        session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        })

        while queue and len(pages) < max_pages:
            current_url = queue.popleft()

            if current_url in visited:
                continue

            visited.add(current_url)

            page = fetch_page(session, current_url)

            if page["html"]:
                links = extract_links(
                    page["html"],
                    page["final_url"],
                    hostname,
                )

                page["links"] = links

                for link in links:
                    if link not in visited and link not in queued:
                        queue.append(link)
                        queued.add(link)

            # HTML is useful during the extraction phase,
            # but we don't want to keep it in the final crawl result.
            page.pop("html", None)

            pages.append(page)

    return pages


if __name__ == "__main__":
    import json
    import sys

    url = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"

    result = crawl(url, max_pages=10)

    print(json.dumps(result, indent=2, ensure_ascii=False))