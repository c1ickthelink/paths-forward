#!/usr/bin/env python3
"""Fetch approved RSS/Atom feeds and write news.json for the 'What's changing' page.

Standard library only, so the GitHub Action needs no installs.
Stores headline, link, date and source only, never article text.
One failing feed never stops the others; each feed's status goes into the output.
"""
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.entities import name2codepoint
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CONFIG = HERE / "sources.json"
PINNED = HERE / "pinned.json"
OUT = ROOT / "news.json"

# Browser-like UA: some government sites (BLS) refuse generic bot user agents.
UA = "Mozilla/5.0 (compatible; PathsForwardGeorgia/1.0; +https://c1ickthelink.github.io/paths-forward/)"

# Relevance filter for broad publishers (word-boundary match, case-insensitive).
RELEVANT = r"\b(jobs?|work(ers?|force|place)?|labor|employ\w*|unemploy\w*|wages?|pay|hiring|career\w*|college\w*|universit\w*|degree\w*|graduat\w*|student\w*|apprentic\w*|skills?|training|vocational|trades?|AI|artificial intelligence|automation|robot\w*|entrepreneur\w*|small business\w*|startups?|military|veterans?|occupation\w*)\b"

# Path tags. An item can carry several.
TAGS = {
    "college": r"\b(college\w*|universit\w*|degree\w*|bachelor\w*|graduat\w*|tuition|student loans?|student debt)\b",
    "technical": r"\b(trades?|technical college|vocational|electrician\w*|plumb\w*|HVAC|welder\w*|construction|manufactur\w*|skilled)\b",
    "apprenticeship": r"\b(apprentic\w*)\b",
    "military": r"\b(military|veterans?|armed forces|enlist\w*)\b",
    "work": r"\b(retail|restaurant\w*|food service|hospitality|frontline|front-line|hourly|entry-level|wages?)\b",
    "entrepreneurship": r"\b(entrepreneur\w*|small business\w*|startups?|self-employ\w*|business formation\w*)\b",
    "ai": r"\bAI\b|(?i:\b(artificial intelligence|automation|generative|chatbots?|robot\w*|LLMs?)\b)",
}

def text(el):
    return unescape(re.sub(r"\s+", " ", "".join(el.itertext()))).strip() if el is not None else ""

def parse_date(s):
    if not s:
        return None
    s = s.strip()
    try:
        d = parsedate_to_datetime(s)  # RFC 822 (RSS)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))  # ISO 8601 (Atom)
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

def local(tag):
    return tag.rsplit("}", 1)[-1]

def find(el, name):
    for c in el:
        if local(c.tag) == name:
            return c
    return None

XML_ENTITIES = {b"amp", b"lt", b"gt", b"quot", b"apos"}

def fix_entities(xml_bytes):
    """Some feeds (Brookings) use HTML entities like &nbsp; that strict XML rejects. Convert them to numeric refs."""
    def rep(m):
        name = m.group(1)
        if name in XML_ENTITIES:
            return m.group(0)
        cp = name2codepoint.get(name.decode("ascii", "ignore"))
        return b"&#%d;" % cp if cp else b""
    xml_bytes = re.sub(rb"&([A-Za-z][A-Za-z0-9]{1,31});", rep, xml_bytes)
    # Bare ampersands ("AT&T", "Q&A") are also invalid XML; escape any & that doesn't start a reference.
    return re.sub(rb"&(?!#[0-9]+;|#x[0-9A-Fa-f]+;|[A-Za-z][A-Za-z0-9]*;)", b"&amp;", xml_bytes)

def parse_feed(xml_bytes):
    root = ET.fromstring(fix_entities(xml_bytes))
    items = []
    for el in root.iter():
        kind = local(el.tag)
        if kind not in ("item", "entry"):
            continue
        title = text(find(el, "title"))
        link_el = find(el, "link")
        link = ""
        if link_el is not None:
            link = link_el.get("href") or text(link_el)
        date = None
        for n in ("pubDate", "published", "updated", "date"):
            date = parse_date(text(find(el, n)))
            if date:
                break
        desc = text(find(el, "description")) or text(find(el, "summary"))
        if title and link:
            items.append({"title": title, "url": link.strip(), "date": date, "_desc": desc})
    return items

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.5"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

def main():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    cutoff = datetime.now(timezone.utc) - timedelta(days=cfg.get("max_age_days", 75))
    per = cfg.get("max_per_source", 12)
    all_items, status = [], []
    for src in cfg["sources"]:
        try:
            items = parse_feed(fetch(src["url"]))
            kept = []
            for it in items:
                if it["date"] and it["date"] < cutoff:
                    continue
                hay = f'{it["title"]} {it["_desc"]}'
                if src.get("filter") and not re.search(RELEVANT, hay, re.I):
                    continue
                if src.get("require") and not re.search(src["require"], hay, re.I):
                    continue
                # "AI" is matched case-sensitively so words like "said" never tag; the rest ignore case.
                tags = [t for t, rx in TAGS.items() if re.search(rx, hay, 0 if t == "ai" else re.I)]
                tags += [t for t in src.get("tags", []) if t not in tags]
                kept.append({
                    "title": it["title"][:220],
                    "url": it["url"],
                    "date": it["date"].date().isoformat() if it["date"] else None,
                    "source": src["name"],
                    "kind": src.get("kind", "news"),
                    "tags": tags,
                })
            kept.sort(key=lambda x: x["date"] or "", reverse=True)
            kept = kept[:per]
            all_items.extend(kept)
            status.append({"name": src["name"], "ok": True, "count": len(kept)})
        except Exception as e:  # keep going; record the failure
            status.append({"name": src["name"], "ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}"})
            print(f"WARN {src['name']}: {e}", file=sys.stderr)

    # Hand-picked key reads: always included, exempt from the age cutoff, listed first.
    pinned = []
    if PINNED.exists():
        for it in json.loads(PINNED.read_text(encoding="utf-8")).get("items", []):
            pinned.append({"title": it["title"], "url": it["url"], "date": it.get("date"), "source": it["source"],
                           "kind": "pinned", "tags": it.get("tags", []), "note": it.get("note", ""), "pinned": True})
    pinned_urls = {p["url"] for p in pinned}

    seen, uniq = set(pinned_urls), list(pinned)
    feed_count = 0
    for it in sorted(all_items, key=lambda x: x["date"] or "", reverse=True):
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        uniq.append(it)
        feed_count += 1

    # Keep the previous file if every feed failed, so a bad night doesn't blank the page.
    if feed_count == 0 and OUT.exists() and json.loads(OUT.read_text(encoding="utf-8")).get("sources"):
        print("All sources empty or failed; keeping previous news.json", file=sys.stderr)
        return

    OUT.write_text(json.dumps({
        "updated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "items": uniq,
        "sources": status,
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(pinned)} pinned + {feed_count} feed items from {sum(s['ok'] for s in status)}/{len(status)} sources")

if __name__ == "__main__":
    main()
