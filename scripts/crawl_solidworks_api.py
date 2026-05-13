#!/usr/bin/env python3
"""Crawl SOLIDWORKS API Web Help pages into RAG-friendly local files."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import quote, urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup


DEFAULT_START_URLS = [
    "https://help.solidworks.com/2025/english/api/sldworksapiprogguide/Welcome.htm",
    "https://help.solidworks.com/2025/english/api/help_list.htm?id=2",
]


@dataclass(frozen=True)
class Page:
    url: str
    title: str
    browser_title: str
    help_html: str
    text: str
    links: list[str]


def normalize_url(url: str, base_url: str | None = None) -> str:
    absolute = urljoin(base_url or "", url)
    absolute, _fragment = urldefrag(absolute)
    parsed = urlparse(absolute)
    path = quote(parsed.path, safe="/%:@")
    query = quote(parsed.query, safe="=&?/%:@.+,;~-")
    return parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        path=path,
        query=query,
    ).geturl()


def in_scope(url: str, scope_prefix: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme in {"http", "https"}
        and parsed.netloc == "help.solidworks.com"
        and parsed.path.startswith(scope_prefix)
        and parsed.path.lower().endswith((".htm", ".html"))
    )


def page_id(url: str) -> str:
    parsed = urlparse(url)
    stem = f"{parsed.path}?{parsed.query}" if parsed.query else parsed.path
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", stem.strip("/"))
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    return f"{safe[:140]}_{digest}"


def extract_next_data(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__", type="application/json")
    if not script or not script.string:
        return {}
    return json.loads(script.string)


def text_from_help_html(help_html: str) -> str:
    soup = BeautifulSoup(help_html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    return re.sub(r"\n{3,}", "\n\n", text)


def links_from_html(help_html: str, page_url: str, scope_prefix: str) -> list[str]:
    soup = BeautifulSoup(help_html, "html.parser")
    links: list[str] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "")
        if href.startswith(("mailto:", "javascript:", "#")):
            continue
        url = normalize_url(href, page_url)
        if in_scope(url, scope_prefix) and url not in seen:
            links.append(url)
            seen.add(url)
    return links


def parse_page(html: str, url: str, scope_prefix: str) -> Page:
    data = extract_next_data(html)
    page_props = data.get("props", {}).get("pageProps", {})
    help_data = page_props.get("helpContentData") or {}
    help_html = help_data.get("helpText") or ""

    if not help_html:
        soup = BeautifulSoup(html, "html.parser")
        main = soup.find("main") or soup.body or soup
        help_html = str(main)

    title = help_data.get("title") or ""
    browser_title = help_data.get("browserTitle") or ""
    text = text_from_help_html(help_html)
    links = links_from_html(help_html, url, scope_prefix)

    next_prev = page_props.get("nextPrevData") or {}
    for key in ("next_url", "prev_url"):
        value = next_prev.get(key)
        if value:
            link = normalize_url(value, url)
            if in_scope(link, scope_prefix) and link not in links:
                links.append(link)

    return Page(
        url=url,
        title=title or browser_title or url,
        browser_title=browser_title,
        help_html=help_html,
        text=text,
        links=links,
    )


def load_index(output_dir: Path) -> tuple[set[str], list[str]]:
    index_path = output_dir / "pages.jsonl"
    seen: set[str] = set()
    discovered: list[str] = []
    if not index_path.exists():
        return seen, discovered
    with index_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                seen.add(record["url"])
                discovered.extend(record.get("links") or [])
            except (KeyError, json.JSONDecodeError):
                continue
    return seen, discovered


def write_page(output_dir: Path, page: Page) -> None:
    pid = page_id(page.url)
    html_dir = output_dir / "html"
    text_dir = output_dir / "text"
    html_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    (html_dir / f"{pid}.html").write_text(page.help_html, encoding="utf-8")
    (text_dir / f"{pid}.txt").write_text(page.text, encoding="utf-8")

    record = {
        "id": pid,
        "url": page.url,
        "title": page.title,
        "browser_title": page.browser_title,
        "text_path": str((text_dir / f"{pid}.txt").as_posix()),
        "html_path": str((html_dir / f"{pid}.html").as_posix()),
        "char_count": len(page.text),
        "links": page.links,
    }
    with (output_dir / "pages.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def crawl(
    start_urls: Iterable[str],
    output_dir: Path,
    scope_prefix: str,
    max_pages: int,
    delay: float,
    timeout: float,
    resume: bool,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (compatible; SolidWorksApiRagCrawler/0.1; "
                "+local research crawler)"
            )
        }
    )

    seen, discovered = load_index(output_dir) if resume else (set(), [])
    queued: set[str] = set()
    queue: deque[str] = deque()
    for start_url in [*start_urls, *discovered]:
        url = normalize_url(start_url)
        if in_scope(url, scope_prefix) and url not in seen and url not in queued:
            queue.append(url)
            queued.add(url)

    fetched = 0
    failures: list[dict[str, str]] = []

    while queue and fetched < max_pages:
        url = queue.popleft()
        queued.discard(url)
        if url in seen:
            continue

        try:
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
            page = parse_page(response.text, response.url, scope_prefix)
            write_page(output_dir, page)
            seen.add(url)
            fetched += 1
            print(f"[{fetched}] {page.title} :: {url} :: links={len(page.links)}")

            for link in page.links:
                if link not in seen and link not in queued:
                    queue.append(link)
                    queued.add(link)
        except Exception as exc:  # noqa: BLE001 - crawler should continue collecting.
            failures.append({"url": url, "error": repr(exc)})
            print(f"[failed] {url} :: {exc!r}")

        if delay > 0:
            time.sleep(delay)

    state = {
        "fetched_this_run": fetched,
        "seen_total": len(seen),
        "queued_remaining": len(queue),
        "failures": failures,
    }
    (output_dir / "crawl_state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(state, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start-url",
        action="append",
        dest="start_urls",
        help="Start URL. Can be passed multiple times.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/solidworks_api_2025",
        help="Directory for pages.jsonl, html/, text/, and crawl_state.json.",
    )
    parser.add_argument(
        "--scope-prefix",
        default="/2025/english/api/",
        help="Only crawl help.solidworks.com paths under this prefix.",
    )
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignore existing pages.jsonl instead of skipping already indexed URLs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    crawl(
        start_urls=args.start_urls or DEFAULT_START_URLS,
        output_dir=Path(args.output_dir),
        scope_prefix=args.scope_prefix,
        max_pages=args.max_pages,
        delay=args.delay,
        timeout=args.timeout,
        resume=not args.no_resume,
    )


if __name__ == "__main__":
    main()
