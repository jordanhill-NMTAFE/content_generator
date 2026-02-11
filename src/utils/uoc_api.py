"""Module for fetching and parsing training.gov.au unit of competencies using API"""

from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Dict, Any, List, Optional

import requests
import typer
from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

import json
import gzip
import time
import shutil
import textwrap
import vectorgrep
from datetime import datetime, timedelta, timezone
from pathlib import Path
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
import math

try:
    from tqdm import tqdm  # type: ignore
except Exception:
    tqdm = None  # Fallback if tqdm not installed; we'll print per-page

log = logging.getLogger(__name__)


app = typer.Typer(help="🎓 Australian VET Unit of Competency (UOC) Tool")

# Global runtime flags
_NO_CACHE: bool = False

# Shared session for connection pooling (reduces DNS lookups and TCP handshakes)
_SESSION: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    """Get or create a shared requests.Session for connection pooling."""
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        # Configure connection pool size for concurrent access
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=0,  # We handle retries manually
        )
        _SESSION.mount("https://", adapter)
        _SESSION.mount("http://", adapter)
    return _SESSION


def _fetch_with_retry(
    url: str,
    timeout: int = 30,
    max_retries: int = 5,
    session: Optional[requests.Session] = None,
) -> requests.Response:
    """Fetch a URL with exponential backoff retry logic."""
    sess = session or _get_session()
    headers = {
        "Accept": "application/json",
        "User-Agent": "NMTAFE-Content-Generator/1.0",
    }
    backoff = 0.5
    last_exc: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            resp = sess.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.HTTPError as e:
            status = getattr(e.response, "status_code", None)
            # Retry on rate-limit or server errors
            if status in {417, 429} or (status and 500 <= status < 600):
                last_exc = e
                time.sleep(min(8.0, backoff + random.uniform(0, 0.5)))
                backoff *= 2
                continue
            raise
        except requests.RequestException as e:
            # Network errors (DNS, connection, timeout) - retry with backoff
            last_exc = e
            time.sleep(min(8.0, backoff + random.uniform(0, 0.5)))
            backoff *= 2
            continue
    # All retries exhausted
    if last_exc:
        raise last_exc
    raise requests.RequestException(f"Failed to fetch {url} after {max_retries} attempts")


@app.callback()
def _global_flags(
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Bypass all caches (index, UOC/QUAL content, release/bundle/component caches)",
        envvar="UOC_NO_CACHE",
    ),
) -> None:
    global _NO_CACHE
    _NO_CACHE = bool(no_cache)


# ----------------------------
# Code/type helpers
# ----------------------------
_COURSE_CODE_RE = re.compile(r"\b[A-Z]{3,}[A-Z]*\d{5}\b")
_SKILLSET_CODE_RE = re.compile(r"\b[A-Z]{3,}SS\d{5}\b")
_UNIT_CODE_RE = re.compile(r"\b[A-Z]{3,}[A-Z]*\d{3}\b")


def is_course_like_code(code: str) -> bool:
    """Heuristic: qualifications (and many accredited courses/skill sets) end with 5 digits."""
    return bool(_COURSE_CODE_RE.fullmatch(code) or _SKILLSET_CODE_RE.fullmatch(code))


def is_unit_like_code(code: str) -> bool:
    """Heuristic for units: many end with 3 digits and not 5."""
    return bool(_UNIT_CODE_RE.fullmatch(code)) and not is_course_like_code(code)


# ----------------------------
# NRT Indexing (search API)
# ----------------------------

# Base query: nationally recognised (ASQA/TAC/VRQA)
NRT_SEARCH_URL = (
    "https://training.gov.au/api/search/training?api-version=1.0"
    "&searchText=&includeTotalCount=true&orderBy=score+desc"
    "&filter=(RecognitionManager%2FCode+eq+%2704%27+or+RecognitionManager%2FCode+eq+%2701%27+or+RecognitionManager%2FCode+eq+%2712%27)"
)

# Additional query: training package objects (types)
NRT_TP_SEARCH_URL = (
    "https://training.gov.au/api/search/training?api-version=1.0"
    "&searchText=&includeTotalCount=true&orderBy=score+desc"
    "&filter=(Type%2FId+eq+8+or+Type%2FId+eq+4+or+Type%2FId+eq+2+or+Type%2FId+eq+32)"
)


def _default_cache_dir() -> Path:
    base = Path.home() / ".cache" / "content_generator" / "uoc_index"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _meta_path(cache_dir: Path) -> Path:
    return cache_dir / "nrt_index.meta.json"


def _index_path(cache_dir: Path) -> Path:
    return cache_dir / "nrt_index.jsonl.gz"


def _is_cache_fresh(cache_dir: Path, max_age_days: int = 7) -> bool:
    meta_file = _meta_path(cache_dir)
    if not meta_file.exists():
        return False
    try:
        data = json.loads(meta_file.read_text(encoding="utf-8"))
        ts = data.get("last_updated")
        if not ts:
            return False
        last = datetime.fromisoformat(ts)
        now = datetime.now(timezone.utc).astimezone(last.tzinfo)
        return (now - last) <= timedelta(days=max_age_days)
    except Exception:
        return False


# ----------------------------
# WA TPS Nominal Hours cache helpers
# ----------------------------


def _wa_nominal_hours_path(cache_dir: Path) -> Path:
    return cache_dir / "wa_nominal_hours.json"


def _wa_nominal_hours_meta_path(cache_dir: Path) -> Path:
    return cache_dir / "wa_nominal_hours.meta.json"


def _is_wa_cache_fresh(cache_dir: Path, max_age_days: int = 30) -> bool:
    meta_file = _wa_nominal_hours_meta_path(cache_dir)
    if not meta_file.exists():
        return False
    try:
        data = json.loads(meta_file.read_text(encoding="utf-8"))
        ts = data.get("last_updated")
        if not ts:
            return False
        last = datetime.fromisoformat(ts)
        now = datetime.now(timezone.utc).astimezone(last.tzinfo)
        return (now - last) <= timedelta(days=max_age_days)
    except Exception:
        return False


def _write_meta(cache_dir: Path, total_count: int, duration_s: float):
    meta = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "source": NRT_SEARCH_URL,
        "total_count": total_count,
        "duration_seconds": round(duration_s, 3),
    }
    _meta_path(cache_dir).write_text(json.dumps(meta, indent=2), encoding="utf-8")


def _fetch_nrt_page(base_url: str, offset: int, page_size: int) -> dict:
    url = f"{base_url}&offset={offset}&pageSize={page_size}"
    resp = _fetch_with_retry(url, timeout=30)
    return resp.json()


def _safe_fetch_items(
    base_url: str,
    offset: int,
    page_size: int,
    max_retries: int = 4,
    min_page_size: int = 100,
) -> list:
    """Fetch items with retries and graceful degradation by splitting page_size.

    - Retries with exponential backoff (0.5s → 1s → 2s → 4s max)
    - On repeated HTTP errors (e.g., 417/429/5xx), halve page_size and fetch in chunks
    """
    attempt = 0
    backoff = 0.5

    while attempt <= max_retries:
        try:
            data = _fetch_nrt_page(base_url, offset, page_size)
            return data.get("data") or data.get("items") or data.get("value") or []
        except requests.HTTPError as e:
            status = getattr(e.response, "status_code", None)
            # Retry only for transient statuses
            if status in {417, 429} or (status and 500 <= status < 600):
                sleep_for = backoff + random.uniform(0, 0.25)
                time.sleep(min(4.5, sleep_for))
                backoff *= 2
                attempt += 1
                continue
            raise
        except requests.RequestException:
            sleep_for = backoff + random.uniform(0, 0.25)
            time.sleep(min(4.5, sleep_for))
            backoff *= 2
            attempt += 1
            continue

    # If still failing, try to split the page into smaller chunks
    if page_size <= min_page_size:
        # Give up gracefully with empty batch
        return []

    half = page_size // 2
    left = _safe_fetch_items(
        base_url, offset, half, max_retries=max_retries, min_page_size=min_page_size
    )
    right = _safe_fetch_items(
        base_url,
        offset + half,
        half,
        max_retries=max_retries,
        min_page_size=min_page_size,
    )
    return left + right


def _iter_nrt_items(page_size: int = 1000, max_pages: Optional[int] = None):
    offset = 0
    pages_fetched = 0
    while True:
        data = _fetch_nrt_page(NRT_SEARCH_URL, offset, page_size)
        items = data.get("data") or data.get("items") or data.get("value") or []
        if not items:
            break
        for it in items:
            yield it
        offset += page_size
        pages_fetched += 1
        if max_pages and pages_fetched >= max_pages:
            break
        # Be kind to the API
        time.sleep(0.15)


def _write_jsonl_gz(items_iter, out_path: Path) -> int:
    count = 0
    with gzip.open(out_path, "wt", encoding="utf-8") as f:
        for item in items_iter:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
            count += 1
    return count


class NRTIndex:
    """In-memory index built from the local JSONL (gz) of NRT records.

    Provides O(1) lookup by code and grouping by type.
    """

    def __init__(self, index_path: Path):
        self.index_path = index_path
        self.by_code: dict[str, dict] = {}
        self.by_type: dict[str, list[str]] = {}
        self._loaded = False

    def load(self):
        if self._loaded:
            return
        if not self.index_path.exists():
            return
        with gzip.open(self.index_path, "rt", encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    code = str(rec.get("code", "")).upper()
                    if not code:
                        continue
                    self.by_code[code] = rec
                    record_type = str(rec.get("type", "")).strip() or "UNKNOWN"
                    self.by_type.setdefault(record_type, []).append(code)
                except Exception:
                    continue
        self._loaded = True

    def get(self, code: str) -> Optional[dict]:
        if not self._loaded:
            self.load()
        return self.by_code.get(code.upper())

    def get_title(self, code: str) -> str:
        rec = self.get(code)
        if not rec:
            return ""
        return (
            rec.get("title")
            or rec.get("unitTitle")
            or rec.get("UnitTitle")
            or rec.get("name")
            or ""
        )

    def get_type(self, code: str) -> Optional[str]:
        rec = self.get(code)
        return (rec or {}).get("type") if rec else None

    def find_by_type_and_prefix(
        self,
        type_id_or_name: str,
        code_prefix: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[tuple[str, dict]]:
        """Return list of (code, record) filtered by type and optional code prefix.

        type_id_or_name may be the dict or the stringified form in the data; we match string contains.
        """
        if not self._loaded:
            self.load()
        results = []
        for code, rec in self.by_code.items():
            if code_prefix and not code.startswith(code_prefix):
                continue
            record_type = str(rec.get("type"))
            if type_id_or_name in record_type:
                results.append((code, rec))
                if limit and len(results) >= limit:
                    break
        return results


_cached_nrt_index: Optional[NRTIndex] = None


def _resolve_index_path(path_option: Optional[str]) -> Path:
    if path_option:
        return Path(path_option)
    return _index_path(_default_cache_dir())


def _get_nrt_index(path_option: Optional[str] = None) -> Optional[NRTIndex]:
    global _cached_nrt_index
    idx_path = _resolve_index_path(path_option)
    if not _NO_CACHE and _cached_nrt_index and _cached_nrt_index.index_path == idx_path:
        return _cached_nrt_index
    if idx_path.exists():
        _cached_nrt_index = NRTIndex(idx_path)
        _cached_nrt_index.load()
        return _cached_nrt_index
    return None


# ----------------------------
# Record status helpers
# ----------------------------
def _is_deleted_record(rec: dict) -> bool:
    """Return True if a record appears deleted based on status or usage fields.

    Supports both dict-style status and string-style usage fields.
    """
    try:
        status = rec.get("status")
        usage_rec = rec.get("usageRecommendation")
        usage_label = rec.get("usageRecommendationLabel")

        def has_deleted(s) -> bool:
            return isinstance(s, str) and ("deleted" in s.lower())

        # status may be dict { id, name }
        if isinstance(status, dict):
            if has_deleted(status.get("name")) or has_deleted(status.get("id")):
                return True
        elif has_deleted(status):
            return True

        if has_deleted(usage_rec) or has_deleted(usage_label):
            return True
    except Exception:
        return False
    return False


def _is_superseded_record(rec: dict) -> bool:
    """Return True if a record appears superseded based on status/usage fields or links.

    Heuristics:
    - status.name or status.id contains 'superseded'
    - status string contains 'superseded'
    - usageRecommendation/Label contains 'superseded'
    - presence of non-empty 'supersededBy'
    """
    try:
        status = rec.get("status")
        usage_rec = rec.get("usageRecommendation")
        usage_label = rec.get("usageRecommendationLabel")
        superseded_by = rec.get("supersededBy")

        def has_superseded(s) -> bool:
            return isinstance(s, str) and ("superseded" in s.lower())

        if isinstance(status, dict):
            if has_superseded(status.get("name")) or has_superseded(status.get("id")):
                return True
        elif has_superseded(status):
            return True

        if has_superseded(usage_rec) or has_superseded(usage_label):
            return True

        if superseded_by:
            return True
    except Exception:
        return False
    return False


# ----------------------------
# Record type helpers
# ----------------------------
def _is_accredited_record(rec: dict) -> bool:
    """Return True if record appears to be an accredited (non-TP) object.

    Heuristic: the stringified 'type' contains 'accredited'.
    """
    try:
        t = str(rec.get("type", "")).lower()
        return "accredited" in t
    except Exception:
        return False


# ----------------------------
# WA TPS scraping (nominal hours)
# ----------------------------

_TPS_URL = "https://tps.dtwd.wa.gov.au/apps/tps/Pages/default.aspx"
_TPS_GUID = "g_72b3d09c_3e10_4bd3_8b9c_f4643f192177"
_TPS_PREFIX = f"ctl00$SPWebPartManager1${_TPS_GUID}$ctl00$"


def _parse_tps_form(html: str) -> dict:
    """Parse TPS search page HTML and extract ASP.NET form tokens + package options."""
    soup = BeautifulSoup(html, "html.parser")
    result: dict = {}

    # Extract hidden fields
    for name in ("__VIEWSTATE", "__EVENTVALIDATION", "__REQUESTDIGEST", "__VIEWSTATEGENERATOR"):
        tag = soup.find("input", {"name": name})
        if tag:
            result[name] = tag.get("value", "")

    # Extract dynamic GUID prefix from control names
    prefix_tag = soup.find("input", {"name": re.compile(r"ctl00\$SPWebPartManager1\$g_[\w]+\$ctl00\$")})
    if prefix_tag:
        m = re.match(r"(ctl00\$SPWebPartManager1\$g_[\w_]+\$ctl00\$)", prefix_tag["name"])
        if m:
            result["_prefix"] = m.group(1)

    # Extract training package dropdown options (value=GUID, text=display name)
    ddl = soup.find("select", {"name": re.compile(r"TrainingPackageDropDownList$")})
    packages = []
    if ddl:
        for opt in ddl.find_all("option"):
            val = opt.get("value", "")
            if val:
                packages.append((val, opt.get_text(strip=True)))
    result["_packages"] = packages

    return result


def _parse_tps_results(html: str) -> tuple[list[tuple[str, int | None]], bool]:
    """Parse TPS results table HTML.

    Returns:
        (results, has_more) where results is list of (national_code, nominal_hours)
        and has_more indicates if there are additional pages.
    """
    soup = BeautifulSoup(html, "html.parser")
    results: list[tuple[str, int | None]] = []

    # Find the results grid table
    grid = soup.find("table", {"id": re.compile(r"TrainingProductGridView")})
    if not grid:
        return results, False

    rows = grid.find_all("tr")
    for row in rows[1:]:  # Skip header row
        cells = row.find_all("td")
        if len(cells) < 7:
            continue
        national_code = cells[0].get_text(strip=True)
        if not national_code or national_code == "\xa0":
            continue
        hours_text = cells[5].get_text(strip=True)
        try:
            nominal_hours = int(hours_text) if hours_text and hours_text != "\xa0" else None
        except (ValueError, TypeError):
            nominal_hours = None
        if national_code:
            results.append((national_code.upper(), nominal_hours))

    # Detect pagination: look for "Page X of Y" label
    has_more = False
    page_label = soup.find("span", {"id": re.compile(r"PageLabel")})
    if page_label:
        m = re.search(r"Page\s+(\d+)\s+of\s+(\d+)", page_label.get_text())
        if m:
            current_page, total_pages = int(m.group(1)), int(m.group(2))
            has_more = current_page < total_pages

    return results, has_more


def _build_wa_nominal_hours_mapping(concurrency: int = 3) -> dict[str, int]:
    """Scrape WA TPS to build a national_code → nominal_hours mapping.

    Strategy: for each training package in the dropdown, GET a fresh page
    to obtain valid ASP.NET ViewState tokens, then POST a search filtered
    to Module/UoC type. Handles pagination within each package.
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": "NMTAFE-Content-Generator/1.0",
    })

    # Step 1: GET the search page to extract the package list
    resp = session.get(_TPS_URL, timeout=30)
    resp.raise_for_status()
    initial_form = _parse_tps_form(resp.text)
    prefix = initial_form.get("_prefix", _TPS_PREFIX)
    packages = initial_form.get("_packages", [])

    if not packages:
        log.warning("WA TPS: no training packages found in dropdown")
        return {}

    mapping: dict[str, int] = {}

    # Step 2: For each training package, GET fresh tokens then POST search
    bar = None
    if tqdm:
        bar = tqdm(total=len(packages), unit="pkg", desc="WA TPS packages", dynamic_ncols=True)

    for pkg_idx, (pkg_guid, pkg_name) in enumerate(packages):
        try:
            # GET fresh page to get valid ViewState for this search
            time.sleep(0.15)
            fresh_resp = session.get(_TPS_URL, timeout=30)
            fresh_resp.raise_for_status()
            form_data = _parse_tps_form(fresh_resp.text)

            # POST search for this package, Module/UoC only
            post_data = {
                "__EVENTTARGET": "",
                "__EVENTARGUMENT": "",
                "__VIEWSTATE": form_data.get("__VIEWSTATE", ""),
                "__EVENTVALIDATION": form_data.get("__EVENTVALIDATION", ""),
                "__REQUESTDIGEST": form_data.get("__REQUESTDIGEST", ""),
                "__VIEWSTATEGENERATOR": form_data.get("__VIEWSTATEGENERATOR", ""),
                f"{prefix}TrainingPackageDropDownList": pkg_guid,
                f"{prefix}ModuleUocCheckBox": "on",
                f"{prefix}OrderByDropDownList": "nationaltitle",
                f"{prefix}IdentifierTextBox": "",
                f"{prefix}IncludeSupersededCheckBox": "on",
                f"{prefix}TitleTextBox": "",
                f"{prefix}SearchButton": "Search",
            }

            time.sleep(0.15)
            resp = session.post(_TPS_URL, data=post_data, timeout=60)
            resp.raise_for_status()

            # Parse results
            page_results, has_more = _parse_tps_results(resp.text)
            for code, hours in page_results:
                if hours is not None:
                    mapping[code] = hours

            # Handle pagination within this package
            page_num = 1
            while has_more:
                page_num += 1
                time.sleep(0.15)
                # Reuse tokens from last response (same search context)
                page_form = _parse_tps_form(resp.text)
                grid_id = f"{prefix}TrainingProductGridView"
                page_post = {
                    "__EVENTTARGET": grid_id,
                    "__EVENTARGUMENT": f"Page${page_num}",
                    "__VIEWSTATE": page_form.get("__VIEWSTATE", ""),
                    "__EVENTVALIDATION": page_form.get("__EVENTVALIDATION", ""),
                    "__REQUESTDIGEST": page_form.get("__REQUESTDIGEST", ""),
                    "__VIEWSTATEGENERATOR": page_form.get("__VIEWSTATEGENERATOR", ""),
                    f"{prefix}TrainingPackageDropDownList": pkg_guid,
                    f"{prefix}ModuleUocCheckBox": "on",
                    f"{prefix}OrderByDropDownList": "nationaltitle",
                    f"{prefix}IdentifierTextBox": "",
                    f"{prefix}IncludeSupersededCheckBox": "on",
                    f"{prefix}TitleTextBox": "",
                }
                resp = session.post(_TPS_URL, data=page_post, timeout=60)
                resp.raise_for_status()
                page_results, has_more = _parse_tps_results(resp.text)
                for code, hours in page_results:
                    if hours is not None:
                        mapping[code] = hours

        except Exception as e:
            log.warning("WA TPS: error scraping package %s: %s", pkg_name, e)
            continue

        if bar:
            bar.update(1)
        elif (pkg_idx + 1) % 20 == 0:
            print(f"  • Scraped {pkg_idx + 1}/{len(packages)} packages ({len(mapping)} hours mapped)")

    if bar:
        bar.close()

    return mapping


# ----------------------------
# WA nominal hours load/save/lookup
# ----------------------------

_cached_wa_nominal_hours: Optional[dict[str, int]] = None


def _save_wa_nominal_hours(mapping: dict[str, int], cache_dir: Path) -> None:
    """Save WA nominal hours mapping and meta file."""
    nh_path = _wa_nominal_hours_path(cache_dir)
    nh_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    meta = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "source": _TPS_URL,
        "total_count": len(mapping),
    }
    _wa_nominal_hours_meta_path(cache_dir).write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )


def _load_wa_nominal_hours() -> dict[str, int]:
    """Load WA nominal hours from cache, return empty dict if missing."""
    global _cached_wa_nominal_hours
    if not _NO_CACHE and _cached_wa_nominal_hours is not None:
        return _cached_wa_nominal_hours
    cache_dir = _default_cache_dir()
    nh_path = _wa_nominal_hours_path(cache_dir)
    if not nh_path.exists():
        return {}
    try:
        data = json.loads(nh_path.read_text(encoding="utf-8"))
        _cached_wa_nominal_hours = data
        return data
    except Exception:
        return {}


def _get_wa_nominal_hours(unit_code: str) -> int | None:
    """Look up WA nominal hours for a single unit code."""
    mapping = _load_wa_nominal_hours()
    return mapping.get(unit_code.upper())


# ----------------------------
# UOC content cache (for fast show and global search)
# ----------------------------


def _uoc_content_cache_dir() -> Path:
    base = _default_cache_dir() / "uoc_content"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _uoc_content_cache_path(unit_code: str) -> Path:
    # New default: store as plain text for speed
    return _uoc_content_cache_dir() / f"{unit_code.upper()}.txt"


def _uoc_content_cache_gz_path(unit_code: str) -> Path:
    # Legacy gzip path for backward compatibility
    return _uoc_content_cache_dir() / f"{unit_code.upper()}.txt.gz"


def _load_uoc_content_from_cache(unit_code: str) -> Optional[str]:
    # Prefer plain text
    p_txt = _uoc_content_cache_path(unit_code)
    if not _NO_CACHE and p_txt.exists():
        try:
            return p_txt.read_text(encoding="utf-8")
        except Exception:
            return None
    # Fallback to legacy gzip
    p_gz = _uoc_content_cache_gz_path(unit_code)
    if not _NO_CACHE and p_gz.exists():
        try:
            with gzip.open(p_gz, "rt", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return None
    return None


def _save_uoc_content_to_cache(unit_code: str, content: str) -> None:
    p = _uoc_content_cache_path(unit_code)
    try:
        p.write_text(content, encoding="utf-8")
    except Exception:
        pass


# ----------------------------
# UOC JSON cache (structured data)
# ----------------------------


def _uoc_json_cache_dir() -> Path:
    """Get JSON cache directory for structured UoC data."""
    base = _default_cache_dir() / "uoc_cache" / "json"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _uoc_json_cache_path(unit_code: str) -> Path:
    """Get JSON cache path for a unit code."""
    return _uoc_json_cache_dir() / f"{unit_code.upper()}.json.gz"


def _save_uoc_json_to_cache(
    unit_code: str, data: UnitOfCompetencyData, metadata: dict
) -> None:
    """Save UoC data and metadata to JSON cache."""
    p = _uoc_json_cache_path(unit_code)
    try:
        cache_data = {
            "schema_version": 1,
            "unit_code": unit_code.upper(),
            "aqf_level": data.aqf_level,
            "title": metadata.get("title", ""),
            "training_package": metadata.get("training_package", ""),
            "status": metadata.get("status", "current"),
            "cached_at": metadata.get("cached_at", ""),
            "source": metadata.get("source", {}),
            "sections": data.to_dict(),
        }
        json_str = json.dumps(cache_data, ensure_ascii=False, indent=2)
        with gzip.open(p, "wt", encoding="utf-8") as f:
            f.write(json_str)
    except Exception:
        pass


def _load_uoc_json_from_cache(
    unit_code: str,
) -> Optional[tuple[UnitOfCompetencyData, dict]]:
    """Load UoC data and metadata from JSON cache."""
    if _NO_CACHE:
        return None
    p = _uoc_json_cache_path(unit_code)
    if not p.exists():
        return None
    try:
        with gzip.open(p, "rt", encoding="utf-8") as f:
            cache_data = json.loads(f.read())

        # Extract sections data
        sections_data = cache_data.get("sections", {})
        data = UnitOfCompetencyData.from_dict(sections_data)

        # Extract metadata
        metadata = {
            "title": cache_data.get("title", ""),
            "training_package": cache_data.get("training_package", ""),
            "status": cache_data.get("status", "current"),
            "cached_at": cache_data.get("cached_at", ""),
            "source": cache_data.get("source", {}),
            "schema_version": cache_data.get("schema_version", 1),
        }

        return data, metadata
    except Exception:
        return None


def _build_uoc_content(unit_code: str) -> Optional[str]:
    """Fast-path content fetcher for a unit code using API-only calls.

    Skips accredited units and returns a simple text concatenation suitable for search.
    """
    try:
        idx = _get_nrt_index()
        rec = idx.get(unit_code) if idx else None
        if rec and (
            _is_accredited_record(rec)
            or _is_deleted_record(rec)
            or _is_superseded_record(rec)
        ):
            return None

        api_base = "https://training.gov.au/api/"
        version = "1.0"

        # Determine best/latest release dynamically
        try:
            releases = _list_training_releases(unit_code)
            best_rel = _best_release_number(releases) or "1"
        except Exception:
            best_rel = "1"
        rel_url = (
            f"{api_base}training/{unit_code}/releases/{best_rel}?api-version={version}"
        )
        try:
            r = _fetch_with_retry(rel_url, timeout=20, max_retries=3)
        except requests.HTTPError as e:
            if getattr(e.response, "status_code", None) == 404:
                return None
            raise
        release = r.json() or {}
        bundles = release.get("contentBundles") or []
        if not bundles:
            return None

        parts: list[str] = []
        # Prepend header with title for better context
        title = idx.get_title(unit_code) if idx else ""
        if title:
            parts.append(f"{unit_code} — {title}")
            parts.append("")

        for b in bundles:
            bid = b.get("id")
            if not bid:
                continue
            b_url = f"{api_base}content/bundle/{bid}?api-version={version}"
            try:
                br = _fetch_with_retry(b_url, timeout=20, max_retries=3)
                data = br.json() or {}
                for item in data.get("items", []) or []:
                    it_title = item.get("title")
                    html_content = item.get("content")
                    if not html_content:
                        continue
                    soup = BeautifulSoup(html_content, "html.parser")
                    text = soup.get_text("\n", strip=True)
                    if it_title:
                        parts.append(str(it_title))
                    if text:
                        parts.append(text)
            except Exception:
                continue

        return "\n".join(parts).strip() if parts else None
    except Exception:
        return None


def _build_content_cache_from_index(
    idx: NRTIndex, concurrency: int = 4, limit: Optional[int] = None
) -> int:
    unit_codes: list[str] = []
    for code, rec in idx.by_code.items():
        if (
            "unit" in str(rec.get("type"))
            and not _is_accredited_record(rec)
            and not _is_deleted_record(rec)
            and not _is_superseded_record(rec)
            and is_unit_like_code(code)
        ):
            unit_codes.append(code)
            if limit and len(unit_codes) >= limit:
                break

    if not unit_codes:
        return 0

    total = len(unit_codes)
    bar = None
    if tqdm:
        bar = tqdm(
            total=total, unit="uoc", desc="Caching UOC content", dynamic_ncols=True
        )

    saved = 0

    def work(code: str) -> int:
        # Skip if already cached (check JSON cache first)
        if _uoc_json_cache_path(code).exists():
            return 0
        # Skip if text cache exists but no JSON (legacy)
        if (
            _uoc_content_cache_path(code).exists()
            and not _uoc_json_cache_path(code).exists()
        ):
            # Could do migration here, but for now just skip
            return 0

        # Instantiate UoC (fetches from API, populates data)
        try:
            _ = UnitOfCompetency(code, prefer_cache=False)  # Side effect: caches data
        except Exception:
            return 0

        # Save JSON (already done in __init__ when prefer_cache=False and fetch succeeds)
        # The JSON cache is written automatically in __init__ after API fetch

        # Text is also saved automatically in __init__ after API fetch
        return 1

    if concurrency <= 1:
        for code in unit_codes:
            saved += work(code)
            if bar:
                bar.update(1)
    else:
        with ThreadPoolExecutor(max_workers=max(1, concurrency * 2)) as pool:
            futures = {pool.submit(work, c): c for c in unit_codes}
            for fut in as_completed(futures):
                try:
                    saved += fut.result()
                except Exception:
                    pass
                if bar:
                    bar.update(1)
    if bar:
        bar.close()
    return saved


# ----------------------------
# Qualification content cache (for search/usability)
# ----------------------------


def _qual_content_cache_dir() -> Path:
    base = _default_cache_dir() / "qual_content"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _qual_content_cache_path(qual_code: str) -> Path:
    return _qual_content_cache_dir() / f"{qual_code.upper()}.txt"


def _save_qual_content_to_cache(qual_code: str, content: str) -> None:
    p = _qual_content_cache_path(qual_code)
    try:
        p.write_text(content, encoding="utf-8")
    except Exception:
        pass


def _build_qual_content(qual_code: str) -> Optional[str]:
    """Build a plain-text content snapshot for a qualification code.

    Includes title header, description, entry requirements, packaging rules,
    and a bullet list of units with titles when available.
    """
    try:
        q = Qualification(qual_code)
    except Exception:
        return None

    parts: list[str] = []
    title = q.data.title or q.title or ""
    header = f"{qual_code} — {title}" if title else qual_code
    parts.append(header)
    parts.append("")

    if q.data.description:
        parts.append("Description")
        parts.append(q.data.description)
        parts.append("")

    if q.data.entry_requirements:
        parts.append("Entry requirements")
        parts.append(q.data.entry_requirements)
        parts.append("")

    if q.data.packaging_rules:
        parts.append("Packaging rules")
        parts.append(q.data.packaging_rules)
        parts.append("")

    # Units list (best-effort)
    try:
        units = q.get_units()
    except Exception:
        units = []
    if units:
        parts.append("Units")
        for u in units:
            cid = str(u.get("id") or "").upper()
            nm = str(u.get("title") or "").strip()
            if cid:
                parts.append(f"• {cid} — {nm}" if nm else f"• {cid}")

    return "\n".join(parts)


def _build_qual_content_cache_from_index(
    idx: NRTIndex, concurrency: int = 4, limit: Optional[int] = None
) -> int:
    qual_codes: list[str] = []
    for code, rec in idx.by_code.items():
        if (
            "qualification" in str(rec.get("type"))
            and not _is_deleted_record(rec)
            and not _is_superseded_record(rec)
            and is_course_like_code(code)
        ):
            qual_codes.append(code)
            if limit and len(qual_codes) >= limit:
                break

    if not qual_codes:
        return 0

    total = len(qual_codes)
    bar = None
    if tqdm:
        bar = tqdm(
            total=total, unit="qual", desc="Caching QUAL content", dynamic_ncols=True
        )

    saved = 0

    def work(code: str) -> int:
        if _qual_content_cache_path(code).exists():
            return 0
        text = _build_qual_content(code)
        if text:
            _save_qual_content_to_cache(code, text)
            return 1
        return 0

    if concurrency <= 1:
        for code in qual_codes:
            saved += work(code)
            if bar:
                bar.update(1)
    else:
        with ThreadPoolExecutor(max_workers=max(1, concurrency * 2)) as pool:
            futures = {pool.submit(work, c): c for c in qual_codes}
            for fut in as_completed(futures):
                try:
                    saved += fut.result()
                except Exception:
                    pass
                if bar:
                    bar.update(1)
    if bar:
        bar.close()
    return saved


# Training Package Components (relations)
# ----------------------------


def _tp_components_cache_dir() -> Path:
    base = _default_cache_dir() / "tp_components"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _tp_components_cache_path(pkg_code: str, release: str) -> Path:
    safe_code = pkg_code.upper()
    safe_rel = release.replace("/", "-")
    return _tp_components_cache_dir() / f"{safe_code}_{safe_rel}.json"


def _fetch_tp_components(pkg_code: str, release: str) -> dict:
    url = f"https://training.gov.au/api/training/{pkg_code}/releases/{release}/components?api-version=1.0"
    try:
        resp = _fetch_with_retry(url, timeout=30)
        return resp.json()
    except Exception:
        return {}


def _get_tp_components(
    pkg_code: str, release: Optional[str], force: bool = False
) -> Optional[dict]:
    """Get components for a training package release with cache."""
    if not release:
        # Try to infer from index latestRelease
        idx = _get_nrt_index()
        rel = None
        if idx:
            rec = idx.get(pkg_code)
            if rec:
                lr = rec.get("latestRelease") or {}
                rel = lr.get("number")
        release = rel or "1.0"

    cache_path = _tp_components_cache_path(pkg_code, release)
    if cache_path.exists() and not (force or _NO_CACHE):
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    data = _fetch_tp_components(pkg_code, release)
    if data and not _NO_CACHE:
        try:
            cache_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass
        return data
    return None


def _tp_components_split(
    components_payload: dict,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Split components into (qualifications, skillsets, units)."""
    quals: list[dict] = []
    ssets: list[dict] = []
    units: list[dict] = []

    if not isinstance(components_payload, dict):
        return quals, ssets, units

    # Try common shapes: {"components": [...] } or top-level list under a key
    items = []
    if "components" in components_payload and isinstance(
        components_payload["components"], list
    ):
        items = components_payload["components"]
    elif "value" in components_payload and isinstance(
        components_payload["value"], list
    ):
        items = components_payload["value"]
    elif isinstance(components_payload, list):
        items = components_payload

    for it in items:
        try:
            code = (it.get("code") or it.get("id") or "").upper()
            title = it.get("title") or it.get("name") or ""
            type_info = it.get("type")
            type_str = str(type_info)
            rec = {"id": code, "title": title, "type": type_info}
            if "qualification" in type_str:
                quals.append(rec)
            elif (
                "skillSet" in type_str
                or "Skill set" in type_str
                or "skill set" in type_str
            ):
                ssets.append(rec)
            elif "unit" in type_str:
                units.append(rec)
        except Exception:
            continue
    return quals, ssets, units


# ----------------------------
# Qualification → Units (unitgrid)
# ----------------------------


def _qual_units_cache_dir() -> Path:
    base = _default_cache_dir() / "qual_units"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _qual_units_cache_path(qual_code: str, release: str) -> Path:
    return _qual_units_cache_dir() / f"{qual_code.upper()}_{release}.json"


def _fetch_qual_unitgrid(qual_code: str, release: str) -> dict:
    url = f"https://training.gov.au/api/training/{qual_code}/releases/{release}/unitgrid?api-version=1.0"
    try:
        resp = _fetch_with_retry(url, timeout=30)
        return resp.json()
    except Exception:
        return {}


def _parse_unitgrid(payload: dict) -> list[dict]:
    """Parse unitgrid payload into list of {id, title} dicts.

    Handles common shapes with generous key matching.
    """
    results: list[dict] = []
    if not payload:
        return results
    rows = []
    if isinstance(payload, dict):
        if isinstance(payload.get("rows"), list):
            rows = payload["rows"]
        elif isinstance(payload.get("data"), list):
            rows = payload["data"]
        elif isinstance(payload.get("value"), list):
            rows = payload["value"]
        elif isinstance(payload.get("items"), list):
            rows = payload["items"]
    elif isinstance(payload, list):
        rows = payload

    for r in rows:
        try:
            # Try various likely keys
            code = (
                r.get("code")
                or r.get("unitCode")
                or r.get("UnitCode")
                or r.get("id")
                or ""
            )
            title = (
                r.get("title")
                or r.get("unitTitle")
                or r.get("UnitTitle")
                or r.get("name")
                or ""
            )
            code = str(code).strip().upper()
            if code:
                results.append({"id": code, "title": str(title).strip()})
        except Exception:
            continue
    # De-duplicate preserving order
    seen: set[str] = set()
    deduped: list[dict] = []
    for it in results:
        if it["id"] in seen:
            continue
        seen.add(it["id"])
        deduped.append(it)
    return deduped


def _get_qual_units(
    qual_code: str, release: Optional[str], force: bool = False
) -> list[dict]:
    """Get units for a qualification via unitgrid, with cache and release inference."""
    # Infer release if not provided
    if not release:
        idx = _get_nrt_index()
        rel = None
        if idx:
            rec = idx.get(qual_code)
            if rec:
                lr = rec.get("latestRelease") or {}
                rel = lr.get("number")
        release = rel or "1.0"

    cache_path = _qual_units_cache_path(qual_code, release)
    if cache_path.exists() and not (force or _NO_CACHE):
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            return _parse_unitgrid(payload)
        except Exception:
            pass

    payload = _fetch_qual_unitgrid(qual_code, release)
    if payload and not _NO_CACHE:
        try:
            cache_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass
        return _parse_unitgrid(payload)
    return []


# ----------------------------
# Unit → Usage (quals/skill sets that include the unit)
# ----------------------------


def _unit_usage_cache_dir() -> Path:
    base = _default_cache_dir() / "unit_usage"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _unit_usage_cache_path(unit_code: str) -> Path:
    return _unit_usage_cache_dir() / f"{unit_code.upper()}.json"


def _fetch_unit_usage(unit_code: str) -> list[dict]:
    url = f"https://training.gov.au/api/training/{unit_code}/unitgridusage?api-version=1.0"
    try:
        resp = _fetch_with_retry(url, timeout=30)
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _get_unit_usage(unit_code: str, force: bool = False) -> list[dict]:
    cache_path = _unit_usage_cache_path(unit_code)
    if cache_path.exists() and not force:
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    data = _fetch_unit_usage(unit_code)
    if data:
        try:
            cache_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass
    return data


@app.command()
def index_info(
    index_path: Optional[str] = typer.Option(
        None, "--index-path", help="Path to local NRT index (jsonl.gz)"
    ),
    counts: bool = typer.Option(
        True, "--counts/--no-counts", help="Show counts by type and total"
    ),
):
    """
    Show information about the local NRT index and its metadata.
    """
    path = _resolve_index_path(index_path)
    meta = _meta_path(_default_cache_dir())
    print(f"Index: {path}")
    print(f"Meta:  {meta}")
    if meta.exists():
        try:
            m = json.loads(meta.read_text(encoding="utf-8"))
            print(f"  last_updated: {m.get('last_updated')}")
            print(f"  total_count (recorded): {m.get('total_count')}")
        except Exception:
            pass
    if not counts or not path.exists():
        return
    total = 0
    type_counts: dict[str, int] = {}
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                total += 1
                try:
                    rec = json.loads(line)
                    record_type = str(rec.get("type", "")).strip() or "UNKNOWN"
                    type_counts[record_type] = type_counts.get(record_type, 0) + 1
                except Exception:
                    continue
        print(f"  total_count (scanned): {total}")
        if type_counts:
            print("  by_type:")
            for t, c in sorted(type_counts.items(), key=lambda x: (-x[1], x[0])):
                print(f"    - {t}: {c}")
    except Exception as e:
        print(f"❌ Error reading index: {e}")

    # WA nominal hours cache info
    cache_dir = _default_cache_dir()
    wa_path = _wa_nominal_hours_path(cache_dir)
    wa_meta = _wa_nominal_hours_meta_path(cache_dir)
    print(f"\nWA Nominal Hours: {wa_path}")
    if wa_meta.exists():
        try:
            wm = json.loads(wa_meta.read_text(encoding="utf-8"))
            print(f"  last_updated: {wm.get('last_updated')}")
            print(f"  total_count: {wm.get('total_count')}")
        except Exception:
            pass
    elif not wa_path.exists():
        print("  (not built — run 'uoc wa-index' to build)")


@app.command()
def index_search(
    query: str = typer.Argument(..., help="Substring to search in code or title"),
    index_path: Optional[str] = typer.Option(
        None, "--index-path", help="Path to local NRT index (jsonl.gz)"
    ),
    limit: int = typer.Option(20, "--limit", "-n", help="Max results to show"),
):
    """
    Search the local NRT index by substring in code or title.
    """
    path = _resolve_index_path(index_path)
    if not path.exists():
        print(f"❌ Index not found: {path}")
        raise typer.Exit(1)
    q = query.lower()
    shown = 0
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                code = str(rec.get("code", ""))
                title = str(rec.get("title", ""))
                if q in code.lower() or q in title.lower():
                    print(f"{code} — {title} [{rec.get('type')}]")
                    shown += 1
                    if shown >= limit:
                        break
        if shown == 0:
            print("(no matches)")
    except Exception as e:
        print(f"❌ Error searching index: {e}")


# If there is an error in the underlying html formatting then we have to explicitly add the element so it renders properly


def next_tag(element: Tag) -> Tag:
    try:
        return next(filter(lambda e: isinstance(e, Tag), element.next_siblings))
    except StopIteration:
        return None


def previous_tag(element: Tag) -> Tag:
    try:
        return next(filter(lambda e: isinstance(e, Tag), element.previous_siblings))
    except StopIteration:
        return None


## Helper Functions
def unpack_soup(soup: BeautifulSoup, recursion_count: int = 0) -> dict[str, list[str]]:
    """
    Unpack a nested ul element into a dictionary.
    """
    # Define a base case for recursion and a recursion limit to prevent stack overflow
    if (
        not soup
        or not hasattr(soup, "name")
        or soup.name != "ul"
        or recursion_count > 10
    ):
        return {}

    unpacked = {}
    for element in soup:
        if hasattr(element, "name") and element.name == "li":
            for child in element.children:
                next_tag_child = next_tag(child)
                if (
                    isinstance(child, NavigableString)
                    and next_tag_child
                    and hasattr(next_tag_child, "name")
                    and next_tag_child.name == "ul"
                ):
                    key = child.string
                    unpacked[key] = unpack_soup(next_tag_child, recursion_count + 1)
                    continue
                if (
                    hasattr(child, "string")
                    and child.string
                    and child.string in EXCEPTIONS.keys()
                    and EXCEPTIONS[child.string] in unpacked.keys()
                ):
                    unpacked[EXCEPTIONS[child.string]][child.string] = {}
                    continue
                if isinstance(child, NavigableString) and child.string:
                    key = child.string
                    unpacked[key] = {}
    return unpacked


EXCEPTIONS = {
    "clustering algorithms": "key algorithms used to run unlabelled data, including:",
    "association algorithms": "key algorithms used to run unlabelled data, including:",
    "neural network algorithms": "key algorithms used to run unlabelled data, including:",
}


class UOCSections(Enum):
    """
    Enumeration representing different sections of a Unit of Competency.
    """

    MODIFICATION_HISTORY = "Modification history"
    APPLICATION = "Application"
    PERFORMANCE_EVIDENCE = "Performance evidence"
    KNOWLEDGE_EVIDENCE = "Knowledge evidence"
    ELEMENTS_AND_CRITERIA = "Elements and performance criteria"
    ASSESSMENT_CONDITIONS = "Assessment conditions"
    UNIT_SECTOR = "Unit sector"

    @property
    def attribute_name(self) -> str:
        """
        Convert enum value to snake_case to use it as an attribute name.
        """
        return self.name.lower()


@dataclass
class UnitOfCompetencyData:
    """
    Data class representing the extracted information from a Unit of Competency.
    """

    unit_code: str
    aqf_level: int
    modification_history: str = ""
    application: str = ""
    performance_evidence: dict[str, list[str]] = field(default_factory=dict)
    performance_skills: dict[str, list[str]] = field(default_factory=dict)
    knowledge_evidence: dict[str, list[str]] = field(default_factory=dict)
    elements_and_criteria: dict[str, str] = field(default_factory=dict)
    assessment_conditions: dict[str, list[str]] = field(default_factory=dict)
    unit_sector: str = ""

    def __str__(self) -> str:
        return f"{self.unit_code} - {self.aqf_level}"

    def to_dict(self) -> dict:
        """Serialize data to a dictionary suitable for JSON storage."""
        return {
            "unit_code": self.unit_code,
            "aqf_level": self.aqf_level,
            "modification_history": self.modification_history,
            "application": self.application,
            "performance_evidence": self.performance_evidence,
            "performance_skills": self.performance_skills,
            "knowledge_evidence": self.knowledge_evidence,
            "elements_and_criteria": self.elements_and_criteria,
            "assessment_conditions": self.assessment_conditions,
            "unit_sector": self.unit_sector,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UnitOfCompetencyData":
        """Deserialize from a dictionary (e.g., from JSON cache)."""
        return cls(
            unit_code=data.get("unit_code", ""),
            aqf_level=data.get("aqf_level", 0),
            modification_history=data.get("modification_history", ""),
            application=data.get("application", ""),
            performance_evidence=data.get("performance_evidence", {}),
            performance_skills=data.get("performance_skills", {}),
            knowledge_evidence=data.get("knowledge_evidence", {}),
            elements_and_criteria=data.get("elements_and_criteria", {}),
            assessment_conditions=data.get("assessment_conditions", {}),
            unit_sector=data.get("unit_sector", ""),
        )


class UnitOfCompetencyError(requests.HTTPError):
    """Base class for all errors in this module"""


class UnitOfCompetencyNotFoundError(UnitOfCompetencyError):
    """Raised when a unit of competency cannot be found"""

    def __init__(self, unit_code: str):
        self.unit_code = unit_code
        self.message = f"Unit of competency {unit_code} not found"
        super().__init__(self.message)


class UnitOfCompetency:
    """
    Class representing a Unit of Competency from training.gov.au.
    Responsible for fetching and parsing relevant data using the API.
    """

    base_url = "https://training.gov.au/"
    api_url = "https://training.gov.au/api/"
    api_version = "1.0"

    def __init__(
        self,
        unit_code: str,
        sections: Iterable[UOCSections] = UOCSections,
        prefer_cache: bool = True,
    ):
        # Extract AQF level from unit code (also validates unit code)
        match = re.search(r"\d", unit_code)
        if not match:
            raise UnitOfCompetencyError(f"Invalid unit code {unit_code}")
        self.aqf_level = int(match.group())
        self.unit_code = unit_code
        self.sections = sections
        self.title = ""
        self._cached_text: Optional[str] = None

        # Initialize variables
        self.application = ""
        self.performance_evidence = {}
        self.performance_skills = {}
        self.knowledge_evidence = {}
        self.elements_and_criteria = {}
        self.assessment_conditions = {}
        self.modification_history = ""
        self.unit_sector = ""

        # Prefer initializing from local cached content when available
        initialized_from_cache = False
        if prefer_cache:
            # Try JSON cache first
            json_data = _load_uoc_json_from_cache(self.unit_code)
            if json_data:
                self.data, metadata = json_data
                self.title = metadata.get("title", "")
                # Populate instance attributes from data
                self.application = self.data.application
                self.performance_evidence = self.data.performance_evidence
                self.performance_skills = self.data.performance_skills
                self.knowledge_evidence = self.data.knowledge_evidence
                self.elements_and_criteria = self.data.elements_and_criteria
                self.assessment_conditions = self.data.assessment_conditions
                self.modification_history = self.data.modification_history
                self.unit_sector = self.data.unit_sector
                # Optionally load text for __str__ fast-path
                self._cached_text = _load_uoc_content_from_cache(self.unit_code)
                initialized_from_cache = True
            else:
                # Fallback to text-only (legacy)
                try:
                    cached = _load_uoc_content_from_cache(self.unit_code)
                except Exception:
                    cached = None
                if cached:
                    self._cached_text = cached
                    # Minimal data scaffold so attributes exist
                    self.data = UnitOfCompetencyData(
                        unit_code=self.unit_code,
                        aqf_level=self.aqf_level,
                    )
                    try:
                        idx = _get_nrt_index()
                        if idx:
                            self.title = idx.get_title(self.unit_code) or ""
                    except Exception:
                        pass
                    initialized_from_cache = True

        if not initialized_from_cache:
            # Fetch and process data from API
            self.data = self._get_data()
            self.title = self._get_title()
            # Write to JSON cache
            if not _NO_CACHE:
                # Get training package from unit code
                training_package = ""
                if len(self.unit_code) >= 3:
                    training_package = (
                        re.match(r"^[A-Z]+", self.unit_code).group()
                        if re.match(r"^[A-Z]+", self.unit_code)
                        else ""
                    )

                metadata = {
                    "title": self.title,
                    "training_package": training_package,
                    "status": "current",
                    "cached_at": datetime.now(timezone.utc).isoformat(),
                    "source": {
                        "release": "1",  # TODO: get actual release number
                        "url": f"{self.base_url}training/details/{self.unit_code}",
                    },
                }
                _save_uoc_json_to_cache(self.unit_code, self.data, metadata)
                # Also save text representation
                text = str(self)
                _save_uoc_content_to_cache(self.unit_code, text)

    def get_related_courses(self) -> list[dict[str, str]]:
        """Best-effort extraction of related courses/qualifications containing this unit.

        Strategy:
        - Fetch the public details page and search for codes that look like qualifications/skill sets
        - Try to pick up anchor text as titles when available
        - De-duplicate results
        """
        candidates = [
            f"{self.base_url}training/{self.unit_code}/unitdetails",
            f"{self.base_url}training/details/{self.unit_code}",
        ]

        found: dict[str, str] = {}
        for url in candidates:
            try:
                resp = _fetch_with_retry(url, timeout=30, max_retries=2)
            except Exception:
                continue

            soup = BeautifulSoup(resp.content, "html.parser")
            # Prefer anchors with clear hrefs to courses
            for a in soup.find_all("a", href=True):
                href = a["href"]
                # Normalize relative URLs
                text = a.get_text(strip=True)
                # Try to extract a code-looking token from href or text
                code_match = (
                    _COURSE_CODE_RE.search(href)
                    or _COURSE_CODE_RE.search(text)
                    or _SKILLSET_CODE_RE.search(href)
                    or _SKILLSET_CODE_RE.search(text)
                )
                if not code_match:
                    # Sometimes hrefs are like /training/ICT40120 or have query params
                    if "/training/" in href:
                        tail = href.split("/training/")[-1]
                        tail = re.split(r"[/?#]", tail)[0]
                        if is_course_like_code(tail):
                            code_match = re.match(r".+", tail)
                if code_match:
                    code = code_match.group(0)
                    if code not in found:
                        # Use anchor text if it contains more than just the code; otherwise empty for now
                        title = text if (text and code not in text) else ""
                        found[code] = title

            # If we already found some, stop early
            if found:
                break

        # Optionally, try to enrich missing titles by visiting qualification pages header
        enriched: list[dict[str, str]] = []
        for code, title in found.items():
            if title:
                enriched.append({"id": code, "title": title})
                continue
            try:
                q = Qualification(code)
                enriched.append({"id": code, "title": q.title or ""})
            except Exception:
                enriched.append({"id": code, "title": title})

        # Stable sort by code
        enriched.sort(key=lambda x: x["id"])
        return enriched

    def _get_data(self) -> UnitOfCompetencyData:
        try:
            release_info = self._fetch_release_info()
            content_bundles = release_info.get("contentBundles", [])
            for bundle in content_bundles:
                bundle_id = bundle["id"]
                # Fetch the content of the bundle
                bundle_content = self._fetch_bundle_content(bundle_id)
                # Process the content to extract sections
                self._process_bundle_content(bundle_content)
            return UnitOfCompetencyData(
                unit_code=self.unit_code,
                aqf_level=self.aqf_level,
                application=self.application,
                performance_evidence=self.performance_evidence,
                performance_skills=self.performance_skills,
                knowledge_evidence=self.knowledge_evidence,
                elements_and_criteria=self.elements_and_criteria,
                assessment_conditions=self.assessment_conditions,
                modification_history=self.modification_history,
                unit_sector=self.unit_sector,
            )
        except Exception as e:
            raise UnitOfCompetencyError(
                f"Error fetching data for unit {self.unit_code}: {e}"
            )

    def _get_title(self) -> str:
        # Prefer NRT index title to avoid HTML parsing
        try:
            idx = _get_nrt_index()
            if idx:
                title = idx.get_title(self.unit_code)
                if title:
                    return title
        except Exception:
            pass

        # Fallback to HTML parsing if not found in index
        url = f"{self.base_url}training/{self.unit_code}/unitdetails"
        log.debug(f"Fetching title from {url}")
        try:
            response = _fetch_with_retry(url, timeout=30, max_retries=3)

            from lxml import html

            tree = html.fromstring(response.content)
            xpath_candidates = [
                "//*[@id='content']/div/div/div/div[2]/div/div/div[1]/div/div/div[1]/div[2]/div[1]/span[1]",
                "//*[@id='content']//h1/text()",
                "//h1/text()",
                "//*[@id='content']//span[@class='page-title']/text()",
            ]
            for xp in xpath_candidates:
                matches = [t.strip() for t in tree.xpath(xp) if t.strip()]
                if matches:
                    return matches[0]
            return ""
        except Exception as e:
            log.error(f"Error fetching title for {self.unit_code}: {e}")
            return ""

    def _fetch_release_info(self) -> dict:
        # https://training.gov.au/api/training/ICTPRG302/releases/1?api-version=1.0

        # Prefer best/latest release number from list endpoint
        try:
            releases = _list_training_releases(self.unit_code)
            best_rel = _best_release_number(releases) or "1"
        except Exception:
            best_rel = "1"
        url = f"{self.api_url}training/{self.unit_code}/releases/{best_rel}?api-version={self.api_version}"
        log.debug(f"Fetching release info from {url}")
        try:
            response = _fetch_with_retry(url, timeout=30)
            return response.json()
        except requests.exceptions.HTTPError as e:
            logging.error(f"Failed to fetch release info {url}: {e}")
            raise UnitOfCompetencyNotFoundError(self.unit_code) from e

    def _fetch_bundle_content(self, bundle_id: str) -> dict:
        url = f"{self.api_url}content/bundle/{bundle_id}?api-version={self.api_version}"
        log.debug(f"Fetching bundle content from {url}")
        try:
            response = _fetch_with_retry(url, timeout=30)
            return response.json()
        except requests.exceptions.HTTPError as e:
            logging.error(f"Failed to fetch bundle content {url}: {e}")
            raise UnitOfCompetencyError(f"Error fetching bundle content: {e}")

    def _process_bundle_content(self, bundle_content: dict):
        items = bundle_content.get("items", [])
        for item in items:
            title = item.get("title")
            content = item.get("content")

            if not content:
                continue  # Skip if there's no content

            try:
                # Parse content with BeautifulSoup
                soup = BeautifulSoup(content, "html.parser")

                if title == UOCSections.MODIFICATION_HISTORY.value:
                    self.modification_history = soup.get_text(strip=True)
                elif title == UOCSections.APPLICATION.value:
                    self.application = soup.get_text(strip=True)
                elif title == UOCSections.PERFORMANCE_EVIDENCE.value:
                    self.performance_evidence, self.performance_skills = (
                        self._parse_performance_evidence(soup)
                    )
                elif title == UOCSections.KNOWLEDGE_EVIDENCE.value:
                    self.knowledge_evidence = self._parse_knowledge_evidence(soup)
                elif title == UOCSections.ELEMENTS_AND_CRITERIA.value:
                    self.elements_and_criteria = self._parse_elements_and_criteria(soup)
                elif title == UOCSections.ASSESSMENT_CONDITIONS.value:
                    self.assessment_conditions = self._parse_assessment_conditions(soup)
                elif title == UOCSections.UNIT_SECTOR.value:
                    self.unit_sector = soup.get_text(strip=True)
                else:
                    # Handle other sections or ignore
                    log.debug(f"Ignoring unrecognized section: {title}")
            except Exception as e:
                log.error(f"Error parsing section '{title}': {e}")
                # For debugging, let's continue with other sections instead of failing completely
                continue

    def _parse_assessment_conditions(self, soup: BeautifulSoup) -> Dict[str, List[str]]:
        assessment_conditions = {}  # Dictionary to store the elements and sub-points

        # Check if soup.div exists and is not None
        if not soup.div:
            log.warning("No div element found in assessment conditions section")
            return assessment_conditions

        for element in filter(lambda e: isinstance(e, Tag), soup.div):
            next_tag_element = next_tag(element)
            if (
                element.name == "p"
                and len(element.text) > 0
                and next_tag_element
                and next_tag_element.name == "ul"
            ):
                assessment_conditions[element.text] = unpack_soup(next_tag_element)
                continue
            if element.name == "p" and len(element.text) > 0:
                assessment_conditions[element.text] = {}
                continue

        return assessment_conditions

    def _parse_performance_evidence(
        self, soup: BeautifulSoup
    ) -> tuple[Dict[str, List[str]], Dict[str, List[str]]]:
        performance_evidence = {}  # Dictionary to store the main performance evidence
        performance_skills = {}  # Dictionary to store the performance skills

        # Check if soup.div exists and is not None
        if not soup.div:
            log.warning("No div element found in performance evidence section")
            return performance_evidence, performance_skills

        is_skills_section = False  # Track whether we're in the skills section
        elements = list(filter(lambda e: isinstance(e, Tag), soup.div))

        for i, element in enumerate(elements):
            # Check if this paragraph indicates the start of the skills section
            if (
                element.name == "p"
                and "In the course of the above, the candidate must:" in element.text
            ):
                is_skills_section = True
                # The next element should be a ul with the skills
                if i + 1 < len(elements) and elements[i + 1].name == "ul":
                    performance_skills[element.text] = unpack_soup(elements[i + 1])
                else:
                    performance_skills[element.text] = {}
                continue

            # Handle ul elements that follow skills section paragraph
            if element.name == "ul" and is_skills_section:
                # This ul is already handled above when we found the skills section paragraph
                continue

            next_tag_element = next_tag(element)

            if (
                element.name == "p"
                and len(element.text) > 0
                and next_tag_element
                and next_tag_element.name == "ul"
                and not is_skills_section  # Only for performance evidence, not skills
            ):
                performance_evidence[element.text] = unpack_soup(next_tag_element)
                continue

            if element.name == "p" and len(element.text) > 0 and not is_skills_section:
                performance_evidence[element.text] = {}
                continue

        return performance_evidence, performance_skills

    def _parse_knowledge_evidence(self, soup: BeautifulSoup) -> Dict[str, List[str]]:
        """
        Parse the 'Knowledge Evidence' section of a Unit of Competency.
        """
        knowledge_evidence = {}  # Dictionary to store the elements and sub-points

        # Check if soup.div exists and is not None
        if not soup.div:
            log.warning("No div element found in knowledge evidence section")
            return knowledge_evidence

        for element in filter(lambda e: isinstance(e, Tag), soup.div):
            next_tag_element = next_tag(element)
            if (
                element.name == "p"
                and len(element.text) > 0
                and next_tag_element
                and next_tag_element.name == "ul"
            ):
                knowledge_evidence[element.text] = unpack_soup(next_tag_element)
                continue
            # elif element.name == "ul":
            #     performance_evidence.update(unpack_soup(element))
            if element.name == "p" and len(element.text) > 0:
                knowledge_evidence[element.text] = {}
                continue

        return knowledge_evidence

    def _parse_elements_and_criteria(self, soup: BeautifulSoup) -> Dict[str, str]:
        """
        Parse the 'Elements and Criteria' section of a Unit of Competency.
        """
        # Assuming content is in a structured format like HTML with a table
        elements = {}
        table = soup.find("table")
        if not table:
            return elements

        rows = table.find_all("tr")
        for row in rows[2:]:  # Skip header row
            cols = row.find_all("td")
            if len(cols) >= 2:
                element = cols[0].get_text(strip=True)
                criteria = unpack_soup(cols[1].ul)
                elements[element] = criteria
        return elements

    def __str__(self) -> str:
        # If we have cached text, return it directly for fastest rendering
        if getattr(self, "_cached_text", None):
            return str(self._cached_text)
        # Include code and title as part of the content output
        header_lines: List[str] = []
        try:
            idx = _get_nrt_index()
        except Exception:
            idx = None
        resolved_title = self.title or (idx.get_title(self.unit_code) if idx else "")
        if resolved_title:
            header_lines.append(f"{self.unit_code} — {resolved_title}")
            header_lines.append("")

        # Width-aware wrapper preserving indentation and bullets
        import shutil as _shutil
        import textwrap as _textwrap

        term_width = _shutil.get_terminal_size((100, 20)).columns

        def _wrap_preserve_indent(text: str) -> str:
            lines_in = text.splitlines()
            out: list[str] = []
            width = max(60, min(term_width, 100))
            for ln in lines_in:
                if not ln.strip():
                    out.append(ln)
                    continue
                # Detect indentation and bullet prefix
                rest = ln
                # Count leading spaces
                leading_spaces = len(ln) - len(ln.lstrip(" "))
                indent_str = " " * leading_spaces
                rest = ln[leading_spaces:]
                bullet_prefix = ""
                for bp in ["- ", "• ", "* ", "— "]:
                    if rest.startswith(bp):
                        bullet_prefix = bp
                        rest = rest[len(bp) :]
                        break
                initial = indent_str + (bullet_prefix if bullet_prefix else "")
                subsequent = indent_str + ("  " if bullet_prefix else "")
                filled = _textwrap.fill(
                    rest,
                    width=width,
                    initial_indent=initial,
                    subsequent_indent=subsequent,
                    replace_whitespace=False,
                )
                out.append(filled)
            return "\n".join(out)

        def format_nested(
            value: Any, indent_level: int = 0, bullet_for_level0_keys: bool = True
        ) -> str:
            indent = "  " * indent_level
            lines: List[str] = []

            if isinstance(value, dict):
                for key, sub in value.items():
                    # Treat empty/None keys as container-only: no heading/bullet, inline children
                    if key is None or (isinstance(key, str) and key.strip() == ""):
                        if isinstance(sub, (dict, list)):
                            lines.append(
                                format_nested(sub, indent_level, bullet_for_level0_keys)
                            )
                        else:
                            lines.append(f"{indent}{sub}")
                        continue

                    if indent_level == 0 and not bullet_for_level0_keys:
                        heading_line = f"{indent}{key}"
                        lines.append(heading_line)
                    else:
                        lines.append(f"{indent}- {key}")

                    if isinstance(sub, (dict, list)) and sub:
                        lines.append(format_nested(sub, indent_level + 1, True))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, (dict, list)):
                        lines.append(format_nested(item, indent_level, True))
                    else:
                        lines.append(f"{indent}- {item}")
            else:
                lines.append(f"{indent}{value}")

            return "\n".join(lines)

        def split_knowledge_preamble(value: Any) -> tuple[list[str], Any]:
            if not isinstance(value, dict) or not value:
                return [], value

            preamble_patterns = [
                r"^The candidate must.*knowledge.*",
                r"^The candidate must be able to demonstrate knowledge.*",
                r".*including knowledge of.*",
                r".*This includes knowledge of.*",
            ]

            def is_preamble(text: str) -> bool:
                return any(
                    re.search(pat, text, re.IGNORECASE) for pat in preamble_patterns
                )

            preamble_lines: list[str] = []
            remaining: dict[str, Any] = {}

            if len(value) == 1:
                only_key = next(iter(value.keys()))
                if isinstance(only_key, str) and is_preamble(only_key):
                    preamble_lines.append(only_key)
                    return preamble_lines, value[only_key]

            for k, v in value.items():
                if isinstance(k, str) and is_preamble(k):
                    preamble_lines.append(k)
                    if isinstance(v, dict):
                        for ck, cv in v.items():
                            remaining[ck] = cv
                    elif isinstance(v, list):
                        # Inline list without adding an artificial heading
                        remaining[""] = v
                else:
                    remaining[k] = v

            return preamble_lines, (remaining if remaining else value)

        def split_performance_preamble(value: Any) -> tuple[list[str], Any]:
            if not isinstance(value, dict) or not value:
                return [], value

            preamble_patterns = [
                r"^The candidate must.*complete the tasks.*",
                r"^The candidate must demonstrate the ability.*",
                r".*including evidence of the ability.*",
            ]

            def is_preamble(text: str) -> bool:
                return any(
                    re.search(pat, text, re.IGNORECASE) for pat in preamble_patterns
                )

            preamble_lines: list[str] = []
            remaining: dict[str, Any] = {}

            if len(value) == 1:
                only_key = next(iter(value.keys()))
                if isinstance(only_key, str) and is_preamble(only_key):
                    preamble_lines.append(only_key)
                    return preamble_lines, value[only_key]

            for k, v in value.items():
                if isinstance(k, str) and is_preamble(k):
                    preamble_lines.append(k)
                    if isinstance(v, dict):
                        for ck, cv in v.items():
                            remaining[ck] = cv
                    elif isinstance(v, list):
                        remaining[""] = v
                else:
                    remaining[k] = v

            return preamble_lines, (remaining if remaining else value)

        sections_strings = []
        seen_sections: set[UOCSections] = set()

        for section in self.sections:
            attr_name = section.attribute_name
            value = getattr(self.data, attr_name)
            if value and section not in seen_sections:
                if isinstance(value, (dict, list)):
                    if section == UOCSections.KNOWLEDGE_EVIDENCE:
                        preamble, content = split_knowledge_preamble(value)
                        section_lines: List[str] = [f"{section.value}"]
                        if preamble:
                            section_lines.extend(preamble)
                        if content:
                            formatted = format_nested(content, 0, True)
                            if formatted:
                                section_lines.append(formatted)
                        section_string = "\n".join(section_lines)
                    elif section == UOCSections.ELEMENTS_AND_CRITERIA:
                        section_string = f"{section.value}\n" + format_nested(
                            value, 0, False
                        )
                    elif section == UOCSections.PERFORMANCE_EVIDENCE:
                        preamble, content = split_performance_preamble(value)
                        section_lines = [f"{section.value}"]
                        if preamble:
                            section_lines.extend(preamble)
                        if content:
                            formatted = format_nested(content, 0, True)
                            if formatted:
                                section_lines.append(formatted)
                        section_string = "\n".join(section_lines)
                    elif section == UOCSections.ASSESSMENT_CONDITIONS:
                        # Print top-level paragraphs as plain headings (no bullet), bullets for nested lists
                        section_string = f"{section.value}\n" + format_nested(
                            value, 0, False
                        )
                    else:
                        section_string = f"{section.value}\n" + format_nested(
                            value, 0, True
                        )
                else:
                    section_string = f"{section.value}\n{value}"
                # Wrap and record
                sections_strings.append(_wrap_preserve_indent(section_string))
                seen_sections.add(section)

        body = "\n\n".join(sections_strings)
        if header_lines:
            return "\n".join(header_lines + [body]) if body else "\n".join(header_lines)
        return body

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        return f"{class_name}({self.unit_code!r}, {self.sections!r})"


class Qualification:
    """Represents a Qualification/Accredited Course/Skill Set on training.gov.au.

    Provides best-effort course title and unit listing via API+HTML fallbacks.
    """

    base_url = "https://training.gov.au/"
    api_url = "https://training.gov.au/api/"
    api_version = "1.0"

    def __init__(self, course_code: str):
        if not is_course_like_code(course_code):
            raise UnitOfCompetencyError(
                f"Invalid course/qualification code {course_code}"
            )
        self.course_code = course_code
        self.title = self._get_title()
        # Enriched data
        self.data: QualificationData = self._load_data()

    def _get_title(self) -> str:
        # Prefer NRT index title to avoid HTML parsing
        try:
            idx = _get_nrt_index()
            if idx:
                title = idx.get_title(self.course_code)
                if title:
                    return title
        except Exception:
            pass

        # Fallback to HTML parsing
        candidates = [
            f"{self.base_url}training/{self.course_code}/qualificationdetails",
            f"{self.base_url}training/{self.course_code}/coursedetails",
            f"{self.base_url}training/details/{self.course_code}",
            f"{self.base_url}training/{self.course_code}",
        ]
        for url in candidates:
            try:
                response = _fetch_with_retry(url, timeout=30, max_retries=2)
                from lxml import html

                tree = html.fromstring(response.content)
                xpath_candidates = [
                    "//*[@id='content']//h1/text()",
                    "//h1/text()",
                    "//*[@id='content']//span[@class='page-title']/text()",
                ]
                for xp in xpath_candidates:
                    matches = [
                        t.strip()
                        for t in tree.xpath(xp)
                        if isinstance(t, str) and t.strip()
                    ]
                    if matches:
                        return matches[0]
            except Exception:
                continue
        return ""

    def _fetch_release_info(self) -> dict:
        # Resolve best/latest release via list endpoint, fallback to 1
        try:
            releases = _list_training_releases(self.course_code)
            best_rel = _best_release_number(releases) or "1"
        except Exception:
            best_rel = "1"
        url = (
            f"{self.api_url}training/{self.course_code}/releases/{best_rel}"
            f"?include=All&api-version={self.api_version}"
        )
        log.debug(f"Fetching course release info from {url}")
        try:
            response = _fetch_with_retry(url, timeout=30)
            data = response.json()
            return data if isinstance(data, dict) else {}
        except Exception as e:
            logging.warning(f"Failed to fetch course release info {url}: {e}")
            return {}

    def _load_data(self) -> QualificationData:
        # Try cached release first (latest seen is often 4, but we don't assume it exists)
        release_meta = self._fetch_release_info()
        rel_num = str(release_meta.get("releaseNumber") or "")
        rel_date = str(release_meta.get("releaseDate") or "")
        currency = str(release_meta.get("currency") or "")
        assets = release_meta.get("assets") or []
        external_links = release_meta.get("externalLinks") or []
        specialisations = (
            release_meta.get("specializations")
            or release_meta.get("specialisations")
            or []
        )

        # Follow content bundle link to get items (mod history, description, entry req, packaging rules)
        description = ""
        entry_req = ""
        packaging_rules = ""
        try:
            # Prefer explicit bundle id for a full bundle fetch (no itemType filters)
            bundle_href = None
            bundles = release_meta.get("contentBundles") or []
            if bundles:
                bid = bundles[0].get("id")
                if bid:
                    bundle_href = f"https://training.gov.au/api/content/bundle/{bid}"
            # Fallback: try to derive bundle id from links
            if not bundle_href:
                for link in release_meta.get("links") or []:
                    href = str(link.get("href") or "")
                    if "/api/content/bundle/" in href:
                        # Trim query params to avoid filtered views
                        bundle_href = href.split("?")[0]
                        break
            if bundle_href:
                # Ensure api-version parameter
                if "?" in bundle_href:
                    bundle_url = bundle_href
                else:
                    bundle_url = f"{bundle_href}?api-version={self.api_version}"
                bundle = _fetch_json(bundle_url)
                for item in bundle.get("items", []) or []:
                    ctype = str(item.get("contentType") or "")
                    title = str(item.get("title") or "")
                    content = str(item.get("content") or "")
                    text = _html_to_text(content)
                    norm_title = title.strip().lower()
                    if (
                        ctype == "Description"
                        or norm_title == "qualification description"
                    ):
                        description = text
                    elif (
                        ctype == "EntryRequirements"
                        or norm_title == "entry requirements"
                    ):
                        entry_req = text
                    elif (
                        ctype == "PackagingRules"
                        or norm_title == "packaging rules"
                        or "packaging rules" in norm_title
                    ):
                        # Some bundles label via title rather than contentType
                        packaging_rules = (
                            text
                            if not packaging_rules
                            else f"{packaging_rules}\n\n{text}"
                        )
        except Exception:
            pass

        return QualificationData(
            course_code=self.course_code,
            title=self.title,
            currency=currency,
            release_number=rel_num,
            release_date=rel_date,
            assets=assets,
            external_links=external_links,
            specialisations=specialisations,
            description=description,
            entry_requirements=entry_req,
            packaging_rules=packaging_rules,
        )

    def get_units(self) -> list[dict[str, str]]:
        """Return list of units in this course as dicts with id and title when available.

        Tries API first; falls back to parsing HTML for unit codes.
        """
        # Attempt API → contentBundles HTML
        try:
            release = self._fetch_release_info()
            items = []
            for bundle in release.get("contentBundles", []) or []:
                try:
                    url = f"{self.api_url}content/bundle/{bundle['id']}?api-version={self.api_version}"
                    content = _fetch_with_retry(url, timeout=30, max_retries=3)
                    items.extend(content.json().get("items", []))
                except Exception:
                    continue

            codes: dict[str, str] = {}
            for item in items:
                html_content = item.get("content")
                if not html_content:
                    continue
                soup = BeautifulSoup(html_content, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    text = a.get_text(strip=True)
                    # Extract unit-like codes from href/text
                    match = _UNIT_CODE_RE.search(href) or _UNIT_CODE_RE.search(text)
                    if match:
                        code = match.group(0)
                        if is_unit_like_code(code):
                            if code not in codes:
                                title = text if (text and code not in text) else ""
                                codes[code] = title

            if codes:
                results: list[dict[str, str]] = []
                for code, title in codes.items():
                    if title:
                        results.append({"id": code, "title": title})
                    else:
                        # Try enrich title
                        try:
                            u = UnitOfCompetency(code)
                            results.append({"id": code, "title": u.title or ""})
                        except Exception:
                            results.append({"id": code, "title": title})
                results.sort(key=lambda x: x["id"])
                return results
        except Exception:
            pass

        # HTML fallback: scan public page(s)
        codes: dict[str, str] = {}
        for url in [
            f"{self.base_url}training/{self.course_code}/qualificationdetails",
            f"{self.base_url}training/{self.course_code}/coursedetails",
            f"{self.base_url}training/details/{self.course_code}",
            f"{self.base_url}training/{self.course_code}",
        ]:
            try:
                resp = _fetch_with_retry(url, timeout=30, max_retries=2)
            except Exception:
                continue
            soup = BeautifulSoup(resp.content, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True)
                match = _UNIT_CODE_RE.search(href) or _UNIT_CODE_RE.search(text)
                if match:
                    code = match.group(0)
                    if is_unit_like_code(code) and code not in codes:
                        title = text if (text and code not in text) else ""
                        codes[code] = title

            if codes:
                break

        results: list[dict[str, str]] = []
        for code, title in codes.items():
            if title:
                results.append({"id": code, "title": title})
            else:
                try:
                    u = UnitOfCompetency(code)
                    results.append({"id": code, "title": u.title or ""})
                except Exception:
                    results.append({"id": code, "title": title})
        results.sort(key=lambda x: x["id"])
        return results


@app.command()
def show(
    unit_code: str = typer.Argument(
        ..., help="Unit or Course code (e.g., ICTPRG302 or ICT40120)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed debug information"
    ),
    sections_only: bool = typer.Option(
        False, "--sections", "-s", help="Show available sections only"
    ),
    index_path: Optional[str] = typer.Option(
        None, "--index-path", help="Override path to local NRT index (jsonl.gz)"
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Output as JSON (from cache or fetched)"
    ),
):
    """
    📖 Display Unit or Course information (default command).

    Examples:
        uoc show ICTPRG302                 # Show full UOC details
        uoc show ICT40120                 # Show basic course info
        uoc show ICTPRG302 -v             # Verbose
        uoc show --sections ICTPRG302     # Sections only (units)
    """
    try:
        if verbose:
            import logging

            logging.basicConfig(level=logging.DEBUG)

        idx = _get_nrt_index(index_path)

        # Try local index type-based routing first
        idx = _get_nrt_index(index_path)
        rec = idx.get(unit_code) if idx else None
        rec_type = str(rec.get("type")) if rec else ""

        if rec and "trainingPackage" in rec_type:
            # Defer to package view
            return packages(unit_code, index_path, True, True, False)  # type: ignore

        # Skill set: show title and list units via unitgrid
        if rec and ("skillSet" in rec_type or "Skill set" in rec_type):
            print(f"🧩 Skill Set: {unit_code}")
            print("=" * 60)
            print(
                rec.get("title")
                or (idx.get_title(unit_code) if idx else "")
                or "(title unavailable)"
            )
            units = _get_qual_units(unit_code, None, force=False)
            if units:
                print(f"\n📚 Units in {unit_code} ({len(units)}):")
                for u in units:
                    if not u.get("title") and idx:
                        u["title"] = idx.get_title(u["id"]) or ""
                    name_part = f" — {u['title']}" if u.get("title") else ""
                    print(f"  • {u['id']}{name_part}")
            return

        if rec and (
            "qualification" in rec_type
            or "accreditedCourse" in rec_type
            or is_course_like_code(unit_code)
        ):
            q = Qualification(unit_code)
            print(f"🎓 Course: {unit_code}")
            print("=" * 60)
            print(
                q.data.title
                or q.title
                or (idx.get_title(unit_code) if idx else "")
                or "(title unavailable)"
            )
            if q.data.release_number or q.data.currency:
                meta = []
                if q.data.release_number:
                    meta.append(f"Release {q.data.release_number}")
                if q.data.currency:
                    meta.append(q.data.currency)
                print(f"({', '.join(meta)})")
            # Terminal width-aware wrapper
            term_width = shutil.get_terminal_size((100, 20)).columns

            def _wrap_text(s: str) -> str:
                if not s:
                    return ""
                width = max(60, min(term_width, 100))
                return "\n".join(textwrap.wrap(s, width=width))

            if q.data.description:
                print("\nDescription")
                print("-" * 11)
                print(_wrap_text(q.data.description))
            if q.data.entry_requirements:
                print("\nEntry requirements")
                print("-" * 19)
                print(_wrap_text(q.data.entry_requirements))
            if q.data.packaging_rules:
                print("\nPackaging rules")
                print("-" * 16)
                print(
                    _format_packaging_rules_readable(q.data.packaging_rules, term_width)
                )
            # Units
            units = q.get_units()
            if units:
                print(f"\n📦 Units in {unit_code} ({len(units)}):")
                for u in units:
                    if not u.get("title") and idx:
                        u["title"] = idx.get_title(u["id"]) or ""
                    name_part = f" — {u['title']}" if u.get("title") else ""
                    print(f"  • {u['id']}{name_part}")
        else:
            uoc = UnitOfCompetency(unit_code)

            if json_output:
                # Output JSON from cache or fetched data
                json_data = _load_uoc_json_from_cache(unit_code)
                if json_data:
                    # Load from cache
                    data, metadata = json_data
                    output = {
                        "schema_version": metadata.get("schema_version", 1),
                        "unit_code": unit_code.upper(),
                        "aqf_level": data.aqf_level,
                        "title": metadata.get("title", uoc.title),
                        "training_package": metadata.get("training_package", ""),
                        "status": metadata.get("status", "current"),
                        "cached_at": metadata.get("cached_at", ""),
                        "source": metadata.get("source", {}),
                        "sections": data.to_dict(),
                    }
                else:
                    # No cache, use current data
                    training_package = ""
                    if len(unit_code) >= 3:
                        training_package = (
                            re.match(r"^[A-Z]+", unit_code).group()
                            if re.match(r"^[A-Z]+", unit_code)
                            else ""
                        )
                    output = {
                        "schema_version": 1,
                        "unit_code": unit_code.upper(),
                        "aqf_level": uoc.data.aqf_level,
                        "title": uoc.title,
                        "training_package": training_package,
                        "status": "current",
                        "cached_at": datetime.now(timezone.utc).isoformat(),
                        "source": {
                            "release": "1",
                            "url": f"{uoc.base_url}training/details/{unit_code}",
                        },
                        "sections": uoc.data.to_dict(),
                    }
                wa_hours = _get_wa_nominal_hours(unit_code)
                if wa_hours is not None:
                    output["wa_nominal_hours"] = wa_hours
                print(json.dumps(output, ensure_ascii=False, indent=2))
            elif sections_only:
                print(f"📋 Available sections for {unit_code}:")
                for section in uoc.sections:
                    print(f"  • {section.value}")
            else:
                header_title = (
                    uoc.title or (idx.get_title(unit_code) if idx else "") or ""
                )
                header = (
                    f"{unit_code} — {header_title}" if header_title else f"{unit_code}"
                )
                print(f"📖 Unit of Competency: {header}")
                print("=" * 60)
                wa_hours = _get_wa_nominal_hours(unit_code)
                if wa_hours is not None:
                    print(f"WA Nominal Hours: {wa_hours}")
                print(uoc)

    except UnitOfCompetencyNotFoundError:
        print(f"❌ Unit '{unit_code}' not found on training.gov.au")
        print("💡 Check the unit code spelling and try again")
        raise typer.Exit(1)
    except UnitOfCompetencyError as e:
        print(f"❌ Error: {e}")
        raise typer.Exit(1)


# Make 'show' the default command when no subcommand is specified
def main_entry():
    """Main entry point that defaults to 'show' command if no subcommand given."""
    import sys

    # If no arguments or first arg is not a known command, prepend 'show'
    args = sys.argv[1:]
    known_commands = [
        "show",
        "compare",
        "search",
        "raw",
        "index",
        "index-info",
        "index-search",
        "wa-index",
        "quals",
        "ss",
        "units",
        "packages",
    ]
    if not args:
        sys.argv.insert(1, "show")
    else:
        # Reorder to support global flags (e.g., --no-cache) placed after the implicit command
        # Collect global flags (currently only --no-cache) from anywhere in args
        global_flags = {"--no-cache"}
        leading_opts: list[str] = []
        remaining: list[str] = []
        # Preserve original order for non-global opts
        for a in args:
            if a in global_flags:
                leading_opts.append(a)
            else:
                remaining.append(a)
        # Determine insertion point: before first non-option that is not a known command
        if remaining and (
            remaining[0] not in known_commands and not remaining[0].startswith("-")
        ):
            # Build argv: prog + leading_global + ['show'] + remaining
            sys.argv = [sys.argv[0]] + leading_opts + ["show"] + remaining
        else:
            # If a real command was used, keep argv as-is (with global flags leading if any)
            if leading_opts:
                # Move leading_opts to just after program name
                new_args = leading_opts + [a for a in args if a not in global_flags]
                sys.argv = [sys.argv[0]] + new_args

    app()


def main_callback():
    """Empty callback - not used in this structure"""
    pass


def _maybe_configure_vectorgrep() -> None:
    """Attempt to configure vectorgrep native library paths on macOS/Linux.

    Looks in package vendor dir and common system locations (Homebrew) for:
    - libvectorscan/libhs (Hyperscan/Vectorscan)
    - libvectorgrep
    - libzstd
    """
    try:
        pkg_dir = Path(vectorgrep.__file__).parent
        vendor = pkg_dir / "lib"
        lib_dirs = [vendor, Path("/opt/homebrew/lib"), Path("/usr/local/lib")]

        def find_one(names: list[str]) -> Optional[str]:
            for d in lib_dirs:
                try:
                    for n in names:
                        p = d / n
                        if p.exists():
                            return str(p)
                except Exception:
                    continue
            return None

        libhs = find_one(["libvectorscan.dylib", "libhs.dylib", "libhs.so"])
        libvg = find_one(["libvectorgrep.dylib", "libvectorgrep.so"])
        libzstd = find_one(
            ["libzstd.dylib", "libzstd.1.dylib", "libzstd.so", "libzstd.so.1"]
        )

        # Configure only if we found at least one override; harmless otherwise
        vectorgrep.configure_libraries(
            libhs=libhs, libvectorgrep=libvg, libzstd=libzstd
        )
    except Exception:
        # Non-fatal: we'll let vectorgrep try its defaults
        pass


def _extract_title_from_lines(lines: list[str], unit_code: str) -> str:
    """Attempt to extract a unit title from cached text lines.

    Primary strategy: look for a header like "CODE — Title" near the top.
    Returns empty string if not found.
    """
    try:
        # Search first 10 lines for a header form
        upper_code = unit_code.upper()
        for raw in lines[:10]:
            line = raw.strip()
            if not line:
                continue
            if line.startswith(upper_code) and "—" in line:
                # Expected format: CODE — Title
                parts = line.split("—", 1)
                if len(parts) == 2:
                    return parts[1].strip()
        return ""
    except Exception:
        return ""


# ---------------------------------
# Qualification data model & cache
# ---------------------------------


@dataclass
class QualificationData:
    course_code: str
    title: str = ""
    currency: str = ""
    release_number: str = ""
    release_date: str = ""
    assets: list[dict] = field(default_factory=list)
    external_links: list[dict] = field(default_factory=list)
    specialisations: list[dict] = field(default_factory=list)
    description: str = ""
    entry_requirements: str = ""
    packaging_rules: str = ""


def _qual_release_cache_dir() -> Path:
    base = _default_cache_dir() / "qual_releases"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _qual_bundle_cache_dir() -> Path:
    base = _default_cache_dir() / "qual_bundles"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _qual_release_cache_path(course_code: str, release_number: str) -> Path:
    return _qual_release_cache_dir() / f"{course_code.upper()}_R{release_number}.json"


def _qual_bundle_cache_path(bundle_id: str) -> Path:
    return _qual_bundle_cache_dir() / f"{bundle_id}.json"


def _fetch_json(url: str) -> dict:
    try:
        resp = _fetch_with_retry(url, timeout=30)
        data = resp.json()
        return data if isinstance(data, dict) else {}
    except Exception as e:
        raise UnitOfCompetencyError(f"Failed to fetch URL {url}: {e}")


def _html_to_text(html_str: str) -> str:
    try:
        soup = BeautifulSoup(html_str, "html.parser")
        return soup.get_text("\n", strip=True)
    except Exception:
        return html_str or ""


def _api_base_and_version() -> tuple[str, str]:
    return ("https://training.gov.au/api/", "1.0")


def _list_training_releases(code: str) -> list[dict]:
    api_base, version = _api_base_and_version()
    urls = [
        f"{api_base}training/{code}/releases?api-version={version}",
        f"{api_base}training/{code}/releases",
    ]
    for url in urls:
        try:
            resp = _fetch_with_retry(url, timeout=30, max_retries=3)
            data = resp.json()
            if isinstance(data, list):
                return data
        except Exception:
            continue
    return []


def _best_release_number(releases: list[dict]) -> Optional[str]:
    if not releases:
        return None
    # Prefer currency == current
    current = [r for r in releases if str(r.get("currency")).lower() == "current"]
    candidates = current or releases

    # Sort by numeric releaseNumber (e.g., 9.1 > 9.0 > 8.1)
    def parse_num(s: str) -> tuple[int, int]:
        try:
            parts = s.split(".")
            major = int(parts[0]) if parts and parts[0].isdigit() else 0
            minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            return (major, minor)
        except Exception:
            return (0, 0)

    candidates.sort(
        key=lambda r: parse_num(str(r.get("releaseNumber") or "0.0")), reverse=True
    )
    return str(candidates[0].get("releaseNumber")) if candidates else None


def _format_packaging_rules_readable(text: str, width: int) -> str:
    """Render packaging rules into a more readable, structured layout.

    Heuristics:
    - Extract and show totals (total/core/elective)
    - Promote section headings (Core units, Elective units, Specialisations, Group X ...)
    - Bullet rule lines (starts with 'at least', 'up to', 'Select')
    - Format unit lines starting with a code as bullets: CODE — title
    - Wrap long lines to the provided width
    """
    if not text:
        return ""

    lines = [ln.strip() for ln in text.splitlines()]

    # Extract counts
    total_units = None
    core_units = None
    elective_units = None
    for ln in lines[:50]:
        m = re.search(r"Total number of units\s*=\s*(\d+)", ln, re.I)
        if m:
            total_units = m.group(1)
        m = re.search(r"(\d+)\s+core units", ln, re.I)
        if m:
            core_units = m.group(1)
        m = re.search(r"(\d+)\s+elective units", ln, re.I)
        if m:
            elective_units = m.group(1)

    out: list[str] = []
    if any([total_units, core_units, elective_units]):
        meta_parts = []
        if total_units:
            meta_parts.append(f"Total units: {total_units}")
        if core_units:
            meta_parts.append(f"Core: {core_units}")
        if elective_units:
            meta_parts.append(f"Electives: {elective_units}")
        out.append("; ".join(meta_parts))

    def add_heading(title: str):
        out.append("")
        out.append(title)
        out.append("-" * len(title))

    CODE_RE = re.compile(r"^([A-Z]{2,}[A-Z0-9]+)\b(.*)")

    i = 0
    while i < len(lines):
        ln = lines[i]
        if not ln:
            i += 1
            continue

        lower = ln.lower()
        # Section headings
        if lower in {"core units", "elective units", "specialisations"}:
            add_heading(ln)
            i += 1
            continue
        if ln.startswith("Group ") and ln.rstrip().endswith("Specialisation"):
            add_heading(ln)
            i += 1
            continue

        # Bullet rules
        if (
            lower.startswith("at least")
            or lower.startswith("up to")
            or lower.startswith("select")
            or lower.startswith("units selected")
            or lower.startswith("elective units must")
        ):
            out.append(f" - {ln}")
            i += 1
            continue

        # Unit lines starting with a code
        m = CODE_RE.match(ln)
        if m:
            code, rest = m.group(1), m.group(2).strip(" \u2014-:\u2013")
            # If no inline title, try to merge with the following line when it looks like a title
            if not rest and i + 1 < len(lines):
                nxt = lines[i + 1].strip()
                # Next line should not start with another code, heading, or rule starter
                if nxt and not CODE_RE.match(nxt):
                    nxt_lower = nxt.lower()
                    if (
                        nxt_lower
                        not in {"core units", "elective units", "specialisations"}
                        and not nxt_lower.startswith("group ")
                        and not nxt_lower.startswith("at least")
                        and not nxt_lower.startswith("up to")
                        and not nxt_lower.startswith("select")
                        and not nxt_lower.startswith("units selected")
                        and not nxt_lower.startswith("elective units must")
                    ):
                        rest = nxt
                        i += 1  # consume next line as title
            bullet = f"  • {code}"
            if rest:
                bullet += f" — {rest}"
            out.append(bullet)
            i += 1
            continue

        # Default: keep line
        out.append(ln)
        i += 1

    # Wrap
    wrapped: list[str] = []
    wrap_width = max(60, min(width, 100))
    for ln in out:
        if not ln or ln.startswith(" ") or ln.startswith("- "):
            # For bullets, wrap with indentation
            if ln.startswith("  • "):
                indent = "    "
                content = ln[3:].strip()
                chunks = textwrap.wrap(content, width=wrap_width - len(indent))
                if chunks:
                    wrapped.append("  • " + chunks[0])
                    for c in chunks[1:]:
                        wrapped.append(indent + c)
                else:
                    wrapped.append(ln)
            elif ln.startswith(" - "):
                indent = "   "
                content = ln[3:]
                chunks = textwrap.wrap(content, width=wrap_width - len(indent))
                for j, c in enumerate(chunks):
                    wrapped.append((" - " if j == 0 else indent) + c)
            else:
                wrapped.append(ln)
        else:
            wrapped.extend(textwrap.wrap(ln, width=wrap_width) or [ln])

    return "\n".join(wrapped)


@app.command()
def compare(
    unit1: str = typer.Argument(..., help="First unit code"),
    unit2: str = typer.Argument(..., help="Second unit code"),
):
    """
    🔍 Compare two Units of Competency side by side.
    """
    try:
        uoc1 = UnitOfCompetency(unit1)
        uoc2 = UnitOfCompetency(unit2)

        print(f"📊 Comparing {unit1} vs {unit2}")
        print("=" * 60)

        print(f"\n📝 {unit1} Elements: {len(uoc1.data.elements_and_criteria)}")
        print(f"📝 {unit2} Elements: {len(uoc2.data.elements_and_criteria)}")

        # Count criteria
        criteria1 = sum(
            len(criteria) for criteria in uoc1.data.elements_and_criteria.values()
        )
        criteria2 = sum(
            len(criteria) for criteria in uoc2.data.elements_and_criteria.values()
        )
        print(f"📋 {unit1} Criteria: {criteria1}")
        print(f"📋 {unit2} Criteria: {criteria2}")

        # Knowledge evidence
        ke1_values = (
            list(uoc1.data.knowledge_evidence.values())
            if uoc1.data.knowledge_evidence
            else []
        )
        ke2_values = (
            list(uoc2.data.knowledge_evidence.values())
            if uoc2.data.knowledge_evidence
            else []
        )
        ke1 = ke1_values[0] if ke1_values else []
        ke2 = ke2_values[0] if ke2_values else []
        ke1_count = len(ke1) if isinstance(ke1, (list, dict)) else 0
        ke2_count = len(ke2) if isinstance(ke2, (list, dict)) else 0
        print(f"🧠 {unit1} Knowledge items: {ke1_count}")
        print(f"🧠 {unit2} Knowledge items: {ke2_count}")

        # Performance evidence
        pe1_values = (
            list(uoc1.data.performance_evidence.values())
            if uoc1.data.performance_evidence
            else []
        )
        pe2_values = (
            list(uoc2.data.performance_evidence.values())
            if uoc2.data.performance_evidence
            else []
        )
        pe1 = pe1_values[0] if pe1_values else []
        pe2 = pe2_values[0] if pe2_values else []
        pe1_count = len(pe1) if isinstance(pe1, (list, dict)) else 0
        pe2_count = len(pe2) if isinstance(pe2, (list, dict)) else 0
        print(f"🎯 {unit1} Performance items: {pe1_count}")
        print(f"🎯 {unit2} Performance items: {pe2_count}")

        # Performance skills
        ps1_values = (
            list(uoc1.data.performance_skills.values())
            if uoc1.data.performance_skills
            else []
        )
        ps2_values = (
            list(uoc2.data.performance_skills.values())
            if uoc2.data.performance_skills
            else []
        )
        ps1 = ps1_values[0] if ps1_values else []
        ps2 = ps2_values[0] if ps2_values else []
        ps1_count = len(ps1) if isinstance(ps1, (list, dict)) else 0
        ps2_count = len(ps2) if isinstance(ps2, (list, dict)) else 0
        print(f"🔧 {unit1} Performance skills: {ps1_count}")
        print(f"🔧 {unit2} Performance skills: {ps2_count}")

    except (UnitOfCompetencyNotFoundError, UnitOfCompetencyError) as e:
        print(f"❌ Error: {e}")
        raise typer.Exit(1)


@app.command()
def search(
    terms: List[str] = typer.Argument(
        ..., help="Search terms (regex). Multiple terms are OR'ed together"
    ),
    before: int = typer.Option(
        0, "--before", "-B", help="Lines of context before match"
    ),
    after: int = typer.Option(0, "--after", "-A", help="Lines of context after match"),
    ignore_case: bool = typer.Option(
        True, "--ignore-case/--case-sensitive", help="Case-insensitive search"
    ),
    include: Optional[str] = typer.Option(
        None,
        "--include",
        "-i",
        help="Comma-separated training package prefixes to include (e.g., ICT,MEM)",
    ),
    qual: Optional[str] = typer.Option(
        None,
        "--qual",
        "-q",
        help="Comma-separated qualification/skill set codes to restrict units (e.g., ICT40120)",
    ),
    cache_dir: Optional[str] = typer.Option(
        None, "--cache-dir", help="Override path to UOC content cache directory"
    ),
    limit: Optional[int] = typer.Option(
        None, "--limit", "-n", help="Maximum number of UoCs to display"
    ),
):
    """
    Search UoC content cache (.txt and .txt.gz) for terms and print collated hits
    with configurable context per match. Each UoC groups its hits separated by
    a blank line and '...' between blocks.
    """
    # Resolve cache directory
    uoc_dir = Path(cache_dir) if cache_dir else _uoc_content_cache_dir()
    if not uoc_dir.exists():
        print(f"❌ UOC content cache not found: {uoc_dir}")
        raise typer.Exit(1)

    # Try to configure vectorgrep to avoid dlopen errors (macOS/Homebrew etc.)
    _maybe_configure_vectorgrep()

    # Prepare pattern list for vectorgrep
    patterns = list(terms)
    shown_units = 0

    # Load NRT index once to resolve titles
    try:
        idx = _get_nrt_index()
    except Exception:
        idx = None

    # Parse includes into uppercase prefixes
    include_prefixes: set[str] = set()
    if include:
        try:
            include_prefixes = {
                p.strip().upper() for p in include.split(",") if p.strip()
            }
        except Exception:
            include_prefixes = set()

    # Build allowed unit set from qualification codes if provided
    allowed_units: set[str] = set()
    if qual:
        try:
            qual_codes = [q.strip().upper() for q in qual.split(",") if q.strip()]
            for qc in qual_codes:
                try:
                    for u in _get_qual_units(qc, None, force=False):
                        uid = str(u.get("id") or "").upper()
                        if uid:
                            allowed_units.add(uid)
                except Exception:
                    try:
                        q = Qualification(qc)
                        for u in q.get_units():
                            uid = str(u.get("id") or "").upper()
                            if uid:
                                allowed_units.add(uid)
                    except Exception:
                        continue
        except Exception:
            allowed_units = set()

    # Collect candidate files (.txt and .txt.gz)
    files: List[Path] = []
    files.extend(sorted(uoc_dir.glob("*.txt")))
    files.extend(sorted(uoc_dir.glob("*.txt.gz")))

    if not files:
        print("(no UoC content files found in cache)")
        raise typer.Exit(0)

    for path in files:
        # Determine unit code from filename and filter by prefixes and quals if provided
        unit_code = path.stem.split(".")[0].upper()
        if include_prefixes and not any(
            unit_code.startswith(p) for p in include_prefixes
        ):
            continue
        if allowed_units and unit_code not in allowed_units:
            continue
        # Call vectorgrep on the file path
        vg_failed = False
        try:
            matches_or_count, rc = vectorgrep.grep(
                str(path), patterns, ignore_case=ignore_case, count_only=False
            )
        except Exception as e:
            vg_failed = True
            vg_error = str(e)

        # vectorgrep.grep returns (list[(line_number, line_text)], return_code)
        if not vg_failed:
            if isinstance(matches_or_count, int) or not matches_or_count:
                continue

        # Load lines for context printing
        try:
            if path.suffix == ".gz":
                import gzip

                with gzip.open(path, "rt", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            else:
                lines = path.read_text(encoding="utf-8", errors="ignore").splitlines(
                    True
                )
        except Exception:
            # Fallback safe read
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            except Exception as e:
                print(f"⚠️  Failed to read {path.name} for context: {e}")
                continue

        # unit_code already derived above

        # When vectorgrep failed, fall back to Python regex over loaded lines
        if vg_failed:
            try:
                flags = re.IGNORECASE if ignore_case else 0
                pattern = re.compile("|".join(patterns), flags)
                matches = []
                for idx, line in enumerate(lines, start=1):
                    if pattern.search(line):
                        matches.append((idx, line))
                if not matches:
                    continue
                matches_or_count = matches
            except Exception:
                print(f"⚠️  Skipping {path.name} due to search error: {vg_error}")
                continue

        # Print unit header with title if available
        try:
            title = idx.get_title(unit_code) if idx else ""
            if not title:
                # Best-effort: try to extract from cached content header
                title = _extract_title_from_lines(lines, unit_code) or ""
        except Exception:
            title = _extract_title_from_lines(lines, unit_code) or ""
        header_line = f"{unit_code} — {title}" if title else unit_code
        print(header_line)
        print("=" * len(header_line))

        first_block = True
        for line_number, _line_text in matches_or_count:
            # Separate blocks with '...'
            if not first_block:
                print("...")
                print("")
            first_block = False

            # Compute context window (1-based to 0-based indices)
            ln = max(1, int(line_number))
            start_idx = max(1, ln - before)
            end_idx = min(len(lines), ln + after)
            # Print context lines
            for i in range(start_idx - 1, end_idx):
                print(lines[i].rstrip("\n"))

        print("")
        shown_units += 1
        if limit is not None and shown_units >= limit:
            break


@app.command()
def raw(
    unit_code: str = typer.Argument(..., help="Unit code"),
    json_output: bool = typer.Option(False, "--json", help="Output raw data as JSON"),
):
    """
    🔧 Show raw UOC data structure (for debugging).
    """
    try:
        uoc = UnitOfCompetency(unit_code)
        if json_output:
            # Output the data structure as JSON
            output = {
                "unit_code": uoc.unit_code,
                "aqf_level": uoc.aqf_level,
                "title": uoc.title,
                "data": uoc.data.to_dict(),
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            print(f"🔧 Raw data for {unit_code}:")
            print("=" * 60)
            print(uoc.data)
    except (UnitOfCompetencyNotFoundError, UnitOfCompetencyError) as e:
        print(f"❌ Error: {e}")
        raise typer.Exit(1)


@app.command()
def index(
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Path to write the JSONL (gz) index. Defaults to cache dir",
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Ignore cache currency and refresh now"
    ),
    clear: bool = typer.Option(
        False,
        "--clear",
        help="Delete existing NRT index and UOC content cache before indexing",
    ),
    page_size: int = typer.Option(1000, "--page-size", help="API page size (max 1000)"),
    max_pages: Optional[int] = typer.Option(
        None, "--max-pages", help="Limit number of pages (for testing)"
    ),
    concurrency: int = typer.Option(
        5, "--concurrency", "-c", help="Number of pages to fetch in parallel"
    ),
):
    """
    Build a local index of Nationally Recognised Training (units, courses, packages).

    - Fetches the paginated search endpoint
    - Writes JSONL (gz) file to cache (or --output)
    - Uses a 7-day currency timer unless --force
    """
    cache_dir = _default_cache_dir()
    dst = Path(output) if output else _index_path(cache_dir)

    # Clear caches if requested
    if clear:
        try:
            # Remove index files
            ip = _index_path(cache_dir)
            mp = _meta_path(cache_dir)
            if ip.exists():
                ip.unlink(missing_ok=True)  # type: ignore[arg-type]
            if mp.exists():
                mp.unlink(missing_ok=True)  # type: ignore[arg-type]

            # Remove UOC content cache files (both txt and txt.gz)
            uoc_dir = _uoc_content_cache_dir()
            if uoc_dir.exists():
                for p in list(uoc_dir.glob("*.txt")) + list(uoc_dir.glob("*.txt.gz")):
                    try:
                        p.unlink()
                    except Exception:
                        pass

            # Remove QUAL content cache files
            try:
                q_dir = _qual_content_cache_dir()
                if q_dir.exists():
                    for p in q_dir.glob("*.txt"):
                        try:
                            p.unlink()
                        except Exception:
                            pass
            except Exception:
                pass

            # Optionally clear QUAL release/bundle metadata caches
            try:
                qr_dir = _qual_release_cache_dir()
                if qr_dir.exists():
                    for p in qr_dir.glob("*.json"):
                        try:
                            p.unlink()
                        except Exception:
                            pass
            except Exception:
                pass
            try:
                qb_dir = _qual_bundle_cache_dir()
                if qb_dir.exists():
                    for p in qb_dir.glob("*.json"):
                        try:
                            p.unlink()
                        except Exception:
                            pass
            except Exception:
                pass

            print("🧹 Cleared index and content caches (UOC + QUAL)")
        except Exception as e:
            print(f"⚠️  Failed to clear cache: {e}")

    if not force and dst.exists() and _is_cache_fresh(cache_dir, max_age_days=7):
        print("✅ Index is fresh (≤ 7 days). Skipping fetch. Use --force to refresh.")
        print(f"📄 Index: {dst}")
        print(f"ℹ️  Meta: {_meta_path(cache_dir)}")
        return

    print("🔄 Fetching NRT index from training.gov.au …")
    start = time.time()
    try:
        count = 0
        pages = 0
        bar = None

        # Function to fetch and write one source (base_url)
        def fetch_source(base_url: str):
            nonlocal count, pages, bar
            # First page to determine total if available
            first = _fetch_nrt_page(base_url, 0, page_size)
            first_items = (
                first.get("data") or first.get("items") or first.get("value") or []
            )
            total = (
                first.get("totalCount")
                or first.get("count")
                or first.get("@odata.count")
            )

            if tqdm and isinstance(total, int):
                # Recreate bar if not present; otherwise leave as dynamic
                if not bar:
                    bar = tqdm(
                        total=total, unit="rec", desc="Indexing", dynamic_ncols=True
                    )
                else:
                    bar.total = (bar.total or 0) + total  # type: ignore
                    bar.refresh()
            elif tqdm and not bar:
                bar = tqdm(total=None, unit="rec", desc="Indexing", dynamic_ncols=True)

            # If concurrency <= 1 or total unknown, use sequential streaming
            if concurrency <= 1 or not isinstance(total, int):
                items = first_items
                offset = 0
                while True:
                    if not items:
                        break
                    for it in items:
                        f.write(json.dumps(it, ensure_ascii=False) + "\n")
                        count += 1
                    if bar:
                        bar.update(len(items))
                    else:
                        print(f"  • Page {pages + 1}: +{len(items)} (total {count})")
                    pages += 1
                    if max_pages and pages >= max_pages:
                        break
                    offset += page_size
                    time.sleep(0.15)
                    items = _safe_fetch_items(base_url, offset, page_size)
            else:
                # Concurrent fetching with ordering by page index
                total_pages = math.ceil(total / page_size)
                if max_pages:
                    total_pages = min(total_pages, max_pages)

                # Write first page immediately
                if first_items:
                    for it in first_items:
                        f.write(json.dumps(it, ensure_ascii=False) + "\n")
                        count += 1
                    if bar:
                        bar.update(len(first_items))
                    else:
                        print(f"  • Page 1: +{len(first_items)} (total {count})")
                    pages += 1

                # Submit remaining page fetches
                def fetch_page(idx: int):
                    offset = idx * page_size
                    return idx, _safe_fetch_items(base_url, offset, page_size)

                next_to_write = 1
                buffer: dict[int, list] = {}
                with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
                    futures = [
                        pool.submit(fetch_page, idx) for idx in range(1, total_pages)
                    ]

                    for fut in as_completed(futures):
                        idx, items = fut.result()
                        buffer[idx] = items
                        # Write in-order pages as available
                        while next_to_write in buffer:
                            items_w = buffer.pop(next_to_write)
                            if not items_w:
                                next_to_write += 1
                                continue
                            for it in items_w:
                                f.write(json.dumps(it, ensure_ascii=False) + "\n")
                                count += 1
                            if bar:
                                bar.update(len(items_w))
                            else:
                                print(
                                    f"  • Page {next_to_write + 1}: +{len(items_w)} (total {count})"
                                )
                            pages += 1
                            next_to_write += 1

        with gzip.open(dst, "wt", encoding="utf-8") as f:
            # Fetch both sources sequentially into the same file
            fetch_source(NRT_SEARCH_URL)
            fetch_source(NRT_TP_SEARCH_URL)

        if bar:
            bar.close()

        duration = time.time() - start
        _write_meta(cache_dir, total_count=count, duration_s=duration)
        print(f"✅ Wrote {count} records to {dst} in {duration:.2f}s")
        print(f"ℹ️  Meta: {_meta_path(cache_dir)}")

        # Build/refresh UOC and QUAL content caches after index fetch
        try:
            idx = _get_nrt_index()
            if idx:
                print("🔄 Building UOC content cache …")
                built = _build_content_cache_from_index(
                    idx, concurrency=max(1, concurrency // 2)
                )
                print(f"✅ Cached {built} UOC contents")
                print("🔄 Building QUAL content cache …")
                qbuilt = _build_qual_content_cache_from_index(
                    idx, concurrency=max(1, concurrency // 2)
                )
                print(f"✅ Cached {qbuilt} QUAL contents")
        except Exception as e:
            print(f"⚠️  Skipped content cache build: {e}")

        # Build WA nominal hours mapping
        try:
            print("🔄 Building WA nominal hours mapping …")
            wa_mapping = _build_wa_nominal_hours_mapping(concurrency=3)
            _save_wa_nominal_hours(wa_mapping, cache_dir)
            print(f"✅ Mapped {len(wa_mapping)} WA nominal hours")
        except Exception as e:
            print(f"⚠️  Skipped WA nominal hours build: {e}")
    except requests.HTTPError as e:
        print(f"❌ HTTP error fetching index: {e}")
        raise typer.Exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        raise typer.Exit(1)


# Removed legacy commands: courses, units, course, unit (replaced by show/quals/ss/package)


@app.command("wa-index")
def wa_index(
    force: bool = typer.Option(
        False, "--force", "-f", help="Ignore cache currency and refresh now"
    ),
    clear: bool = typer.Option(
        False, "--clear", help="Delete existing WA nominal hours cache before building"
    ),
    concurrency: int = typer.Option(
        3, "--concurrency", "-c", help="Concurrency level (unused, reserved for future)"
    ),
):
    """
    Build WA nominal hours mapping by scraping the DTWD Training Product Search.

    - Iterates all training packages in the TPS dropdown
    - Collects nominal hours for each Module / UoC
    - Saves to a JSON cache file (30-day TTL)
    """
    cache_dir = _default_cache_dir()

    if clear:
        for p in (_wa_nominal_hours_path(cache_dir), _wa_nominal_hours_meta_path(cache_dir)):
            if p.exists():
                p.unlink()
        print("🧹 Cleared WA nominal hours cache")

    if not force and _is_wa_cache_fresh(cache_dir, max_age_days=30):
        meta = json.loads(_wa_nominal_hours_meta_path(cache_dir).read_text(encoding="utf-8"))
        print(f"✅ WA nominal hours cache is fresh (≤ 30 days). {meta.get('total_count', '?')} records.")
        print("   Use --force to refresh.")
        return

    print("🔄 Building WA nominal hours mapping from TPS …")
    start = time.time()
    try:
        wa_mapping = _build_wa_nominal_hours_mapping(concurrency=concurrency)
        _save_wa_nominal_hours(wa_mapping, cache_dir)
        duration = time.time() - start
        print(f"✅ Mapped {len(wa_mapping)} WA nominal hours in {duration:.1f}s")
    except Exception as e:
        print(f"❌ Error building WA nominal hours: {e}")
        raise typer.Exit(1)


@app.command("packages")
def packages(
    code: Optional[str] = typer.Argument(
        None, help="Optional training package code (e.g., ICT)"
    ),
    index_path: Optional[str] = typer.Option(
        None, "--index-path", help="Path to local NRT index (jsonl.gz)"
    ),
    show_qualifications: bool = typer.Option(
        True, "--qual/--no-qual", help="List qualifications in this package"
    ),
    show_skillsets: bool = typer.Option(
        True, "--skillsets/--no-skillsets", help="List skill sets in this package"
    ),
    show_units: bool = typer.Option(
        False, "--units/--no-units", help="List units in this package (may be long)"
    ),
):
    """
    List training packages or show a package view:
    - No code: list all training packages in the index
    - With code: package → qualifications / skill sets → (optional) units
    """
    idx = _get_nrt_index(index_path)
    if not idx:
        print("❌ Local index not found. Run 'uoc index' first.")
        raise typer.Exit(1)
    # No code: list all packages
    if not code:
        items: list[tuple[str, str]] = []
        for c, rec in idx.by_code.items():
            if (
                "trainingPackage" in str(rec.get("type"))
                and not _is_deleted_record(rec)
                and not _is_superseded_record(rec)
            ):
                items.append((c, rec.get("title", "")))
        items.sort()
        if not items:
            print("(no training packages found)")
            return
        print("📦 Training Packages:")
        print("=" * 60)
        for c, t in items:
            print(f"• {c} — {t}")
        return

    code = code.upper()
    pkg_rec = idx.get(code)
    if not pkg_rec or "trainingPackage" not in str(pkg_rec.get("type")):
        print(f"❌ Training package '{code}' not found in local index")
        raise typer.Exit(1)

    print(f"📦 Training Package: {code}")
    print("=" * 60)
    print(pkg_rec.get("title") or "(title unavailable)")

    # Try to enrich lists via training package components endpoint (cached)
    comps = _get_tp_components(code, None, force=False)
    enriched_quals: list[tuple[str, str]] = []
    enriched_ssets: list[tuple[str, str]] = []
    enriched_units: list[tuple[str, str]] = []
    if comps:
        ql, ss, un = _tp_components_split(comps)
        enriched_quals = sorted(
            [(q["id"], q.get("title", "")) for q in ql if not _is_deleted_record(q)]
        )
        enriched_ssets = sorted(
            [(s["id"], s.get("title", "")) for s in ss if not _is_deleted_record(s)]
        )
        if show_units:
            enriched_units = sorted(
                [(u["id"], u.get("title", "")) for u in un if not _is_deleted_record(u)]
            )

    def belongs_to_package(c: str) -> bool:
        return c.startswith(code)

    # Qualifications
    if show_qualifications:
        if enriched_quals:
            print(f"\n🎓 Qualifications ({len(enriched_quals)}):")
            for c, t in enriched_quals:
                print(f"  • {c} — {t}")
        else:
            quals = []
            for c, rec in idx.by_code.items():
                if not belongs_to_package(c):
                    continue
                if (
                    "qualification" in str(rec.get("type"))
                    and not _is_deleted_record(rec)
                    and not _is_superseded_record(rec)
                ):
                    quals.append((c, rec.get("title", "")))
            if quals:
                print(f"\n🎓 Qualifications ({len(quals)}):")
                for c, t in sorted(quals):
                    print(f"  • {c} — {t}")

    # Skill sets (commonly 'skillSet' type)
    if show_skillsets:
        if enriched_ssets:
            print(f"\n🧩 Skill Sets ({len(enriched_ssets)}):")
            for c, t in enriched_ssets:
                print(f"  • {c} — {t}")
        else:
            ssets = []
            for c, rec in idx.by_code.items():
                if not belongs_to_package(c):
                    continue
                if (
                    (
                        "skillSet" in str(rec.get("type"))
                        or "Skill set" in str(rec.get("type"))
                    )
                    and not _is_deleted_record(rec)
                    and not _is_superseded_record(rec)
                ):
                    ssets.append((c, rec.get("title", "")))
            if ssets:
                print(f"\n🧩 Skill Sets ({len(ssets)}):")
                for c, t in sorted(ssets):
                    print(f"  • {c} — {t}")

    # Units (optional, can be very long)
    if show_units:
        if enriched_units:
            print(f"\n📚 Units ({len(enriched_units)}):")
            for c, t in enriched_units:
                print(f"  • {c} — {t}")
        else:
            units = []
            for c, rec in idx.by_code.items():
                if not belongs_to_package(c):
                    continue
                if (
                    "unit" in str(rec.get("type"))
                    and c != code
                    and not _is_deleted_record(rec)
                ):
                    units.append((c, rec.get("title", "")))
            if units:
                print(f"\n📚 Units ({len(units)}):")
                for c, t in sorted(units):
                    print(f"  • {c} — {t}")


@app.command()
def quals(
    code_or_filter: Optional[str] = typer.Argument(
        None,
        help="Optional filter: training package code (e.g., ICT), unit code to find containing quals, or a specific qual code",
    ),
    index_path: Optional[str] = typer.Option(
        None, "--index-path", help="Path to local NRT index (jsonl.gz)"
    ),
    limit: Optional[int] = typer.Option(
        None, "--limit", "-n", help="Max items to print"
    ),
):
    """List qualifications. The filter can be a package, unit, or qual code."""
    idx = _get_nrt_index(index_path)
    if not idx:
        print("❌ Local index not found. Run 'uoc index' first.")
        raise typer.Exit(1)

    # No filter → list all qualifications
    if not code_or_filter:
        items: list[tuple[str, str]] = []
        for code, rec in idx.by_code.items():
            if (
                "qualification" in str(rec.get("type"))
                and not _is_deleted_record(rec)
                and not _is_superseded_record(rec)
            ):
                items.append((code, rec.get("title", "")))
        items.sort()
        for code, title in items[: (limit or len(items))]:
            print(f"{code} — {title}")
        if not items:
            print("(no qualifications found)")
        return

    q = code_or_filter.upper()
    rec = idx.get(q)

    # Package → list qualifications in package (prefer components)
    if (rec and "trainingPackage" in str(rec.get("type"))) or (
        not rec and q.isalpha() and len(q) in (2, 3, 4) and idx.get_title(q)
    ):
        quals_list: list[tuple[str, str]] = []
        comps = _get_tp_components(q, None, force=False)
        if isinstance(comps, dict) and comps.get("components"):
            ql, _, _ = _tp_components_split(comps)
            if ql:
                quals_list = sorted(
                    [
                        (x["id"], x.get("title", ""))
                        for x in ql
                        if not _is_deleted_record(x) and not _is_superseded_record(x)
                    ]
                )
        # Fallback if components not dict or empty
        if not quals_list:
            for code, r in idx.by_code.items():
                if (
                    code.startswith(q)
                    and "qualification" in str(r.get("type"))
                    and not _is_deleted_record(r)
                    and not _is_superseded_record(r)
                ):
                    quals_list.append((code, r.get("title", "")))
            quals_list.sort()
        for code, title in quals_list[: (limit or len(quals_list))]:
            print(f"{code} — {title}")
        if not quals_list:
            print("(no qualifications found)")
        return

    # Unit → list qualifications containing the unit (prefer official usage endpoint, else related courses)
    if rec and "unit" in str(rec.get("type")):
        try:
            results: list[tuple[str, str]] = []
            usage = _get_unit_usage(q, force=False)
            if usage:
                for it in usage:
                    cid = str(it.get("code", "")).upper()
                    record_type = str(it.get("type", ""))
                    if cid and "qualification" in record_type:
                        title = it.get("title", "")
                        results.append((cid, title))
            else:
                # Fallback to page-scrape-based related courses
                u = UnitOfCompetency(q)
                related = u.get_related_courses()  # returns list of dicts with id/title
                for it in related:
                    cid = it.get("id")
                    if not cid:
                        continue
                    c_rec = idx.get(cid)
                    if c_rec and "qualification" in str(c_rec.get("type")):
                        results.append(
                            (cid, c_rec.get("title", "") or it.get("title", ""))
                        )
            results = sorted(list({r[0]: r for r in results}.values()))
            for code, title in results[: (limit or len(results))]:
                print(f"{code} — {title}")
            if not results:
                print("(no matching qualifications found for unit)")
            return
        except Exception as e:
            print(f"❌ Error resolving unit relations: {e}")
            raise typer.Exit(1)

    # Qualification code → print itself
    if rec and "qualification" in str(rec.get("type")):
        print(f"{q} — {rec.get('title', '')}")
        return

    # Fallback: treat as package prefix filter
    items: list[tuple[str, str]] = []
    for code, r in idx.by_code.items():
        if code.startswith(q) and "qualification" in str(r.get("type")):
            items.append((code, r.get("title", "")))
    items.sort()
    for code, title in items[: (limit or len(items))]:
        print(f"{code} — {title}")
    if not items:
        print("(no qualifications found)")


def _list_units_from_index(
    idx: NRTIndex, pkg_prefix: Optional[str], current_only: bool, limit: Optional[int]
):
    items: list[tuple[str, str]] = []
    for code, rec in idx.by_code.items():
        if pkg_prefix and not code.startswith((pkg_prefix or "").upper()):
            continue
        if "unit" in str(rec.get("type")) and not _is_deleted_record(rec):
            if current_only and "Current" not in str(rec.get("status", "")):
                continue
            items.append((code, rec.get("title", "")))
    items.sort()
    count = 0
    for c, t in items:
        print(f"{c} — {t}")
        count += 1
        if limit and count >= limit:
            break
    if not items:
        print("(no units found)")


@app.command()
def ss(
    code_or_filter: Optional[str] = typer.Argument(
        None,
        help="Filter: package code (e.g., ICT) or unit code to find containing skill sets",
    ),
    index_path: Optional[str] = typer.Option(
        None, "--index-path", help="Path to local NRT index (jsonl.gz)"
    ),
    limit: Optional[int] = typer.Option(
        None, "--limit", "-n", help="Max items to print"
    ),
):
    """List skill sets; filter by package prefix or list skill sets containing a unit code."""
    idx = _get_nrt_index(index_path)
    if not idx:
        print("❌ Local index not found. Run 'uoc index' first.")
        raise typer.Exit(1)
    # If a unit code is provided: use unit usage to list containing skill sets
    if code_or_filter:
        q = code_or_filter.upper()
        rec = idx.get(q)
        if rec and "unit" in str(rec.get("type")):
            usage = _get_unit_usage(q, force=False)
            results: list[tuple[str, str]] = []
            for it in usage:
                record_type = str(it.get("type", ""))
                if "skillset" in record_type.lower():
                    if _is_deleted_record(it) or _is_superseded_record(it):
                        continue
                    results.append(
                        (str(it.get("code", "")).upper(), it.get("title", ""))
                    )
            results = sorted(list({r[0]: r for r in results}.values()))
            for code, title in results[: (limit or len(results))]:
                print(f"{code} — {title}")
            if not results:
                print("(no skill sets found for unit)")
            return

    # Otherwise: list all skill sets, optionally filtered by package prefix
    pkg_prefix = code_or_filter.upper() if code_or_filter else None
    items: list[tuple[str, str]] = []
    for code, rec in idx.by_code.items():
        if pkg_prefix and not code.startswith(pkg_prefix):
            continue
        t = str(rec.get("type"))
        if (
            ("skillSet" in t or "Skill set" in t)
            and not _is_deleted_record(rec)
            and not _is_superseded_record(rec)
        ):
            items.append((code, rec.get("title", "")))
    items.sort()
    count = 0
    for code, title in items:
        print(f"{code} — {title}")
        count += 1
        if limit and count >= limit:
            break
    if not items:
        print("(no skill sets found)")


@app.command()
def units(
    code_or_prefix: Optional[str] = typer.Argument(
        None,
        help="List units. Provide qualification/skill set code or package prefix (e.g., ICT40120, ICTSS00120, ICT). If omitted, lists all units.",
    ),
    index_path: Optional[str] = typer.Option(
        None, "--index-path", help="Override path to local NRT index (jsonl.gz)"
    ),
    current_only: bool = typer.Option(
        True, "--current/--all", help="Show only current units by default"
    ),
    limit: Optional[int] = typer.Option(
        None, "--limit", "-n", help="Max items to print"
    ),
):
    """
    📦 List units by hierarchy:
    - No argument: all units from the index (current by default)
    - Package code (e.g., ICT): units under that package
    - Qualification or Skill Set code: units packaged within it
    """
    idx = _get_nrt_index(index_path)
    if not idx:
        print("❌ Local index not found. Run 'uoc index' first.")
        raise typer.Exit(1)

    # No argument → list all
    if not code_or_prefix:
        _list_units_from_index(idx, None, current_only, limit)
        return

    code = code_or_prefix.upper()
    rec = idx.get(code)

    # Package code → use training package components if available; fallback to index scan
    if rec and "trainingPackage" in str(rec.get("type")):
        comps = _get_tp_components(code, None, force=False)
        units_list: list[tuple[str, str]] = []
        if comps:
            _, _, un = _tp_components_split(comps)
            if un:
                units_list = sorted(
                    [
                        (u["id"], u.get("title", ""))
                        for u in un
                        if not _is_deleted_record(u) and not _is_superseded_record(u)
                    ]
                )
        if not units_list:
            items: list[tuple[str, str]] = []
            for c, r in idx.by_code.items():
                if c.startswith(code) and "unit" in str(r.get("type")):
                    if current_only and "Current" not in str(r.get("status", "")):
                        continue
                    if _is_deleted_record(r) or _is_superseded_record(r):
                        continue
                    items.append((c, r.get("title", "")))
            units_list = sorted(items)
        print(f"📚 Units in package {code} ({len(units_list)}):")
        for c, t in units_list[: (limit or len(units_list))]:
            print(f"• {c} — {t}")
        return

    # Qualification or Skill Set code → unitgrid
    if rec and (
        "qualification" in str(rec.get("type"))
        or "skillSet" in str(rec.get("type"))
        or "Skill set" in str(rec.get("type"))
    ):
        unit_list = _get_qual_units(code, None, force=False)
        title = idx.get_title(code)
        if not unit_list:
            print(f"⚠️  No units found for {code}")
            return
        print(f"📦 Units for {code} — {title}")
        print("=" * 60)
        count = 0
        for u in unit_list:
            if not u.get("title") and idx:
                u["title"] = idx.get_title(u["id"]) or ""
            title_part = f" — {u['title']}" if u.get("title") else ""
            print(f"• {u['id']}{title_part}")
            count += 1
            if limit and count >= limit:
                break
        return

    # Fallback: treat as package prefix filter
    _list_units_from_index(idx, code, current_only, limit)


if __name__ == "__main__":
    main_entry()
