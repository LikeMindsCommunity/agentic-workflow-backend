"""
Web scraper for fetching documentation from URLs.
Crawls pages, extracts content, converts to markdown.
"""
import time
import re
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup, Comment
from markdownify import markdownify as md
import config


STRIP_TAGS = [
    "nav", "footer", "header", "aside", "script", "style",
    "noscript", "iframe", "form", "button", "svg", "img"
]

STRIP_PATTERNS = [
    "nav", "sidebar", "menu", "footer", "header", "breadcrumb",
    "cookie", "banner", "ad-", "popup", "modal", "social", "share",
    "comment", "signup", "newsletter"
]


def _should_strip(tag) -> bool:
    classes = " ".join(tag.get("class", []))
    tag_id = tag.get("id", "")
    combined = f"{classes} {tag_id}".lower()
    return any(p in combined for p in STRIP_PATTERNS)


def _extract_content(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag_name in STRIP_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    for tag in soup.find_all(True):
        if _should_strip(tag):
            tag.decompose()

    main_content = None
    for selector in ["main", "article", '[role="main"]', ".content",
                     ".docs-content", ".documentation", "#content"]:
        main_content = soup.select_one(selector)
        if main_content:
            break

    if not main_content:
        main_content = soup.find("body") or soup

    content_md = md(str(main_content), heading_style="ATX", strip=["img"])
    content_md = re.sub(r"\n{3,}", "\n\n", content_md).strip()

    if len(content_md) > config.MAX_CONTENT_PER_PAGE:
        content_md = content_md[:config.MAX_CONTENT_PER_PAGE] + "\n\n... [content truncated]"

    return content_md


def _find_doc_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    base_domain = urlparse(base_url).netloc
    links = set()

    skip_exts = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf",
                 ".zip", ".tar", ".gz", ".mp4", ".mp3", ".css", ".js"}

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue

        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)

        if parsed.netloc != base_domain:
            continue
        if any(parsed.path.lower().endswith(ext) for ext in skip_exts):
            continue

        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            clean_url += f"?{parsed.query}"

        links.add(clean_url)

    return list(links)


def scrape_url(url: str, follow_links: bool = False,
               max_pages: int = None) -> list[dict]:
    if max_pages is None:
        max_pages = config.MAX_PAGES_PER_URL

    results = []
    visited = set()
    to_visit = [url]

    with httpx.Client(timeout=config.SCRAPE_TIMEOUT, follow_redirects=True) as client:
        while to_visit and len(visited) < max_pages:
            current_url = to_visit.pop(0)
            if current_url in visited:
                continue
            visited.add(current_url)

            try:
                print(f"    Fetching: {current_url}")
                response = client.get(current_url, headers={
                    "User-Agent": "LikeMinds-DocScraper/1.0"
                })
                response.raise_for_status()
            except httpx.HTTPError as e:
                print(f"    [WARNING] Failed: {current_url} - {e}")
                continue

            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type:
                continue

            html = response.text
            content = _extract_content(html)

            if len(content.strip()) < 50:
                continue

            soup = BeautifulSoup(html, "html.parser")
            title = (soup.title.string.strip()
                     if soup.title and soup.title.string else current_url)

            results.append({
                "filename": title,
                "content": f"# {title}\n\nSource: {current_url}\n\n{content}",
                "file_type": "url",
                "source_url": current_url
            })

            if follow_links and len(visited) < max_pages:
                for link in _find_doc_links(html, current_url):
                    if link not in visited:
                        to_visit.append(link)

            if to_visit:
                time.sleep(config.SCRAPE_DELAY)

    return results


def scrape_urls(urls: list[str], follow_links: bool = False,
                max_pages: int = None) -> list[dict]:
    all_results = []
    seen_urls = set()

    for url in urls:
        for r in scrape_url(url, follow_links=follow_links, max_pages=max_pages):
            source = r.get("source_url", r["filename"])
            if source not in seen_urls:
                seen_urls.add(source)
                all_results.append(r)

    return all_results
