from __future__ import annotations

import re
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup, Tag


WIKIPEDIA_HOST = "en.wikipedia.org"
_CITATION_RE = re.compile(r"\[\d+\]")


class ArticleError(Exception):
    pass


@dataclass
class ArticleContent:
    title: str
    body_text: str


async def fetch_article(url: str) -> ArticleContent:
    _require_wikipedia_url(url)
    html = await _get_html(url)
    return _parse(html)


def _require_wikipedia_url(url: str) -> None:
    if WIKIPEDIA_HOST not in url:
        raise ArticleError("Not a Wikipedia URL")


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; WikiChat/1.0; +https://github.com/wikichat)"
    )
}


async def _get_html(url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(url, headers=_HEADERS)
            response.raise_for_status()
            return response.text
    except httpx.TimeoutException as exc:
        raise ArticleError("Request timed out") from exc
    except httpx.HTTPStatusError as exc:
        raise ArticleError(f"HTTP {exc.response.status_code}") from exc


def _parse(html: str) -> ArticleContent:
    soup = BeautifulSoup(html, "lxml")
    title = _extract_title(soup)
    body = _extract_body(soup)
    if not body:
        raise ArticleError("Article body is empty or could not be parsed")
    return ArticleContent(title=title, body_text=body)


def _extract_title(soup: BeautifulSoup) -> str:
    tag = soup.find("h1", {"id": "firstHeading"}) or soup.find("h1", class_="firstHeading")
    return tag.get_text(strip=True) if isinstance(tag, Tag) else ""


def _extract_body(soup: BeautifulSoup) -> str:
    content = soup.find("div", {"id": "mw-content-text"})
    if not isinstance(content, Tag):
        return ""

    if content.find(class_="dmbox-disambig"):
        raise ArticleError("Disambiguation page — provide a more specific URL")

    for unwanted in content.find_all(["table", "sup", "style", "script"]):
        unwanted.decompose()

    for unwanted in content.find_all(class_=["navbox", "reflist", "references", "mw-editsection"]):
        unwanted.decompose()

    paragraphs = [
        p.get_text(" ", strip=True)
        for p in content.find_all("p")
        if p.get_text(strip=True)
    ]

    raw = "\n\n".join(paragraphs)
    return _CITATION_RE.sub("", raw).strip()
