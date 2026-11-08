#!/usr/bin/env python3
"""
sitegen.py - builds the whole static website from  data/site.json  and  data/publications.json

    python sitegen.py            # rebuild every .html page in this folder

You normally do not run this by hand: manage.py rebuilds automatically after every change.
Design lives in assets/css/style.css and assets/js/main.js (plain files, edit freely).
Standard library only (Python 3.8+).
"""
import datetime
import html
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

ROLE_ORDER = [("pi", "Principal Investigator", "Principal Investigator"),
              ("postdoc", "Postdoctoral Researchers", "Postdoctoral Researcher"),
              ("phd", "Doctoral Students", "Doctoral Student"),
              ("masters", "Masters & Project Students", "Masters Student"),
              ("visitor", "Visitors & Interns", "Visitor")]
ALUM_ORDER = [("phd", "PhD Alumni"), ("postdoc", "Postdoctoral Alumni"),
              ("masters", "Masters & Project Students"), ("other", "Other Former Members")]

# --------------------------------------------------------------------------- helpers


def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


def clean_title(t):
    """INSPIRE titles can contain <inspire:math> tags and entities; keep plain text + $latex$."""
    t = html.unescape(str(t or ""))
    t = re.sub(r"</?inspire:[^>]*>", "", t)
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"\s+", " ", t).strip()


def T(t):
    return esc(clean_title(t))


def safe_url(u):
    u = (u or "").strip()
    if not u:
        return ""
    if re.match(r"^(https?://|mailto:)", u, re.I):
        return u
    if re.match(r"^[\w./#?=&;%~+-]+$", u):          # relative link, no scheme
        return u
    if re.match(r"^[\w.-]+\.[a-z]{2,}(/.*)?$", u, re.I):  # bare domain
        return "https://" + u
    return ""


def rich(text):
    """Escape, then allow [label](url), **bold**, *italic*."""
    s = esc(text)

    def link(m):
        url = safe_url(html.unescape(m.group(2)))
        if not url:
            return m.group(1)
        ext = url.startswith("http")
        extra = ' target="_blank" rel="noopener noreferrer"' if ext else ""
        return '<a href="%s"%s>%s</a>' % (esc(url), extra, m.group(1))
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"<em>\1</em>", s)
    return s


def slugify(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "item"


def initials(name):
    toks = [t for t in re.findall(r"[^\W\d_]+", name or "", re.U) if len(t) > 1 or True]
    if not toks:
        return "?"
    if len(toks) == 1:
        return toks[0][0].upper()
    return (toks[0][0] + toks[-1][0]).upper()


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fmt_date(d):
    d = str(d or "").strip()
    m = re.match(r"^(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?", d)
    if not m:
        return d
    y, mo, da = m.groups()
    if mo and 1 <= int(mo) <= 12:
        out = "%s %s" % (MONTHS[int(mo) - 1], y)
        if da:
            out = "%d %s" % (int(da), out)
        return out
    return y


def dkey(d):
    m = re.match(r"^(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?", str(d or ""))
    if not m:
        return "0000-00-00"
    y, mo, da = m.groups()
    return "%s-%02d-%02d" % (y, int(mo or 0), int(da or 0))


def sig(name):
    """(last name, first initial) signature used to recognise people in author lists."""
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    toks = re.findall(r"[a-z]+", s)
    if len(toks) < 2:
        return None
    return (toks[-1], toks[0][0])


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


# --------------------------------------------------------------------------- icons

ARROW = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>'
EXT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 17 17 7M8 7h9v9"/></svg>'
MOON = '<svg class="ico-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 13.2A8.5 8.5 0 1 1 10.8 3 6.6 6.6 0 0 0 21 13.2z"/></svg>'
SUN = '<svg class="ico-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>'
TROPHY = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 4h8v5a4 4 0 0 1-8 0zM8 6H5v2a3 3 0 0 0 3 3M16 6h3v2a3 3 0 0 1-3 3M12 13v4M8 20h8M10 17h4"/></svg>'
AREA_ICONS = {
    "cmb": '<circle cx="12" cy="12" r="9"/><path d="M3.2 11c3-2.8 5.6 2.6 8.8 0s5.8 2.6 8.8 0"/><path d="M6 5.8c2.2 1.6 4.6-.8 6.4.6"/><circle class="f" cx="16.5" cy="16.5" r="1.1"/>',
    "lss": '<path d="M5 6l7 5 7-4M12 11v8M5 6v9l7 4 7-4V7"/><circle class="f" cx="5" cy="6" r="1.6"/><circle class="f" cx="12" cy="11" r="1.6"/><circle class="f" cx="19" cy="7" r="1.6"/><circle class="f" cx="12" cy="19" r="1.6"/>',
    "21cm": '<path d="M2 12h3.5l2-6 3 12 3-9 1.6 3H22"/><circle class="f" cx="19" cy="6" r="1.4"/>',
    "dipole": '<circle cx="12" cy="12" r="9"/><path d="M8 16l8-8M10.5 8H16v5.5"/>',
    "entropy": '<path d="M4 19V10M9 19V5M14 19v-7M19 19V8"/><circle class="f" cx="9" cy="3.6" r="1.1"/>',
    "theory": '<path d="M3 18c4-13 14-13 18 0"/><circle class="f" cx="12" cy="7.4" r="1.7"/><path d="M3 21h18"/>',
    "star": '<path d="M12 3l2.4 6 6.6.5-5 4.3 1.6 6.4L12 16.7 6.4 20.2 8 13.8 3 9.5 9.6 9z"/>',
}


def area_icon(key):
    return '<svg viewBox="0 0 24 24" aria-hidden="true">%s</svg>' % AREA_ICONS.get(key, AREA_ICONS["star"])


# --------------------------------------------------------------------------- data model


class Site:
    def __init__(self):
        self.d = load_json(DATA / "site.json", {})
        self.s = self.d.get("settings", {})
        self.members = self.d.get("members", [])
        self.alumni = self.d.get("alumni", [])
        pub = load_json(DATA / "publications.json", {"papers": []})
        self.pub_meta = pub
        hidden = set(self.d.get("publications_hidden", []))
        papers, seen = [], set()
        for p in list(pub.get("papers", [])) + list(self.d.get("publications_manual", [])):
            pid = p.get("id") or p.get("arxiv") or p.get("title")
            if pid in hidden or pid in seen:
                continue
            seen.add(pid)
            q = dict(p)
            q["id"] = pid
            papers.append(q)
        papers.sort(key=lambda p: dkey(p.get("date") or p.get("year")), reverse=True)
        self.papers = papers
        # people recognised in author lists
        self.people = {}
        for m in self.members + self.alumni:
            for nm in [m.get("name", "")] + list(m.get("pub_names", [])):
                sg = sig(nm)
                if sg:
                    self.people[sg] = m["id"]
        self.today = datetime.date.today()

    def g(self, key, default=""):
        return self.s.get(key, default)

    # --- publications
    def paper_people(self, p):
        ids = []
        for a in p.get("authors", []):
            pid = self.people.get(sig(a))
            if pid and pid not in ids:
                ids.append(pid)
        return ids

    def stats(self):
        n = len(self.papers)
        cites = [p.get("citations") for p in self.papers if isinstance(p.get("citations"), int)]
        total = sum(cites) if cites else None
        h = None
        if cites:
            h = 0
            for i, c in enumerate(sorted(cites, reverse=True), 1):
                if c >= i:
                    h = i
        co = set()
        for p in self.papers:
            for a in p.get("authors", []):
                sg = sig(a)
                if sg:
                    co.add(sg)
        return {"papers": n, "cites": total, "h": h, "coauthors": len(co)}


# --------------------------------------------------------------------------- page shell

NAV = [("index.html", "Home"), ("team.html", "Team"), ("research.html", "Research"),
       ("publications.html", "Publications"), ("news.html", "News"), ("gallery.html", "Gallery")]
MORE = [("former.html", "Former Members"), ("collab.html", "Collaborations"), ("calendar.html", "Calendar")]
LAST = [("contact.html", "Contact")]

MARK = ('<svg class="mark" viewBox="0 0 40 40" aria-hidden="true"><defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#7cc4ff"/><stop offset=".55" stop-color="#8b7bff"/><stop offset="1" stop-color="#ffb454"/></linearGradient></defs>'
        '<circle cx="20" cy="20" r="18.5" fill="none" stroke="url(#lg)" stroke-width="1.5"/>'
        '<ellipse cx="20" cy="20" rx="18.5" ry="7" fill="none" stroke="url(#lg)" stroke-width="1.2" transform="rotate(-28 20 20)"/>'
        '<circle cx="20" cy="20" r="4.2" fill="url(#lg)"/><circle cx="33.4" cy="12.2" r="2" fill="#ffb454"/></svg>')

FAVICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
           '<stop offset="0" stop-color="#7cc4ff"/><stop offset=".55" stop-color="#8b7bff"/><stop offset="1" stop-color="#ffb454"/></linearGradient></defs>'
           '<rect width="40" height="40" rx="9" fill="#060818"/><circle cx="20" cy="20" r="14" fill="none" stroke="url(#g)" stroke-width="1.8"/>'
           '<ellipse cx="20" cy="20" rx="14" ry="5.4" fill="none" stroke="url(#g)" stroke-width="1.4" transform="rotate(-28 20 20)"/>'
           '<circle cx="20" cy="20" r="3.4" fill="url(#g)"/><circle cx="30.2" cy="13.6" r="1.7" fill="#ffb454"/></svg>')


def nav_html(S, current):
    def a(f, label):
        on = ' class="on" aria-current="page"' if f == current else ""
        return '<a href="%s"%s>%s</a>' % (f, on, esc(label))
    more_on = any(f == current for f, _ in MORE)
    dd = ('<div class="dd"><button type="button" aria-haspopup="true" aria-expanded="false"%s>More</button><div class="dd-menu">%s</div></div>'
          % (' class="on"' if more_on else "", "".join(a(f, l) for f, l in MORE)))
    return ('<nav class="links" id="links" aria-label="Main">%s%s%s</nav>'
            % ("".join(a(f, l) for f, l in NAV), dd, "".join(a(f, l) for f, l in LAST)))


def shell(S, current, title, body, desc="", math=False, home=False):
    g = S.g
    full_title = g("group_name") if home else "%s · %s" % (title, g("group_name"))
    desc = desc or g("tagline")
    foot_links = "".join('<li><a href="%s">%s</a></li>' % (f, esc(l)) for f, l in NAV + MORE + LAST)
    social = "".join('<li><a href="%s" target="_blank" rel="noopener noreferrer">%s</a></li>' % (esc(safe_url(x.get("url"))), esc(x.get("label")))
                     for x in g("social", []) if safe_url(x.get("url")))
    emails = []
    for e in [g("email"), g("group_email")]:
        if e and e not in emails:
            emails.append(e)
    email_html = "".join('<li><a href="mailto:%s">%s</a></li>' % (esc(e), esc(e)) for e in emails)
    return """<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="%(desc)s">
<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(desc)s">
<meta property="og:type" content="website">
<meta name="theme-color" content="#04050d">
<link rel="icon" href="images/site/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="assets/css/style.css">
<script>try{document.documentElement.setAttribute('data-theme',localStorage.getItem('csp-theme')||'%(theme)s')}catch(e){}document.documentElement.classList.add('js')</script>
</head>
<body class="page-%(page)s">
<canvas id="stars" aria-hidden="true"></canvas>
<div class="aurora" aria-hidden="true"><i></i><i></i></div>
<a class="skip" href="#main">Skip to content</a>
<header class="nav" id="nav">
  <div class="wrap nav-in">
    <a class="brand" href="index.html" aria-label="%(group)s - home">%(mark)s<span class="brand-t"><b>%(brand)s</b><small>%(inst)s</small></span></a>
    %(nav)s
    <button class="icon-btn" id="theme" type="button" aria-label="Toggle light / dark theme">%(moon)s%(sun)s</button>
    <button class="burger" id="burger" type="button" aria-label="Menu" aria-expanded="false" aria-controls="links"><i></i><i></i><i></i></button>
  </div>
</header>
<main id="main">
%(body)s
</main>
<footer class="foot">
  <div class="wrap">
    <div class="foot-grid">
      <div>
        <p class="fb">%(group)s</p>
        <p>%(inst)s<br>%(city)s</p>
        <p class="muted">%(tagline)s</p>
      </div>
      <div><h4>Explore</h4><ul>%(flinks)s</ul></div>
      <div><h4>Contact</h4><ul>%(emails)s%(social)s</ul></div>
    </div>
    <div class="foot-bot"><span>&copy; %(year)s %(group)s</span><span>Last updated: %(updated)s</span></div>
  </div>
</footer>
<script src="assets/js/main.js" defer></script>
</body>
</html>
""" % dict(title=esc(full_title), desc=esc(desc), theme=esc(g("default_theme", "dark")),
           page=slugify(current.replace(".html", "")), group=esc(g("group_name")), brand=esc(g("brand_title") or g("group_name")),
           inst=esc(g("institute")), city=esc(g("city")), tagline=esc(g("tagline")), mark=MARK,
           nav=nav_html(S, current), moon=MOON, sun=SUN, body=body, flinks=foot_links, emails=email_html,
           social=social, year=S.today.year, updated=fmt_date(S.today.isoformat()) if False else S.today.strftime("%d %b %Y").lstrip("0"))


def phead(S, crumb, title, lede=""):
    return """<section class="phead">
  <div class="wrap">
    <p class="crumbs"><a href="index.html">Home</a><span>/</span>%s</p>
    <h1 class="display reveal">%s</h1>
    %s
  </div>
</section>""" % (esc(crumb), rich(title), ('<p class="lede reveal" style="--d:.1s">%s</p>' % rich(lede)) if lede else "")


def sec_head(eyebrow, title, sub="", link=None):
    right = ""
    if link:
        right = '<a class="sec-link" href="%s">%s %s</a>' % (link[0], esc(link[1]), ARROW)
    return ('<div class="sec-head reveal"><p class="eyebrow">%s</p><h2>%s</h2>%s</div>' % (
        esc(eyebrow), rich(title), ('<p class="sub">%s</p>' % rich(sub)) if sub else "") if not link else
        '<div class="sec-head reveal"><p class="eyebrow">%s</p><h2>%s</h2>%s</div>' % (esc(eyebrow), rich(title), right))


def pill(label, url, cls=""):
    url = safe_url(url)
    if not url:
        return ""
    ext = url.startswith("http")
    return '<a class="pill %s" href="%s"%s>%s%s</a>' % (
        cls, esc(url), ' target="_blank" rel="noopener noreferrer"' if ext else "", esc(label), EXT if ext else "")


# --------------------------------------------------------------------------- reusable blocks


def inspire_link(m):
    v = str(m.get("inspire") or "").strip()
    if not v:
        nm = m.get("name", "")
        if sig(nm):
            return "INSPIRE search", "https://inspirehep.net/authors?q=" + quote(nm)
        return None, None
    if v.startswith("http"):
        return "INSPIRE", v
    if re.match(r"^\d+$", v):
        return "INSPIRE", "https://inspirehep.net/authors/%s?ui-citation-summary=true" % v
    return "INSPIRE", "https://inspirehep.net/authors?q=" + quote(v)


def person_links(m, mail=True):
    out = []
    lab, url = inspire_link(m)
    if url:
        out.append(pill(lab, url, "inspire"))
    for l in m.get("links", []):
        out.append(pill(l.get("label", "Link"), l.get("url", "")))
    if mail and m.get("email"):
        out.append(pill("Email", "mailto:" + m["email"]))
    return '<div class="links-row">%s</div>' % "".join(out)


def avatar(m, cls=""):
    photo = m.get("photo", "")
    img = ('<img src="%s" alt="%s" loading="lazy" onerror="this.remove()">' % (esc(photo), esc(m.get("name"))) if photo else "")
    return '<div class="avatar %s"><span>%s</span>%s</div>' % (cls, esc(initials(m.get("name"))), img)


def tags_html(tags):
    tags = [t for t in tags or [] if str(t).strip()]
    return ('<div class="tags">%s</div>' % "".join('<span class="tag">%s</span>' % esc(t) for t in tags)) if tags else ""


def person_card(m, lead=False, delay=0):
    role_title = m.get("title") or dict((r[0], r[2]) for r in ROLE_ORDER).get(m.get("role"), "")
    rows = []
    if m.get("degree"):
        rows.append('<p class="row"><b>PhD</b> &middot; %s</p>' % esc(m["degree"]))
    if m.get("research"):
        rows.append('<p class="row"><b>Research</b> &middot; %s</p>' % esc(m["research"]))
    if m.get("email"):
        rows.append('<p class="row"><b>Email</b> &middot; <a href="mailto:%s">%s</a></p>' % (esc(m["email"]), esc(m["email"])))
    bio = '<p class="bio">%s</p>' % rich(m["bio"]) if m.get("bio") else ""
    return """<article class="card person%s reveal" id="%s" style="--d:%.2fs">
  %s
  <div class="p-body">
    <h3>%s</h3>
    <p class="role">%s</p>
    %s%s%s
    %s
  </div>
</article>""" % (" lead" if lead else "", esc(m["id"]), delay, avatar(m), esc(m["name"]), esc(role_title), "".join(rows), bio,
                 tags_html(m.get("tags")), person_links(m, mail=False))


def alum_card(a, delay=0):
    rows = []
    if a.get("thesis"):
        rows.append('<p class="row"><b>Thesis</b> &middot; %s</p>' % esc(a["thesis"]))
    if a.get("research") and not a.get("thesis"):
        rows.append('<p class="row"><b>Research</b> &middot; %s</p>' % esc(a["research"]))
    if a.get("year"):
        rows.append('<p class="row"><b>%s</b> &middot; %s</p>' % ("Years" if "-" in str(a["year"]) or "–" in str(a["year"]) else "Year", esc(a["year"])))
    if a.get("now_at"):
        rows.append('<p class="row"><b>Now at</b> &middot; %s</p>' % esc(a["now_at"]))
    bio = '<p class="bio">%s</p>' % rich(a["bio"]) if a.get("bio") else ""
    return """<article class="card person alum reveal" id="%s" style="--d:%.2fs">
  %s
  <div class="p-body">
    <h3>%s</h3>
    %s%s%s
    %s
  </div>
</article>""" % (esc(a["id"]), delay, avatar(a), esc(a["name"]), "".join(rows), bio, tags_html(a.get("tags")), person_links(a, mail=False))


def find_paper(S, arxiv):
    for p in S.papers:
        if arxiv and p.get("arxiv") == arxiv:
            return p
    return None


def hl_card(S, h, big=False, delay=0):
    ax = h.get("arxiv", "")
    p = find_paper(S, ax)
    authors = h.get("authors") or (", ".join(p.get("authors", [])[:8]) + (" et al." if p and len(p.get("authors", [])) > 8 else "") if p else "")
    venue = h.get("journal") or (p.get("journal") if p else "") or ("arXiv:" + ax if ax else "")
    date = fmt_date(h.get("date") or (p.get("date") if p else ""))
    summ = h.get("summary", "")
    links = []
    if ax:
        links.append(pill("arXiv", "https://arxiv.org/abs/" + ax, "inspire"))
    doi = h.get("doi") or (p.get("doi") if p else "")
    if doi:
        links.append(pill("DOI", "https://doi.org/" + doi))
    for l in h.get("links", []):
        links.append(pill(l.get("label", "Link"), l.get("url", "")))
    img = h.get("image", "")
    label = ("arXiv " + ax) if ax else "Add image"
    figure = '<figure><span class="ph">%s</span>%s</figure>' % (
        esc(label), ('<img src="%s" alt="%s" loading="lazy" onerror="this.remove()">' % (esc(img), esc(clean_title(h.get("title")))) if img else ""))
    toggle = '<button class="toggle" type="button">Read abstract</button>' if len(summ) > 260 else ""
    return """<article class="card hl%s reveal" style="--d:%.2fs">
  %s
  <div class="hl-body">
    <div class="hl-meta"><span>%s</span><span>%s</span></div>
    <h3 data-tex>%s</h3>
    %s
    <p class="abs">%s</p>%s
    <div class="links-row">%s</div>
  </div>
</article>""" % (" big" if big else "", delay, figure, esc(date), esc(venue), T(h.get("title")),
                 ('<p class="by">%s</p>' % esc(authors)) if authors else "", esc(summ), toggle, "".join(links))


def news_item(n, kind_attr=True):
    link = ""
    if safe_url(n.get("link")):
        ext = safe_url(n["link"]).startswith("http")
        link = '<a class="more" href="%s"%s>%s &rarr;</a>' % (esc(safe_url(n["link"])), ' target="_blank" rel="noopener noreferrer"' if ext else "", esc(n.get("link_label") or "Read more"))
    kind = n.get("kind", "News")
    return """<li class="tl reveal%s" data-kind="%s">
  <div class="when"><span>%s</span><span class="kind">%s</span></div>
  <h3>%s</h3>
  %s
  %s
</li>""" % (" t-award" if kind.lower() == "award" else "", esc(kind), esc(fmt_date(n.get("date"))), esc(kind), rich(n.get("title")),
            ('<p>%s</p>' % rich(n["text"])) if n.get("text") else "", link)


def award_card(a):
    link = ""
    if safe_url(a.get("link")):
        link = ' <a href="%s" target="_blank" rel="noopener noreferrer">More &rarr;</a>' % esc(safe_url(a["link"]))
    who = " &middot; ".join(x for x in [esc(a.get("who")), esc(fmt_date(a.get("date")))] if x)
    return """<div class="card award reveal"><div class="trophy">%s</div><div><p class="w">%s</p><h3>%s</h3>%s</div></div>""" % (
        TROPHY, who, rich(a.get("title")), ('<p>%s%s</p>' % (rich(a["text"]), link)) if a.get("text") else ('<p>%s</p>' % link.strip() if link else ""))


def sorted_news(S):
    return sorted(S.d.get("news", []), key=lambda n: dkey(n.get("date")), reverse=True)


def sorted_awards(S):
    return sorted(S.d.get("awards", []), key=lambda n: dkey(n.get("date")), reverse=True)


def pub_item(S, p):
    authors = p.get("authors", [])
    me_ids = S.paper_people(p)
    parts = []
    for a in authors:
        e = esc(a)
        parts.append('<b class="me">%s</b>' % e if S.people.get(sig(a)) else e)
    shown, rest = parts[:8], parts[8:]
    ah = ", ".join(shown)
    extra = int(p.get("author_count") or 0) - len(authors)
    if rest or extra > 0:
        tail = (", " + ", ".join(rest)) if rest else ""
        if extra > 0:
            tail += " <i>et al.</i>"
        n_more = len(rest) + (extra if extra > 0 else 0)
        ah += '<span class="rest">%s</span> <button type="button" class="more-btn">+%d more</button>' % (tail, n_more)
    year = str(p.get("year") or str(p.get("date", ""))[:4] or "")
    if p.get("journal"):
        venue = '<span class="venue">%s</span>' % esc(p["journal"])
    elif p.get("arxiv"):
        venue = '<span class="pre">Preprint &middot; arXiv:%s</span>' % esc(p["arxiv"])
    else:
        venue = '<span class="pre">Preprint</span>'
    cites = ""
    if isinstance(p.get("citations"), int):
        cites = '<span>%d citation%s</span>' % (p["citations"], "" if p["citations"] == 1 else "s")
    links = []
    if p.get("arxiv"):
        links.append(pill("arXiv", "https://arxiv.org/abs/" + p["arxiv"]))
    if p.get("doi"):
        links.append(pill("DOI", "https://doi.org/" + p["doi"]))
    iu = p.get("inspire_url") or (("https://inspirehep.net/literature?q=arxiv%3A" + quote(p["arxiv"])) if p.get("arxiv") else "")
    if iu:
        links.append(pill("INSPIRE", iu, "inspire"))
    q = " ".join([clean_title(p.get("title")), " ".join(authors), str(p.get("journal", "")), year, str(p.get("arxiv", ""))]).lower()
    t = T(p.get("title"))
    if p.get("arxiv"):
        t = '<a href="https://arxiv.org/abs/%s" target="_blank" rel="noopener noreferrer">%s</a>' % (esc(p["arxiv"]), t)
    return """<li class="pub" data-year="%s" data-date="%s" data-cites="%d" data-people="%s" data-q="%s">
  <div class="pub-year">%s</div>
  <div class="pub-main">
    <h3 class="pub-title" data-tex>%s</h3>
    <p class="pub-auth">%s</p>
    <p class="pub-meta">%s%s</p>
    <div class="pub-links">%s</div>
  </div>
</li>""" % (esc(year), esc(dkey(p.get("date") or year)), p.get("citations") if isinstance(p.get("citations"), int) else 0,
            esc(" ".join(me_ids)), esc(q), esc(year), t, ah, venue, cites, "".join(links))


# --------------------------------------------------------------------------- pages


def page_index(S):
    g = S.g
    st = S.stats()
    members = S.members
    lead = next((m for m in members if m["id"] == g("lead_member")), members[0] if members else None)
    stat_items = [(st["papers"], "Publications")]
    if st["cites"]:
        stat_items.append((st["cites"], "Citations"))
    else:
        stat_items.append((st["coauthors"], "Co-authors"))
    stat_items.append((len(members), "Team members"))
    if S.alumni:
        stat_items.append((len(S.alumni), "Alumni"))
    stats = "".join('<div><dt data-count="%d">%d</dt><dd>%s</dd></div>' % (n, n, esc(l)) for n, l in stat_items)

    hero = """<section class="hero">
  <div class="wrap hero-grid">
    <div class="hero-copy">
      <p class="eyebrow reveal">%(inst)s &middot; %(city)s</p>
      <h1 class="display reveal" style="--d:.08s">%(headline)s</h1>
      <p class="lede reveal" style="--d:.16s">%(tagline)s</p>
      <div class="cta reveal" style="--d:.24s">
        <a class="btn primary" href="research.html">Explore our research %(arrow)s</a>
        <a class="btn" href="team.html">Meet the team</a>
      </div>
      <dl class="stats reveal" style="--d:.32s">%(stats)s</dl>
    </div>
    <div class="hero-visual reveal" style="--d:.2s">
      <div class="globe-wrap">
        <div class="halo"></div>
        <svg class="rings" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <circle cx="50" cy="50" r="49.5"/>
          <ellipse class="dash" cx="50" cy="50" rx="49.5" ry="17" transform="rotate(-24 50 50)"/>
          <circle class="orb" cx="94" cy="32" r="1.1"/>
        </svg>
        <div class="globe-ph"></div>
        <canvas id="globe" role="img" aria-label="Rotating illustrative map of a cosmic microwave background-like temperature field"></canvas>
        <span class="chip c1">&Delta;T / T &sim; <b>10<sup>-5</sup></b></span>
        <span class="chip c2">Gaussian random field</span>
        <span class="chip c3">Minkowski <b>V<sub>0,1,2</sub></b></span>
      </div>
      <p class="cap">%(caption)s</p>
    </div>
  </div>
  <span class="cue" aria-hidden="true"></span>
</section>""" % dict(inst=esc(g("institute")), city=esc(g("city")), headline=rich(g("hero_headline")), tagline=esc(g("tagline")),
                     arrow=ARROW, stats=stats, caption=esc(g("hero_caption")))

    about = """<section class="sec" id="about"><div class="wrap">
  <div class="about">
    <div class="reveal"><p class="eyebrow">%s</p><h2>%s</h2></div>
    <div class="reveal" style="--d:.1s">
      <div class="prose">%s</div>
      <div class="methods"><h4>Tools we build &amp; use</h4>%s</div>
    </div>
  </div>
</div></section>""" % (esc(g("about_eyebrow", "About")), rich(g("about_title")),
                       "".join("<p>%s</p>" % rich(p) for p in g("about", [])), tags_html(g("method_tags", [])))

    areas_html = ""
    ar = S.d.get("research_areas", [])
    if ar:
        cards = "".join("""<article class="card area reveal" style="--d:%.2fs"><span class="num">%02d</span><div class="ico">%s</div><h3>%s</h3><p>%s</p>%s</article>""" % (
            (i % 3) * .08, i + 1, area_icon(a.get("icon")), esc(a.get("title")), rich(a.get("summary")), tags_html(a.get("tags"))) for i, a in enumerate(ar))
        areas_html = '<section class="sec tight"><div class="wrap">%s<div class="areas">%s</div></div></section>' % (
            sec_head("Research", "What we *study*", "Six threads, one idea: extract robust physical information from complex fields.", ("research.html", "All research")), cards)

    hls = [h for h in S.d.get("highlights", []) if h.get("featured", True)]
    hl_html = ""
    if hls:
        cards = "".join(hl_card(S, h, big=(i == 0), delay=(i % 2) * .08) for i, h in enumerate(hls[:5]))
        hl_html = '<section class="sec"><div class="wrap">%s<div class="hl-grid">%s</div><p style="text-align:center;margin-top:44px" class="reveal"><a class="btn" href="publications.html">All %d publications %s</a></p></div></section>' % (
            sec_head("Highlighted work", "Recent *research*", "A selection of our latest papers.", ("research.html#highlights", "More highlights")), cards, st["papers"], ARROW)

    news = sorted_news(S)[:4]
    awards = sorted_awards(S)[:3]
    news_html = ""
    if news or awards:
        left = ""
        if news:
            left = '<div><p class="col-title"><span>Latest news</span><a href="news.html">View all</a></p><ol class="timeline">%s</ol></div>' % "".join(news_item(n) for n in news)
        right = ""
        if awards:
            right = '<div><p class="col-title"><span>Awards &amp; honours</span><a href="news.html#awards">View all</a></p>%s</div>' % "".join(award_card(a) for a in awards)
        single = " single" if not (left and right) else ""
        news_html = '<section class="sec tight"><div class="wrap">%s<div class="duo%s">%s%s</div></div></section>' % (
            sec_head("Updates", "News & *awards*"), single, left, right)

    crew = ""
    if members:
        shown = ([lead] if lead else []) + [m for m in members if m is not lead]
        av = "".join('<a href="team.html#%s" title="%s" aria-label="%s">%s</a>' % (esc(m["id"]), esc(m["name"]), esc(m["name"]), avatar(m)) for m in shown)
        crew = '<section class="sec tight"><div class="wrap"><div class="card reveal" style="padding:clamp(24px,4vw,44px)">%s<div class="crew" style="margin-bottom:26px">%s</div><a class="btn" href="team.html">Meet the whole team %s</a></div></div></section>' % (
            sec_head("People", "A small group with *big* questions"), av, ARROW)

    cta = """<section class="sec tight"><div class="wrap"><div class="cta-band reveal">
  <p class="eyebrow">Get in touch</p><h2>%s</h2><p>%s</p>
  <a class="btn primary" href="contact.html">Contact us %s</a>
</div></div></section>""" % (rich(g("join_title")), rich(g("join_text")), ARROW)

    return shell(S, "index.html", g("group_name"), hero + about + areas_html + hl_html + news_html + crew + cta,
                 desc=" ".join(g("about", [""])[:1])[:300] or g("tagline"), math=True, home=True)


def page_team(S):
    body = [phead(S, "Team", "The *people*", "Researchers at the %s." % S.g("institute"))]
    secs = []
    for role, label, _ in ROLE_ORDER:
        ms = [m for m in S.members if m.get("role") == role]
        if not ms:
            continue
        if role == "pi":
            cards = "".join(person_card(m, lead=True) for m in ms)
            secs.append('<section class="team-sec"><h2>%s</h2><div class="grid">%s</div></section>' % (esc(label if len(ms) > 1 else label), cards))
        else:
            cards = "".join(person_card(m, delay=(i % 2) * .07) for i, m in enumerate(ms))
            secs.append('<section class="team-sec"><h2>%s <small>%02d</small></h2><div class="people-grid">%s</div></section>' % (esc(label), len(ms), cards))
    body.append('<div class="sec tight"><div class="wrap">%s<p class="muted reveal" style="margin-top:20px">Looking for people who have moved on? See <a href="former.html">former members</a>.</p></div></div>' % "".join(secs))
    return shell(S, "team.html", "Team", "\n".join(body), desc="The researchers of the %s." % S.g("group_name"))


def page_former(S):
    body = [phead(S, "Former members", "Where they *went next*", "Students and postdocs who trained in the group.")]
    secs = []
    for cat, label in ALUM_ORDER:
        al = sorted([a for a in S.alumni if a.get("category", "other") == cat], key=lambda a: str(a.get("year", "")), reverse=True)
        if al:
            secs.append('<section class="team-sec"><h2>%s <small>%02d</small></h2><div class="people-grid">%s</div></section>' % (
                esc(label), len(al), "".join(alum_card(a, (i % 2) * .07) for i, a in enumerate(al))))
    if not secs:
        secs.append('<p class="empty">No former members listed yet.</p>')
    body.append('<div class="sec tight"><div class="wrap">%s</div></div>' % "".join(secs))
    return shell(S, "former.html", "Former Members", "\n".join(body))


def page_research(S):
    g = S.g
    body = [phead(S, "Research", "Our *research*", "Cosmology, statistical physics and data-driven methods: from the first light of the Universe to the cosmic web.")]
    ar = S.d.get("research_areas", [])
    if ar:
        cards = "".join("""<article class="card area reveal" style="--d:%.2fs"><span class="num">%02d</span><div class="ico">%s</div><h3>%s</h3><p>%s</p>%s</article>""" % (
            (i % 3) * .08, i + 1, area_icon(a.get("icon")), esc(a.get("title")), rich(a.get("summary")), tags_html(a.get("tags"))) for i, a in enumerate(ar))
        body.append('<section class="sec tight"><div class="wrap">%s<div class="areas">%s</div></div></section>' % (sec_head("Themes", "Research *areas*"), cards))
    hls = S.d.get("highlights", [])
    if hls:
        cards = "".join(hl_card(S, h, big=(i == 0), delay=(i % 2) * .08) for i, h in enumerate(hls))
        body.append('<section class="sec tight" id="highlights"><div class="wrap">%s<div class="hl-grid">%s</div></div></section>' % (sec_head("Highlights", "Highlighted *work*"), cards))
    latest = S.papers[:6]
    if latest:
        items = "".join(pub_item(S, p) for p in latest)
        body.append('<section class="sec tight"><div class="wrap">%s<ul>%s</ul></div></section>' % (
            sec_head("Publications", "Latest *papers*", "", ("publications.html", "All %d publications" % len(S.papers))), items))
    res = g and S.d.get("resources", {})
    blocks = []
    for key, title in (("books", "Free books"), ("online", "Online resources")):
        its = res.get(key, []) if res else []
        if its:
            li = "".join('<li><a href="%s" target="_blank" rel="noopener noreferrer"><span>%s</span><small>%s</small></a></li>' % (esc(safe_url(i.get("url"))), esc(i.get("title")), esc(i.get("note", ""))) for i in its)
            blocks.append('<div class="card res reveal"><h3>%s</h3><ul>%s</ul></div>' % (title, li))
    if blocks:
        body.append('<section class="sec tight"><div class="wrap">%s<div class="grid c2">%s</div></div></section>' % (sec_head("Learn", "Useful *materials*", "Handy references for cosmology and physics."), "".join(blocks)))
    lec = S.d.get("lectures", [])
    if lec:
        cards = []
        for i, l in enumerate(lec):
            url = safe_url(l.get("url"))
            m = re.search(r"(?:v=|youtu\.be/)([\w-]{6,})", url or "")
            th = ('<img src="https://img.youtube.com/vi/%s/hqdefault.jpg" alt="" loading="lazy" onerror="this.remove()">' % m.group(1)) if m else ""
            cards.append('<a class="card lec reveal" style="--d:%.2fs" href="%s" target="_blank" rel="noopener noreferrer"><span class="th">%s</span><span class="lb-t" style="display:block"><h3>%s</h3><p>%s</p></span></a>' % (
                (i % 3) * .08, esc(url), th, esc(l.get("title")), esc(l.get("note", ""))))
        body.append('<section class="sec tight"><div class="wrap">%s<div class="grid c3">%s</div></div></section>' % (sec_head("Watch", "Video *lectures*"), "".join(cards)))
    return shell(S, "research.html", "Research", "\n".join(body), math=True)


def page_publications(S):
    g = S.g
    st = S.stats()
    meta = S.pub_meta
    body = [phead(S, "Publications", "All *publications*", "Papers by the group, pulled from INSPIRE-HEP.")]
    years = Counter(str(p.get("year") or str(p.get("date", ""))[:4]) for p in S.papers)
    years.pop("", None)
    stat_cards = [(st["papers"], "Papers")]
    if st["cites"] is not None:
        stat_cards += [(st["cites"], "Citations"), (st["h"], "h-index")]
    stat_cards.append((st["coauthors"], "Co-authors"))
    stats_html = '<div class="pubstats">%s</div>' % "".join(
        '<div class="card reveal"><div class="n" data-count="%d">%d</div><div class="l">%s</div></div>' % (n, n, l) for n, l in stat_cards)
    bars = ""
    if len(years) >= 3:
        ys = sorted(int(y) for y in years if y.isdigit())
        full = range(ys[0], ys[-1] + 1)
        mx = max(years.values())
        def bar(y):
            n = years.get(str(y), 0)
            lbl = " lbl" if (y % 5 == 0 or y in (ys[0], ys[-1])) else ""
            return '<button type="button" class="bar%s" data-year="%d" title="%d: %d paper%s" aria-label="%d: %d papers" style="--h:%d%%"><i></i><span>%d</span></button>' % (
                lbl, y, y, n, "" if n == 1 else "s", y, n, (max(3, round(100 * n / mx)) if n else 1), y)
        bars = '<div class="bars reveal" role="group" aria-label="Papers per year (click a bar to filter)">%s</div>' % "".join(bar(y) for y in full)
    chips = ['<button type="button" class="chipbtn on" data-person="">Everyone</button>']
    pc = Counter()
    for p in S.papers:
        for pid in S.paper_people(p):
            pc[pid] += 1
    order = [m["id"] for m in S.members + S.alumni]
    names = {m["id"]: m["name"] for m in S.members + S.alumni}
    lead = g("lead_member")
    for pid in sorted(pc, key=lambda i: (i != lead, order.index(i))):
        if pid == lead:
            continue
        chips.append('<button type="button" class="chipbtn" data-person="%s">%s <small class="muted">%d</small></button>' % (esc(pid), esc(names[pid]), pc[pid]))
    chip_html = '<div class="chips" aria-label="Filter by group member">%s</div>' % "".join(chips) if len(chips) > 1 else ""
    year_opts = "".join('<option value="%s">%s</option>' % (y, y) for y in sorted(years, reverse=True))
    controls = """<div class="controls reveal">
  <input class="field" id="pub-q" type="search" placeholder="Search title, author, journal, arXiv id..." aria-label="Search publications">
  <select class="field" id="pub-year" aria-label="Filter by year"><option value="">All years</option>%s</select>
  <select class="field" id="pub-sort" aria-label="Sort"><option value="new">Newest first</option><option value="old">Oldest first</option>%s</select>
</div>""" % (year_opts, '<option value="cites">Most cited</option>' if st["cites"] is not None else "")
    note = ""
    if not meta.get("fetched_at"):
        note = '<p class="notice">This list was imported from the previous website. Run <code>python manage.py</code> and choose <b>Refresh publications</b> to pull citation counts and the latest papers from INSPIRE.</p>'
    updated = ""
    if meta.get("fetched_at"):
        updated = '<p class="muted mono" style="font-size:12px">Synced with INSPIRE-HEP on %s</p>' % esc(fmt_date(meta["fetched_at"][:10]))
    items = "".join(pub_item(S, p) for p in S.papers)
    body.append('<div class="sec tight"><div class="wrap">%s%s%s%s%s%s<p class="count" id="pub-count"></p><ul id="pub-list">%s</ul><p class="empty" id="pub-empty" hidden>No papers match your search.</p>%s</div></div>' % (
        note, stats_html, bars, controls, chip_html, "", items, updated))
    return shell(S, "publications.html", "Publications", "\n".join(body), math=True, desc="Publications of the %s." % g("group_name"))


def page_news(S):
    news = sorted_news(S)
    awards = sorted_awards(S)
    body = [phead(S, "News", "News & *awards*", "What the group has been up to.")]
    inner = []
    if news:
        kinds = []
        for n in news:
            k = n.get("kind", "News")
            if k not in kinds:
                kinds.append(k)
        filt = ""
        if len(kinds) > 1:
            filt = '<div class="filters reveal"><button type="button" class="chipbtn on" data-kind="">All</button>%s</div>' % "".join(
                '<button type="button" class="chipbtn" data-kind="%s">%s</button>' % (esc(k), esc(k)) for k in kinds)
        inner.append('<section>%s<ol class="timeline">%s</ol></section>' % (filt, "".join(news_item(n) for n in news)))
    else:
        inner.append('<p class="empty">No news yet.</p>')
    if awards:
        inner.append('<section id="awards" style="margin-top:clamp(60px,8vw,110px)">%s<div class="grid c2">%s</div></section>' % (
            sec_head("Recognition", "Awards & *honours*"), "".join(award_card(a) for a in awards)))
    body.append('<div class="sec tight"><div class="wrap">%s</div></div>' % "".join(inner))
    return shell(S, "news.html", "News", "\n".join(body))


def page_gallery(S):
    albums = S.d.get("albums", [])
    body = [phead(S, "Gallery", "Moments from the *group*", "Talks, conferences, outreach and group life.")]
    blocks = []
    for a in albums:
        photos = a.get("photos", [])
        figs = []
        for ph in photos:
            cap = ph.get("caption", "")
            figs.append('<figure class="reveal"><button type="button" class="shot" data-src="%s" data-cap="%s"><span class="ph">%s</span><img src="%s" alt="%s" loading="lazy" onerror="this.remove();"></button>%s</figure>' % (
                esc(ph.get("image")), esc(cap or a.get("title", "")), esc(Path(ph.get("image", "")).name), esc(ph.get("image")), esc(cap or a.get("title", "")),
                ('<figcaption>%s</figcaption>' % esc(cap)) if cap else ""))
        blocks.append("""<section class="album" id="%s">
  <div class="album-h reveal"><div>%s<h2>%s</h2>%s</div></div>
  <div class="masonry">%s</div>
</section>""" % (esc(a.get("id")), ('<p class="d">%s</p>' % esc(fmt_date(a.get("date")))) if a.get("date") else "", rich(a.get("title")),
                 ('<p>%s</p>' % rich(a["description"])) if a.get("description") else "", "".join(figs)))
    if not blocks:
        blocks.append('<p class="empty">No photos yet.</p>')
    body.append('<div class="sec tight"><div class="wrap">%s</div></div>' % "".join(blocks))
    return shell(S, "gallery.html", "Gallery", "\n".join(body))


def page_collab(S):
    body = [phead(S, "Collaborations", "Working *together*", "Science is a team sport. These are the institutions and people we work with.")]
    inner = []
    cl = S.d.get("collaborations", [])
    if cl:
        cards = []
        for i, c in enumerate(cl):
            url = safe_url(c.get("url"))
            name = esc(c.get("name"))
            name = '<a href="%s" target="_blank" rel="noopener noreferrer">%s</a>' % (esc(url), name) if url else name
            cards.append('<article class="card inst reveal" style="--d:%.2fs"><span class="loc">%s</span><h3>%s</h3>%s</article>' % (
                (i % 3) * .07, esc(c.get("location", "")), name, ('<p>%s</p>' % rich(c["note"])) if c.get("note") else ""))
        inner.append('<section>%s<div class="grid auto">%s</div></section>' % (sec_head("Institutions", "Our *partners*"), "".join(cards)))
    # frequent co-authors, computed from the publication list
    cnt, names = Counter(), defaultdict(Counter)
    for p in S.papers:
        seen = set()
        for a in p.get("authors", []):
            sg = sig(a)
            if not sg or sg in seen or sg in S.people:
                continue
            seen.add(sg)
            cnt[sg] += 1
            names[sg][a] += 1
    top = [(sg, n) for sg, n in cnt.most_common(40) if n >= 2]
    if top:
        mx = top[0][1]
        chips = "".join('<span class="co" style="--s:%d">%s <small>%d</small></span>' % (round(4 * n / mx), esc(names[sg].most_common(1)[0][0]), n) for sg, n in top)
        inner.append('<section style="margin-top:clamp(50px,7vw,90px)">%s<div class="cloud reveal">%s</div></section>' % (
            sec_head("Co-authors", "Frequent *collaborators*", "Computed automatically from our publication list. The number is shared papers."), chips))
    if not inner:
        inner.append('<p class="empty">Collaborations will appear here.</p>')
    body.append('<div class="sec tight"><div class="wrap">%s</div></div>' % "".join(inner))
    return shell(S, "collab.html", "Collaborations", "\n".join(body))


def page_calendar(S):
    g = S.g
    url = safe_url(g("calendar_embed"))
    body = [phead(S, "Calendar", "What is *happening*", g("calendar_note"))]
    if url:
        body.append('<div class="sec tight"><div class="wrap"><div class="calendar reveal"><iframe src="%s" title="Group calendar" loading="lazy"></iframe></div><p class="muted" style="margin-top:16px;font-size:14px">Times are shown in India Standard Time.</p></div></div>' % esc(url))
    else:
        body.append('<div class="sec tight"><div class="wrap"><p class="empty">Calendar coming soon.</p></div></div>')
    return shell(S, "calendar.html", "Calendar", "\n".join(body))


def page_contact(S):
    g = S.g
    body = [phead(S, "Contact", "Get in *touch*", "Questions about our research, prospective students, collaborations, visits.")]
    emails = []
    for e in [g("email"), g("group_email")]:
        if e and e not in emails:
            emails.append(e)
    c1 = '<div class="card reveal"><span class="k">Email</span><h3>Write to us</h3>%s</div>' % "".join('<p><a href="mailto:%s">%s</a></p>' % (esc(e), esc(e)) for e in emails)
    mp = pill("Open in Maps", g("map_url"), "inspire") if g("map_url") else ""
    c2 = '<div class="card reveal" style="--d:.08s"><span class="k">Visit</span><h3>%s</h3><p>%s</p><p style="margin-top:14px">%s</p></div>' % (esc(g("institute")), esc(g("address") or g("city")), mp)
    soc = "".join('<p>%s</p>' % pill(x.get("label"), x.get("url")) for x in g("social", []) if safe_url(x.get("url")))
    c3 = '<div class="card reveal" style="--d:.16s"><span class="k">Elsewhere</span><h3>Find us online</h3>%s<p>%s</p></div>' % (soc, pill("Group calendar", "calendar.html"))
    body.append('<div class="sec tight"><div class="wrap"><div class="contact-grid">%s%s%s</div></div></div>' % (c1, c2, c3))
    return shell(S, "contact.html", "Contact", "\n".join(body))


def page_404(S):
    body = ('<section class="sec"><div class="wrap" style="text-align:center;padding:60px 0"><p class="eyebrow" style="justify-content:center">Error 404</p>'
            '<h1 class="display" style="font-size:clamp(48px,9vw,120px);margin-bottom:20px">Lost in <em>space</em></h1>'
            '<p class="lede" style="margin:0 auto 34px">This page drifted beyond the observable Universe.</p>'
            '<a class="btn primary" href="index.html">Back to Earth %s</a></div></section>' % ARROW)
    return shell(S, "404.html", "Page not found", body)


PAGES = [("index.html", page_index), ("team.html", page_team), ("research.html", page_research),
         ("publications.html", page_publications), ("news.html", page_news), ("gallery.html", page_gallery),
         ("former.html", page_former), ("collab.html", page_collab), ("calendar.html", page_calendar),
         ("contact.html", page_contact), ("404.html", page_404)]


def build(verbose=True):
    S = Site()
    if not S.s:
        sys.exit("data/site.json is missing or empty.")
    for fname, fn in PAGES:
        (ROOT / fname).write_text(fn(S), encoding="utf-8")
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")
    (ROOT / "images" / "site").mkdir(parents=True, exist_ok=True)
    (ROOT / "images" / "site" / "favicon.svg").write_text(FAVICON, encoding="utf-8")
    if verbose:
        print("Built %d pages  |  %d team members, %d alumni, %d papers" % (len(PAGES), len(S.members), len(S.alumni), len(S.papers)))
    return S


if __name__ == "__main__":
    build()
