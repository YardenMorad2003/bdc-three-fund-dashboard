from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_ROOT = PROJECT_ROOT / ".cache" / "free-sources"
DEFAULT_USER_AGENT = "BDC Tracker research contact yarde@example.com"
csv.field_size_limit(2_147_483_647)


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        values = dict(attrs)
        self._href = values.get("href")
        self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._parts).strip()))
            self._href = None
            self._parts = []


@dataclass
class CachedResponse:
    url: str
    data: bytes
    path: Path
    fetched_at_utc: str
    from_cache: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cache_path(url: str, suffix: str | None = None) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    guessed = suffix or Path(url.split("?", 1)[0]).suffix or ".bin"
    return CACHE_ROOT / f"{digest}{guessed}"


def request_bytes(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 90,
    attempts: int = 3,
) -> bytes:
    request_headers = {
        "User-Agent": os.environ.get("EDGAR_IDENTITY") or DEFAULT_USER_AGENT,
        "Accept-Encoding": "identity",
        "Accept": "application/json,text/csv,text/tab-separated-values,application/zip,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/html;q=0.9,*/*;q=0.8",
    }
    if headers:
        request_headers.update(headers)
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urlopen(Request(url, headers=request_headers), timeout=timeout) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.25 * (attempt + 1))
    assert last_error is not None
    raise last_error


def cached_bytes(
    url: str,
    *,
    suffix: str | None = None,
    max_age_hours: float = 24,
    headers: dict[str, str] | None = None,
    timeout: int = 90,
) -> CachedResponse:
    path = cache_path(url, suffix)
    meta_path = path.with_suffix(path.suffix + ".json")
    now = time.time()
    if path.exists() and now - path.stat().st_mtime <= max_age_hours * 3600:
        fetched_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
        if meta_path.exists():
            try:
                fetched_at = json.loads(meta_path.read_text(encoding="utf-8")).get("fetched_at_utc", fetched_at)
            except (OSError, json.JSONDecodeError):
                pass
        return CachedResponse(url, path.read_bytes(), path, fetched_at, True)
    data = request_bytes(url, headers=headers, timeout=timeout)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    fetched_at = utc_now()
    meta_path.write_text(
        json.dumps({"url": url, "fetched_at_utc": fetched_at, "bytes": len(data)}, indent=2),
        encoding="utf-8",
    )
    return CachedResponse(url, data, path, fetched_at, False)


def cached_json(url: str, **kwargs: Any) -> tuple[Any, CachedResponse]:
    response = cached_bytes(url, suffix=".json", **kwargs)
    return json.loads(response.data.decode("utf-8")), response


def request_json_post(
    url: str,
    payload: Any,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 90,
) -> Any:
    request_headers = {
        "User-Agent": os.environ.get("EDGAR_IDENTITY") or DEFAULT_USER_AGENT,
        "Accept-Encoding": "identity",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if headers:
        request_headers.update(headers)
    body = json.dumps(payload).encode("utf-8")
    with urlopen(Request(url, data=body, headers=request_headers, method="POST"), timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def page_links(url: str, *, max_age_hours: float = 24) -> tuple[list[tuple[str, str]], CachedResponse]:
    response = cached_bytes(url, suffix=".html", max_age_hours=max_age_hours)
    parser = LinkParser()
    parser.feed(response.data.decode("utf-8", errors="replace"))
    return [(urljoin(url, href), text) for href, text in parser.links], response


def discover_zip_links(page_url: str) -> tuple[list[dict[str, str]], CachedResponse]:
    links, response = page_links(page_url)
    output: list[dict[str, str]] = []
    seen: set[str] = set()
    for url, label in links:
        clean_url = url.split("#", 1)[0]
        if ".zip" not in clean_url.lower() or clean_url in seen:
            continue
        seen.add(clean_url)
        output.append({"url": clean_url, "label": re.sub(r"\s+", " ", label).strip()})
    return output, response


def zip_sort_key(row: dict[str, str]) -> tuple[int, int, int, str]:
    text = f"{row.get('label', '')} {row.get('url', '')}".lower()
    year_match = re.search(r"(20\d{2})", text)
    year = int(year_match.group(1)) if year_match else 0
    quarter_match = re.search(r"(?:q|quarter\D*)([1-4])", text)
    month_match = re.search(r"(?:_|-|\b)(0?[1-9]|1[0-2])(?:\.zip|_|-|\b)", text)
    quarter = int(quarter_match.group(1)) if quarter_match else 0
    month = int(month_match.group(1)) if month_match else quarter * 3
    return year, month, quarter, text


def newest_zip_links(page_url: str, limit: int = 1) -> tuple[list[dict[str, str]], CachedResponse]:
    links, response = discover_zip_links(page_url)
    return sorted(links, key=zip_sort_key, reverse=True)[:limit], response


def decode_delimited(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def zip_members(data: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.namelist()


def find_zip_member(data: bytes, candidates: Iterable[str]) -> str | None:
    normalized_candidates = [candidate.lower() for candidate in candidates]
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name in archive.namelist():
            base = Path(name).name.lower()
            if any(candidate == base or candidate in base for candidate in normalized_candidates):
                return name
    return None


def iter_zip_dict_rows(
    data: bytes,
    candidates: Iterable[str],
    *,
    delimiter: str = "\t",
) -> Iterator[dict[str, str]]:
    member = find_zip_member(data, candidates)
    if member is None:
        return
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        with archive.open(member) as binary_file:
            with io.TextIOWrapper(binary_file, encoding="utf-8-sig", errors="replace", newline="") as text_file:
                reader = csv.DictReader(text_file, delimiter=delimiter)
                for row in reader:
                    yield {str(key or "").strip(): str(value or "").strip() for key, value in row.items()}


def pick(row: dict[str, Any], *names: str) -> Any:
    normalized = {re.sub(r"[^a-z0-9]", "", str(key).lower()): value for key, value in row.items()}
    for name in names:
        key = re.sub(r"[^a-z0-9]", "", name.lower())
        if key in normalized:
            return normalized[key]
    return None


def number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("$", "").replace("%", "")
    if not text or text.lower() in {"na", "n/a", "none", "null", "-", "--"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    try:
        value_float = float(text)
    except ValueError:
        return None
    return -value_float if negative else value_float


def normalize_entity(value: str) -> str:
    text = value.casefold().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    suffixes = {
        "inc", "incorporated", "corp", "corporation", "company", "co", "llc", "l l c",
        "lp", "l p", "ltd", "limited", "plc", "holdings", "holding", "group", "sa", "ag",
    }
    tokens = [token for token in text.split() if token not in suffixes]
    return " ".join(tokens)


def status_row(
    source_id: str,
    name: str,
    category: str,
    status: str,
    url: str,
    *,
    records: int = 0,
    as_of: str | None = None,
    confidence: str = "source-direct",
    message: str = "",
    credential_env: str | None = None,
) -> dict[str, Any]:
    return {
        "id": source_id,
        "name": name,
        "category": category,
        "status": status,
        "records": records,
        "as_of": as_of,
        "confidence": confidence,
        "url": url,
        "message": message,
        "credential_env": credential_env,
    }


def safe_error(exc: Exception) -> str:
    if isinstance(exc, HTTPError):
        return f"HTTP {exc.code} from provider"
    if isinstance(exc, URLError):
        return f"Network error: {exc.reason}"
    return f"{type(exc).__name__}: {exc}"
