"""Bounded offline XML/GZIP sitemap import; never fetches nested sitemap URLs.

Supports operator-provided URLSET files only. Actual crawl requests remain
subject to the HTTPS allowlist, robots preflight and scheduled host limits.
"""
from __future__ import annotations

from gzip import GzipFile
from io import BytesIO
from pathlib import Path

from defusedxml.ElementTree import fromstring
from defusedxml.common import DefusedXmlException
from xml.etree.ElementTree import ParseError

from .frontier import _https_url
from .security import hostname

MAX_BYTES = 5 * 1024 * 1024
MAX_URLS = 10000


def _tag(name: str) -> str:
    return name.rsplit("}", 1)[-1]


def read_sitemap_file(
    file_path: str | Path, *, host: str, max_bytes: int = MAX_BYTES,
    max_urls: int = MAX_URLS,
) -> list[str]:
    """Return unique same-host HTTPS URLs from an operator-supplied sitemap.

    Input can be .xml or .xml.gz. Both raw and inflated size are bounded and
    DTDs/entities/external entities are forbidden.
    """
    if not 1 <= max_bytes <= MAX_BYTES or not 1 <= max_urls <= MAX_URLS:
        raise ValueError("Invalid sitemap size/URL limit")
    if not host or any(c in host for c in "/:@?#\\"):
        raise ValueError("Expected a bare DNS hostname for the sitemap allowlist")
    approved_host = hostname("https://" + host + "/")
    path = Path(file_path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("Sitemap must be a regular local file")
    with path.open("rb") as stream:
        raw = stream.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError("Sitemap exceeds size limit")

    if path.name.endswith(".gz"):
        try:
            with GzipFile(fileobj=BytesIO(raw)) as gz:
                raw = gz.read(max_bytes + 1)
        except (OSError, EOFError) as exc:
            raise ValueError("Malformed compressed sitemap") from exc
        if len(raw) > max_bytes:
            raise ValueError("Inflated sitemap exceeds size limit")
    try:
        root = fromstring(raw, forbid_dtd=True, forbid_entities=True,
                          forbid_external=True)
    except (DefusedXmlException, ParseError, ValueError) as exc:
        raise ValueError("Malformed or unsafe sitemap XML") from exc
    if _tag(root.tag) != "urlset":
        raise ValueError("Only URLSET sitemaps are accepted; nested indexes are not fetched")
    result: dict[str, None] = {}
    for child in root:
        if _tag(child.tag) != "url":
            continue
        loc = next(
            (field.text for field in child if _tag(field.tag) == "loc"),
            None,
        )
        if not loc:
            continue
        url = _https_url(loc.strip())
        if hostname(url) != approved_host:
            raise ValueError("Sitemap contains URL outside explicitly approved host")
        result[url] = None
        if len(result) > max_urls:
            raise ValueError("Sitemap exceeds URL count limit")
    return list(result)
