#!/usr/bin/env python3
"""
update_publications.py - pulls the publication list from INSPIRE-HEP into data/publications.json

    python update_publications.py          # fetch, then rebuild the site

Which INSPIRE profiles are used?  settings.publication_sources in data/site.json
(default: the group lead's INSPIRE id).  Several sources are merged and de-duplicated.
Standard library only (Python 3.8+).  Needs internet access.
"""
import datetime
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
API = "https://inspirehep.net/api/literature"
FIELDS = ("titles,authors.full_name,author_count,publication_info,arxiv_eprints,dois,citation_count,"
          "control_number,earliest_date,preprint_date,document_type,collaborations.value")
UA = "group-website-publications/1.0 (static site builder)"
MAX_AUTHORS_STORED = 60


def http_json(url, retries=4):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503, 504):
                wait = int(e.headers.get("Retry-After", 0) or 0) or 2 ** (attempt + 1)
                time.sleep(min(wait, 30))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError("Could not reach INSPIRE-HEP (%s)" % last)


def parse_recid(value):
    """Accepts '1046872' or a profile URL such as https://inspirehep.net/authors/1046872?..."""
    value = str(value or "").strip()
    m = re.search(r"authors/(\d+)", value)
    if m:
        return m.group(1)
    return value if re.match(r"^\d+$", value) else ""


def fmt_name(n):
    """'Last, First' -> 'First Last'."""
    n = (n or "").strip()
    if "," in n:
        last, first = [x.strip() for x in n.split(",", 1)]
        return ("%s %s" % (first, last)).strip()
    return n


def fmt_journal(pub_info):
    for pi in pub_info or []:
        j = pi.get("journal_title")
        if not j:
            continue
        vol = pi.get("journal_volume", "")
        yr = pi.get("year", "")
        art = pi.get("artid") or pi.get("page_start") or ""
        s = j
        if vol:
            s += " " + str(vol)
        if yr:
            s += " (%s)" % yr
        if art:
            s += " " + str(art)
        return s.strip(), str(yr or "")
    return "", ""


def parse_hit(hit):
    md = hit.get("metadata", {})
    titles = md.get("titles") or [{}]
    title = titles[0].get("title", "(untitled)")
    authors = [fmt_name(a.get("full_name", "")) for a in md.get("authors", [])]
    n_auth = md.get("author_count") or len(authors)
    arx = ""
    if md.get("arxiv_eprints"):
        arx = md["arxiv_eprints"][0].get("value", "")
    doi = (md.get("dois") or [{}])[0].get("value", "")
    journal, jyear = fmt_journal(md.get("publication_info"))
    date = md.get("earliest_date") or md.get("preprint_date") or ""
    year = jyear or date[:4]
    recid = str(md.get("control_number") or hit.get("id") or "")
    dtypes = md.get("document_type") or []
    if journal:
        kind = "proceedings" if "conference paper" in dtypes and "article" not in dtypes else "article"
    else:
        kind = "preprint"
    return {
        "id": arx or ("inspire-" + recid),
        "recid": recid,
        "authors": authors[:MAX_AUTHORS_STORED],
        "author_count": n_auth,
        "title": title,
        "journal": journal,
        "year": year,
        "date": date or year,
        "arxiv": arx,
        "doi": doi,
        "citations": md.get("citation_count"),
        "type": kind,
        "inspire_url": ("https://inspirehep.net/literature/" + recid) if recid else "",
    }


def fetch_author(recid, log=print):
    papers, page, size, total = [], 1, 100, None
    while True:
        params = {"q": "authors.recid:%s" % recid, "size": size, "page": page, "sort": "mostrecent", "fields": FIELDS}
        data = http_json(API + "?" + urllib.parse.urlencode(params))
        hits = data.get("hits", {}).get("hits", [])
        if total is None:
            total = data.get("hits", {}).get("total", 0)
        if not hits:
            break
        papers.extend(parse_hit(h) for h in hits)
        log("  fetched page %d (%d records, %d / %s)" % (page, len(hits), len(papers), total))
        if len(papers) >= (total or 0):
            break
        page += 1
        time.sleep(0.4)
    return papers


def fetch_by_arxiv(arxiv_id):
    """Title / authors / abstract / date for one arXiv id (used when adding a research highlight)."""
    arxiv_id = re.sub(r"^(arxiv:|https?://arxiv\.org/abs/)", "", str(arxiv_id).strip(), flags=re.I)
    params = {"q": "arxiv:%s" % arxiv_id, "size": 1, "fields": FIELDS + ",abstracts"}
    data = http_json(API + "?" + urllib.parse.urlencode(params), retries=2)
    hits = data.get("hits", {}).get("hits", [])
    if not hits:
        return None
    p = parse_hit(hits[0])
    abstracts = hits[0].get("metadata", {}).get("abstracts") or [{}]
    p["abstract"] = re.sub(r"\s+", " ", re.sub(r"</?inspire:[^>]*>|<[^>]+>", "", abstracts[0].get("value", ""))).strip()
    return p


def sources_from_site(site):
    s = site.get("settings", {})
    src = [x for x in s.get("publication_sources", []) if parse_recid(x.get("inspire"))]
    if src:
        return [{"label": x.get("label", ""), "recid": parse_recid(x["inspire"])} for x in src]
    lead = next((m for m in site.get("members", []) if m.get("id") == s.get("lead_member")), None)
    if lead and parse_recid(lead.get("inspire")):
        return [{"label": lead["name"], "recid": parse_recid(lead["inspire"])}]
    return []


def update(log=print):
    """Fetch every source, merge, write data/publications.json. Returns number of papers (or None on failure)."""
    site = json.loads((DATA / "site.json").read_text(encoding="utf-8"))
    sources = sources_from_site(site)
    if not sources:
        log("No INSPIRE source configured. Give the group lead an INSPIRE id (manage.py -> Team) "
            "or add a source under Publications.")
        return None
    merged, seen = [], set()
    try:
        for s in sources:
            log("Fetching %s (INSPIRE author %s) ..." % (s["label"] or "?", s["recid"]))
            for p in fetch_author(s["recid"], log):
                if p["id"] in seen:
                    continue
                seen.add(p["id"])
                merged.append(p)
    except Exception as e:  # network trouble must never destroy the existing list
        log("INSPIRE update failed: %s\nThe existing publication list was left untouched." % e)
        return None
    if not merged:
        log("INSPIRE returned no papers; keeping the existing list.")
        return None
    merged.sort(key=lambda p: p.get("date") or p.get("year") or "", reverse=True)
    out = {"fetched_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "sources": sources, "papers": merged}
    (DATA / "publications.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    log("Saved %d papers to data/publications.json" % len(merged))
    return len(merged)


if __name__ == "__main__":
    n = update()
    if n:
        sys.path.insert(0, str(ROOT))
        import sitegen
        sitegen.build()
    else:
        sys.exit(1)
