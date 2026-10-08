from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


IMAGE_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".svg",
    ".avif",
)


def normalize_asset_url(url: str, source_page: str) -> str:
    """
    Convert a discovered asset reference into an absolute URL.
    """
    if not url:
        return ""

    url = url.strip()

    if url.startswith(("data:", "blob:", "javascript:")):
        return ""

    absolute = urljoin(source_page, url)

    parsed = urlparse(absolute)

    if parsed.scheme not in ("http", "https"):
        return ""

    return absolute


def extract_srcset(value: str) -> list[str]:
    """
    Extract URLs from a srcset attribute.

    Example:
        image-small.jpg 480w, image-large.jpg 1200w
    """
    if not value:
        return []

    urls = []

    for item in value.split(","):
        item = item.strip()

        if not item:
            continue

        # URL is the first token.
        url = item.split()[0]

        if url:
            urls.append(url)

    return urls


def extract_images(html: str, source_page: str) -> list[dict]:
    """
    Extract publicly referenced image URLs from a webpage.

    Sources currently supported:

    - <img src>
    - <img srcset>
    - lazy-loading image attributes
    - <source srcset>
    - Open Graph og:image
    - Twitter card image
    - CSS background-image URLs
    """

    soup = BeautifulSoup(html, "html.parser")

    assets = []
    seen = set()

    def add_asset(url: str, discovery_method: str):
        absolute_url = normalize_asset_url(url, source_page)

        if not absolute_url:
            return

        if absolute_url in seen:
            return

        seen.add(absolute_url)

        assets.append({
            "url": absolute_url,
            "source_page": source_page,
            "discovery_method": discovery_method,
        })

    # ---------------------------------------------------------
    # <img>
    # ---------------------------------------------------------

    for img in soup.find_all("img"):
        src = img.get("src")

        if src:
            add_asset(src, "img_src")

        srcset = img.get("srcset")

        if srcset:
            for url in extract_srcset(srcset):
                add_asset(url, "img_srcset")

        # Common lazy-loading attributes.
        for attribute in (
            "data-src",
            "data-lazy-src",
            "data-original",
            "data-image",
            "data-lazy",
        ):
            value = img.get(attribute)

            if value:
                add_asset(value, f"img_{attribute}")

        # Lazy-loaded srcset.
        for attribute in (
            "data-srcset",
            "data-lazy-srcset",
        ):
            value = img.get(attribute)

            if value:
                for url in extract_srcset(value):
                    add_asset(url, f"img_{attribute}")

    # ---------------------------------------------------------
    # <source srcset>
    # ---------------------------------------------------------

    for source in soup.find_all("source"):
        src = source.get("src")

        if src:
            add_asset(src, "source_src")

        srcset = source.get("srcset")

        if srcset:
            for url in extract_srcset(srcset):
                add_asset(url, "source_srcset")

    # ---------------------------------------------------------
    # Open Graph / social images
    # ---------------------------------------------------------

    for meta in soup.find_all("meta"):
        property_name = (
            meta.get("property")
            or meta.get("name")
            or ""
        ).lower()

        content = meta.get("content")

        if not content:
            continue

        if property_name in (
            "og:image",
            "og:image:url",
            "twitter:image",
            "twitter:image:src",
        ):
            add_asset(content, f"meta_{property_name}")

    # ---------------------------------------------------------
    # Inline CSS background images
    # ---------------------------------------------------------

    for element in soup.find_all(style=True):
        style = element.get("style", "")

        marker = "url("

        start = 0

        while True:
            index = style.find(marker, start)

            if index == -1:
                break

            value_start = index + len(marker)
            value_end = style.find(")", value_start)

            if value_end == -1:
                break

            value = style[value_start:value_end].strip()
            value = value.strip("'\"")

            add_asset(value, "inline_css_background")

            start = value_end + 1

    return assets


def extract_images_from_page(page: dict) -> list[dict]:
    """
    Extract image assets from a crawler page record.

    The crawler page must contain:
        html
        url
        final_url
    """

    html = page.get("html", "")

    if not html:
        return []

    source_page = page.get("final_url") or page.get("url", "")

    return extract_images(
        html=html,
        source_page=source_page,
    )