from __future__ import annotations

import pytest
import httpx
import respx

from app.services.scraper import ArticleContent, ArticleError, fetch_article


_WIKI_URL = "https://en.wikipedia.org/wiki/Albert_Einstein"

_VALID_HTML = """
<html><body>
<h1 id="firstHeading">Albert Einstein</h1>
<div id="mw-content-text">
  <div class="mw-parser-output">
    <p>Albert Einstein was a German-born theoretical physicist.<sup>[1]</sup></p>
    <p>He developed the theory of relativity.</p>
    <table class="infobox"><tr><td>Born</td></tr></table>
  </div>
</div>
</body></html>
"""

_DISAMBIGUATION_HTML = """
<html><body>
<h1 id="firstHeading">Mercury (disambiguation)</h1>
<div id="mw-content-text">
  <div class="dmbox dmbox-disambig">
    <p>Mercury may refer to several things.</p>
  </div>
</div>
</body></html>
"""

_EMPTY_BODY_HTML = """
<html><body>
<h1 id="firstHeading">Empty Article</h1>
<div id="mw-content-text">
  <div class="mw-parser-output"></div>
</div>
</body></html>
"""


async def test_fetch_article_returns_parsed_content():
    with respx.mock:
        respx.get(_WIKI_URL).mock(return_value=httpx.Response(200, text=_VALID_HTML))
        result = await fetch_article(_WIKI_URL)

    assert isinstance(result, ArticleContent)
    assert result.title == "Albert Einstein"
    assert "theoretical physicist" in result.body_text
    assert "theory of relativity" in result.body_text


async def test_fetch_article_strips_citation_brackets():
    with respx.mock:
        respx.get(_WIKI_URL).mock(return_value=httpx.Response(200, text=_VALID_HTML))
        result = await fetch_article(_WIKI_URL)

    assert "[1]" not in result.body_text


async def test_fetch_article_strips_tables():
    with respx.mock:
        respx.get(_WIKI_URL).mock(return_value=httpx.Response(200, text=_VALID_HTML))
        result = await fetch_article(_WIKI_URL)

    assert "Born" not in result.body_text


async def test_fetch_article_rejects_non_wikipedia_url():
    with pytest.raises(ArticleError, match="Not a Wikipedia URL"):
        await fetch_article("https://example.com/some-article")


async def test_fetch_article_raises_on_disambiguation_page():
    with respx.mock:
        respx.get(_WIKI_URL).mock(return_value=httpx.Response(200, text=_DISAMBIGUATION_HTML))
        with pytest.raises(ArticleError, match="Disambiguation page"):
            await fetch_article(_WIKI_URL)


async def test_fetch_article_raises_on_empty_body():
    with respx.mock:
        respx.get(_WIKI_URL).mock(return_value=httpx.Response(200, text=_EMPTY_BODY_HTML))
        with pytest.raises(ArticleError, match="empty or could not be parsed"):
            await fetch_article(_WIKI_URL)


async def test_fetch_article_raises_on_http_error():
    with respx.mock:
        respx.get(_WIKI_URL).mock(return_value=httpx.Response(404))
        with pytest.raises(ArticleError, match="HTTP 404"):
            await fetch_article(_WIKI_URL)


async def test_fetch_article_raises_on_timeout():
    with respx.mock:
        respx.get(_WIKI_URL).mock(side_effect=httpx.TimeoutException("timed out"))
        with pytest.raises(ArticleError, match="timed out"):
            await fetch_article(_WIKI_URL)
