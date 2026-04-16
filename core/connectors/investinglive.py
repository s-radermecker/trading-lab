from __future__ import annotations

import time
from typing import List, Optional
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://investinglive.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


@dataclass
class RawArticle:
    title: str
    url: str
    summary: str
    source: str = "investinglive"


def _fetch_page(url: str, timeout: int = 10) -> Optional[BeautifulSoup]:
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        print(f"[investinglive] fetch error: {e}")
        return None


def _extract_article_text(article_url: str) -> str:
    soup = _fetch_page(article_url)
    if not soup:
        return ""

    selectors = [
        "div.article-body-normal",
        "div.article-body-large",
        "div.article-body-largest",
        "div.html-content__general-styles",
        "article",
    ]

    for selector in selectors:
        body = soup.select_one(selector)
        if body:
            paragraphs = body.find_all("p")
            text = " ".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
            if len(text) > 100:
                return text[:3000]

    return ""


def fetch_latest_articles(
    section: str = "forex",
    max_articles: int = 5,
    fetch_full_text: bool = True,
    delay_between_requests: float = 1.0,
) -> List[RawArticle]:
    section_urls = {
        "forex": f"{BASE_URL}/forex/",
        "live": f"{BASE_URL}/live-feed/",
        "technical": f"{BASE_URL}/technical-analysis/",
        "home": f"{BASE_URL}/",
    }

    url = section_urls.get(section, f"{BASE_URL}/forex/")
    soup = _fetch_page(url)

    if not soup:
        return []

    articles = []
    seen_urls = set()

    links = soup.find_all("a", href=True)

    for link in links:
        href = link.get("href", "")

        if not href.startswith("/") and not href.startswith(BASE_URL):
            continue

        if href.startswith("/"):
            full_url = BASE_URL + href
        else:
            full_url = href

        if full_url in seen_urls:
            continue

        skip_patterns = [
            "/brokers", "/education", "/about", "/contact",
            "/privacy", "/terms", "/author/", "/tag/",
            "/category/", "#", "?",
        ]
        if any(p in full_url for p in skip_patterns):
            continue

        path_parts = full_url.replace(BASE_URL, "").strip("/").split("/")
        if len(path_parts) < 2:
            continue

        title_tag = link.find(["h1", "h2", "h3", "h4", "span", "div"])
        title = title_tag.get_text(strip=True) if title_tag else link.get_text(strip=True)

        if not title or len(title) < 10:
            continue

        seen_urls.add(full_url)

        full_text = ""
        if fetch_full_text:
            time.sleep(delay_between_requests)
            full_text = _extract_article_text(full_url)

        articles.append(RawArticle(
            title=title,
            url=full_url,
            summary=full_text if full_text else title,
            source="investinglive",
        ))

        if len(articles) >= max_articles:
            break

    return articles