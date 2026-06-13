"""Metadata lookup helpers for entry source and image URLs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen


HTTP_TIMEOUT_SECONDS = 4
APPLE_SEARCH_URL = "https://itunes.apple.com/search"
GOOGLE_BOOKS_SEARCH_URL = "https://www.googleapis.com/books/v1/volumes"
OPEN_LIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"
VINYL_CATEGORY_TERMS = ("vinyl", "record")
BOOK_CATEGORY_TERMS = ("book",)


@dataclass(frozen=True)
class LookupCandidate:
    title: str
    creator: str
    source_url: str
    image_url: str
    provider: str
    reason: str = ""


def fetch_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": "Records/0.1"})
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def category_lookup_kind(category_name: str) -> str:
    normalized_category = category_name.strip().lower()
    if any(term in normalized_category for term in VINYL_CATEGORY_TERMS):
        return "vinyl"
    if any(term in normalized_category for term in BOOK_CATEGORY_TERMS):
        return "book"
    return ""


def lookup_candidates(category_name: str, title: str, creator: str) -> list[LookupCandidate]:
    lookup_kind = category_lookup_kind(category_name)
    if lookup_kind == "vinyl":
        return lookup_vinyl(title, creator)
    if lookup_kind == "book":
        return lookup_book(title, creator)
    return []


def lookup_vinyl(title: str, creator: str) -> list[LookupCandidate]:
    query = " ".join(part for part in (title.strip(), creator.strip()) if part)
    if not query:
        return []

    candidates = apple_album_candidates(query, title, creator)
    if candidates:
        return candidates

    return [
        LookupCandidate(
            title=title.strip() or query,
            creator=creator.strip(),
            source_url=spotify_search_url(query),
            image_url="",
            provider="Spotify",
            reason="Apple Music did not return a usable album. Use this Spotify search link or enter links manually.",
        )
    ]


def apple_album_candidates(query: str, title: str, creator: str) -> list[LookupCandidate]:
    params = urlencode(
        {
            "term": query,
            "media": "music",
            "entity": "album",
            "country": "US",
            "limit": "6",
        }
    )
    try:
        payload = fetch_json(f"{APPLE_SEARCH_URL}?{params}")
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
        return []

    results = payload.get("results", [])
    ranked = sorted(results, key=lambda item: album_score(item, title, creator))
    candidates: list[LookupCandidate] = []
    seen_urls: set[str] = set()
    for item in ranked:
        source_url = str(item.get("collectionViewUrl") or "")
        album_title = str(item.get("collectionName") or "")
        artist = str(item.get("artistName") or "")
        if not source_url or not album_title:
            continue
        if source_url in seen_urls:
            continue
        seen_urls.add(source_url)
        artwork_url = upgrade_apple_artwork_url(str(item.get("artworkUrl100") or ""))
        candidates.append(
            LookupCandidate(
                title=album_title,
                creator=artist,
                source_url=source_url,
                image_url=artwork_url,
                provider="Apple Music",
                reason="Album match from Apple Music/iTunes.",
            )
        )
    return candidates[:5]


def album_score(item: dict, title: str, creator: str) -> tuple[int, str]:
    album_title = str(item.get("collectionName") or "").lower()
    artist = str(item.get("artistName") or "").lower()
    wanted_title = title.strip().lower()
    wanted_creator = creator.strip().lower()
    score = 0
    if wanted_title and album_title == wanted_title:
        score -= 4
    elif wanted_title and wanted_title in album_title:
        score -= 2
    if wanted_creator and artist == wanted_creator:
        score -= 3
    elif wanted_creator and wanted_creator in artist:
        score -= 1
    return score, album_title


def upgrade_apple_artwork_url(url: str) -> str:
    if not url:
        return ""
    upgraded = re.sub(r"/\d+x\d+bb\.", "/600x600bb.", url)
    upgraded = re.sub(r"\.\d+x\d+-\d+\.", ".600x600-75.", upgraded)
    return upgraded.replace("http://", "https://", 1)


def spotify_search_url(query: str) -> str:
    return f"https://open.spotify.com/search/{quote_plus(query)}"


def lookup_book(title: str, creator: str) -> list[LookupCandidate]:
    query = book_query(title, creator)
    if not query:
        return []
    search_text = " ".join(part for part in (title.strip(), creator.strip()) if part) or query
    metadata_candidates = [*google_book_candidates(query), *open_library_candidates(title, creator)]
    candidates = book_source_candidates(metadata_candidates)
    if candidates:
        return candidates
    return manual_book_search_candidates(search_text, title, creator)


def book_query(title: str, creator: str) -> str:
    title = title.strip()
    creator = creator.strip()
    if title and creator:
        return f"intitle:{title} inauthor:{creator}"
    if title:
        return f"intitle:{title}"
    if creator:
        return f"inauthor:{creator}"
    return ""


def google_book_candidates(query: str) -> list[LookupCandidate]:
    params = urlencode(
        {
            "q": query,
            "printType": "books",
            "maxResults": "5",
            "projection": "lite",
        }
    )
    try:
        payload = fetch_json(f"{GOOGLE_BOOKS_SEARCH_URL}?{params}")
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
        return []

    candidates: list[LookupCandidate] = []
    for item in payload.get("items", []):
        volume_info = item.get("volumeInfo") or {}
        book_title = str(volume_info.get("title") or "")
        authors = volume_info.get("authors") or []
        source_url = str(volume_info.get("previewLink") or volume_info.get("infoLink") or "")
        image_links = volume_info.get("imageLinks") or {}
        image_url = str(image_links.get("thumbnail") or image_links.get("smallThumbnail") or "")
        if not book_title or not source_url:
            continue
        candidates.append(
            LookupCandidate(
                title=book_title,
                creator=", ".join(str(author) for author in authors),
                source_url=source_url,
                image_url=normalize_google_image_url(image_url),
                provider="Google Books",
                reason="Book metadata and cover from Google Books.",
            )
        )
    return candidates


def open_library_candidates(title: str, creator: str) -> list[LookupCandidate]:
    params = {
        "limit": "5",
        "fields": "key,title,author_name,cover_i,isbn",
    }
    if title.strip():
        params["title"] = title.strip()
    if creator.strip():
        params["author"] = creator.strip()
    try:
        payload = fetch_json(f"{OPEN_LIBRARY_SEARCH_URL}?{urlencode(params)}")
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
        return []

    candidates: list[LookupCandidate] = []
    for item in payload.get("docs", []):
        book_title = str(item.get("title") or "")
        authors = item.get("author_name") or []
        key = str(item.get("key") or "")
        if not book_title or not key:
            continue
        cover_id = item.get("cover_i")
        candidates.append(
            LookupCandidate(
                title=book_title,
                creator=", ".join(str(author) for author in authors),
                source_url=f"https://openlibrary.org{key}",
                image_url=open_library_cover_url(cover_id),
                provider="Open Library",
                reason="Book metadata and cover from Open Library.",
            )
        )
    return candidates


def book_source_candidates(metadata_candidates: list[LookupCandidate]) -> list[LookupCandidate]:
    candidates: list[LookupCandidate] = []
    seen: set[tuple[str, str, str]] = set()
    for metadata in metadata_candidates:
        search_text = " ".join(part for part in (metadata.title, metadata.creator) if part)
        source_options = (
            (
                "Goodreads",
                goodreads_search_url(search_text),
                "Goodreads does not provide a stable public lookup API; this opens a Goodreads search using matched book metadata.",
            ),
            (
                "Fable",
                fable_search_url(search_text),
                "Fable does not provide a stable public lookup API; this opens a Fable search using matched book metadata.",
            ),
            (
                metadata.provider,
                metadata.source_url,
                metadata.reason,
            ),
        )
        for provider, source_url, reason in source_options:
            key = (provider, metadata.title.lower(), metadata.creator.lower())
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                LookupCandidate(
                    title=metadata.title,
                    creator=metadata.creator,
                    source_url=source_url,
                    image_url=metadata.image_url,
                    provider=provider,
                    reason=reason,
                )
            )
    return candidates[:9]


def manual_book_search_candidates(search_text: str, title: str, creator: str) -> list[LookupCandidate]:
    return [
        LookupCandidate(
            title=title.strip() or search_text,
            creator=creator.strip(),
            source_url=goodreads_search_url(search_text),
            image_url="",
            provider="Goodreads",
            reason="Goodreads does not provide a stable public lookup API; this opens a Goodreads search.",
        ),
        LookupCandidate(
            title=title.strip() or search_text,
            creator=creator.strip(),
            source_url=fable_search_url(search_text),
            image_url="",
            provider="Fable",
            reason="Fable does not provide a stable public lookup API; this opens a Fable search.",
        ),
    ]


def normalize_google_image_url(url: str) -> str:
    if not url:
        return ""
    return url.replace("http://", "https://", 1)


def open_library_cover_url(cover_id) -> str:
    if not cover_id:
        return ""
    return f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"


def goodreads_search_url(query: str) -> str:
    return f"https://www.goodreads.com/search?q={quote_plus(query)}"


def fable_search_url(query: str) -> str:
    return f"https://fable.co/search?query={quote_plus(query)}"
