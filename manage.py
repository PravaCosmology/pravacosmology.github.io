#!/usr/bin/env python3
"""
manage.py - the editor for your group website.   Run:   python manage.py

Instead of editing HTML you answer questions; the script updates data/site.json and
rebuilds every page.  Then just push to GitHub.

    python manage.py            interactive menu
    python manage.py build      rebuild the pages only
    python manage.py pubs       refresh publications from INSPIRE, then rebuild
    python manage.py serve      preview the site at http://localhost:8000
    python manage.py check      list images the site expects but cannot find yet

Standard library only (Python 3.8+).
"""
import datetime
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SITE = DATA / "site.json"
IMG = ROOT / "images"
sys.path.insert(0, str(ROOT))
import sitegen  # noqa: E402
import update_publications as upub  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


class Quit(Exception):
    pass


# --------------------------------------------------------------------------- small UI helpers

def ask(prompt, default=None):
    """Plain question. Enter keeps the default. Ctrl-D quits, Ctrl-C cancels the current action."""
    suffix = " [%s]" % default if default not in (None, "") else ""
    try:
        v = input("%s%s: " % (prompt, suffix)).strip()
    except EOFError:
        raise Quit()
    return v if v else (default if default is not None else "")


def yes(prompt, default=True):
    d = "Y/n" if default else "y/N"
    v = ask("%s (%s)" % (prompt, d)).lower()
    return default if not v else v.startswith("y")


def menu(title, options, back="Back"):
    """options: list of (key, label). Returns the chosen key or None for back."""
    print("\n== %s ==" % title)
    for k, label in options:
        print("  %s) %s" % (k, label))
    print("  0) %s" % back)
    while True:
        c = ask("Choose").lower()
        if c in ("0", "q", ""):
            return None
        for k, _ in options:
            if str(k).lower() == c:
                return k
        print("  Please pick one of the listed options.")


def choose(prompt, choices, default=None):
    """choices: list of (value, label)."""
    print(prompt)
    for i, (_, label) in enumerate(choices, 1):
        mark = "  (current)" if choices[i - 1][0] == default else ""
        print("  %d) %s%s" % (i, label, mark))
    while True:
        v = ask("Number", "" if default is None else str(next((i for i, c in enumerate(choices, 1) if c[0] == default), "")))
        if v.isdigit() and 1 <= int(v) <= len(choices):
            return choices[int(v) - 1][0]
        if not v and default is not None:
            return default
        print("  Enter a number from the list.")


def norm_url(u):
    u = u.strip()
    if not u or u == "-":
        return ""
    if re.match(r"^(https?://|mailto:)", u, re.I):
        return u
    if "@" in u and " " not in u and "/" not in u:
        return "mailto:" + u
    return "https://" + u


def slug(s):
    return sitegen.slugify(s)


def unique_id(base, items):
    ids = {i.get("id") for i in items}
    s, n = base, 2
    while s in ids:
        s = "%s-%d" % (base, n)
        n += 1
    return s


# --------------------------------------------------------------------------- data load / save

def load():
    return json.loads(SITE.read_text(encoding="utf-8"))


def save(d):
    bdir = DATA / "backup"
    bdir.mkdir(exist_ok=True)
    if SITE.exists():
        shutil.copy2(SITE, bdir / ("site-%s.json" % datetime.datetime.now().strftime("%Y%m%d-%H%M%S")))
        old = sorted(bdir.glob("site-*.json"))
        for f in old[:-25]:
            f.unlink()
    SITE.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")


def commit(d, msg="Saved."):
    save(d)
    sitegen.build(verbose=False)
    print("  OK  %s  (site rebuilt - open index.html to look, then push to GitHub)" % msg)


# --------------------------------------------------------------------------- field editors

def edit_text(prompt, current=""):
    """Multi-line text. Blank line ends. Enter on the first line keeps the current text."""
    print("%s" % prompt)
    if current:
        print("  Current: %s" % (current if len(current) < 220 else current[:220] + "..."))
        print("  (press Enter to keep it, '-' to clear, or type new text; finish with an empty line)")
    else:
        print("  (type the text; finish with an empty line. Optional formatting: **bold**, *italic*, [label](https://url))")
    lines = []
    while True:
        l = ask("  >")
        if not lines and l == "" and current:
            return current
        if not lines and l == "-":
            return ""
        if l == "":
            break
        lines.append(l)
    return " ".join(lines)


def edit_list(prompt, current):
    cur = ", ".join(current or [])
    v = ask(prompt + " (comma separated; '-' clears)", cur)
    if v == "-":
        return []
    return [x.strip() for x in v.split(",") if x.strip()]


LINK_PRESETS = ["Website", "Google Scholar", "ORCID", "ADS", "arXiv author page", "GitHub", "LinkedIn", "X / Twitter",
                "CV", "Thesis", "Mastodon", "YouTube", "Other (type your own label)"]


def edit_links(current):
    links = list(current or [])
    while True:
        print("  Links now: %s" % (", ".join(l["label"] for l in links) or "none"))
        c = ask("  [a]dd link, [r]emove link, [c]lear all, Enter = done").lower()
        if c == "a":
            for i, p in enumerate(LINK_PRESETS, 1):
                print("    %2d) %s" % (i, p))
            n = ask("    Number")
            if not (n.isdigit() and 1 <= int(n) <= len(LINK_PRESETS)):
                continue
            label = LINK_PRESETS[int(n) - 1]
            if label.startswith("Other"):
                label = ask("    Label")
            url = norm_url(ask("    URL"))
            if label and url:
                links.append({"label": label, "url": url})
        elif c == "r" and links:
            for i, l in enumerate(links, 1):
                print("    %d) %s - %s" % (i, l["label"], l["url"]))
            n = ask("    Number to remove")
            if n.isdigit() and 1 <= int(n) <= len(links):
                links.pop(int(n) - 1)
        elif c == "c":
            links = []
        elif c == "":
            return links


def edit_inspire(current):
    print("  INSPIRE author id or profile URL, e.g. 1046872 or https://inspirehep.net/authors/1046872")
    print("  (find yours at inspirehep.net -> Authors; leave blank if none, '-' clears)")
    v = ask("  INSPIRE", current)
    if v == "-":
        return ""
    rid = upub.parse_recid(v)
    if v and not rid:
        print("  That does not look like an INSPIRE author id/URL - kept as typed (it will be used as a search).")
        return v
    return rid


IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".svg")


def clean_path(p):
    p = p.strip().strip('"').strip("'")
    return os.path.expanduser(p)


def edit_image(prompt, folder, base, current=""):
    """Accepts a file name already inside images/<folder>/, or a path to a file on your computer (it gets copied)."""
    print("  %s" % prompt)
    print("  Give a file NAME already in images/%s/, or the full PATH of a picture on your computer (I copy it there)." % folder)
    v = ask("  Image", current)
    if v == "-":
        return ""
    if not v or v == current:
        return current
    v = clean_path(v)
    src = Path(v)
    if src.is_file():
        dest_dir = IMG / folder
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / ("%s%s" % (base, src.suffix.lower()))
        if dest.exists() and dest.resolve() != src.resolve() and not yes("  %s already exists - overwrite?" % dest.name, False):
            dest = dest_dir / src.name
        if dest.resolve() != src.resolve():
            shutil.copy2(src, dest)
        print("  copied to images/%s/%s" % (folder, dest.name))
        return "images/%s/%s" % (folder, dest.name)
    rel = v.replace("\\", "/")
    if rel.startswith("images/"):
        path = rel
    else:
        path = "images/%s/%s" % (folder, rel)
    if not (ROOT / path).exists():
        print("  note: %s is not there yet - copy the picture in, the page will pick it up (initials are shown meanwhile)." % path)
    return path


# --------------------------------------------------------------------------- generic field spec

class F:
    def __init__(self, key, prompt, kind="str", required=False, default=None, choices=None, folder=None, hint=None):
        self.key, self.prompt, self.kind, self.required = key, prompt, kind, required
        self.default, self.choices, self.folder, self.hint = default, choices, folder, hint


def edit_item(spec, item, all_items, id_from, folder_base=None):
    """Walk through the fields. item may be {} (new) or an existing dict (edit: Enter keeps)."""
    new = not item
    out = dict(item)
    print("\n(Press Enter to %s each answer; '-' clears an optional field.)" % ("accept the default for" if new else "keep"))
    for f in spec:
        cur = out.get(f.key, f.default if new else "")
        if cur is None:
            cur = ""
        if f.key == "title" and not cur and out.get("role"):
            cur = ROLE_TITLES.get(out["role"], "")
        if f.hint:
            print("  " + f.hint)
        if f.kind == "str":
            while True:
                v = ask(f.prompt + (" *" if f.required else ""), cur)
                if v == "-" and not f.required:
                    v = ""
                if f.required and not v:
                    print("  This one is required.")
                    continue
                break
            if f.key == "email" and v and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
                print("  (that does not look like an email address, kept anyway)")
            if f.key in ("url", "link", "calendar_embed", "map_url") and v:
                v = norm_url(v)
            out[f.key] = v
        elif f.kind == "text":
            out[f.key] = edit_text(f.prompt, cur or "")
        elif f.kind == "list":
            out[f.key] = edit_list(f.prompt, cur)
        elif f.kind == "choice":
            out[f.key] = choose(f.prompt, f.choices, cur if cur else (f.default or f.choices[0][0]))
        elif f.kind == "bool":
            out[f.key] = yes(f.prompt, bool(cur) if cur != "" else True)
        elif f.kind == "date":
            while True:
                v = ask(f.prompt + " (YYYY-MM-DD, or YYYY-MM)", cur or datetime.date.today().isoformat())
                if v == "-" and not f.required:
                    v = ""
                if not v or re.match(r"^\d{4}(-\d{2}(-\d{2})?)?$", v):
                    break
                print("  Use the format 2026-03-22 or 2026-03.")
            out[f.key] = v
        elif f.kind == "links":
            out[f.key] = edit_links(cur)
        elif f.kind == "inspire":
            out[f.key] = edit_inspire(cur)
        elif f.kind == "image":
            base = slug(out.get(id_from) or "image")
            out[f.key] = edit_image(f.prompt, f.folder, folder_base(out) if folder_base else base, cur)
    if new:
        out["id"] = unique_id(slug(out.get(id_from) or "item"), all_items)
    return out


def describe(item, keys):
    return " - ".join(str(item.get(k, "")) for k in keys if item.get(k))


def crud(title, getlist, spec, id_from, label_keys, extra=None, noun="item", folder_base=None, new_first=False):
    """List / add / edit / delete / reorder for any list inside the data."""
    d = load()
    while True:
        items = getlist(d)
        print("\n== %s (%d) ==" % (title, len(items)))
        for i, it in enumerate(items, 1):
            print("  %2d. %s" % (i, describe(it, label_keys)))
        opts = [("a", "Add a %s" % noun), ("e", "Edit a %s" % noun), ("d", "Delete a %s" % noun), ("m", "Move up / down")]
        if extra:
            opts += [(k, lab) for k, lab, _ in extra]
        c = menu(title, opts)
        if c is None:
            return
        try:
            if c == "a":
                it = edit_item(spec, {}, items, id_from, folder_base)
                if new_first:
                    items.insert(0, it)
                else:
                    items.append(it)
                commit(d, "Added %s." % it.get(id_from, noun))
            elif c in ("e", "d", "m") or (extra and any(c == k for k, _, _ in extra)):
                if not items:
                    print("  Nothing here yet.")
                    continue
                n = ask("Which number")
                if not (n.isdigit() and 1 <= int(n) <= len(items)):
                    print("  Not a valid number.")
                    continue
                idx = int(n) - 1
                if c == "e":
                    items[idx] = edit_item(spec, items[idx], items, id_from, folder_base)
                    commit(d, "Updated.")
                elif c == "d":
                    if yes("Really delete '%s'?" % describe(items[idx], label_keys), False):
                        items.pop(idx)
                        commit(d, "Deleted.")
                elif c == "m":
                    t = ask("New position (1-%d)" % len(items))
                    if t.isdigit() and 1 <= int(t) <= len(items):
                        items.insert(int(t) - 1, items.pop(idx))
                        commit(d, "Moved.")
                else:
                    for k, _, fn in extra:
                        if k == c:
                            fn(d, items, idx)
        except KeyboardInterrupt:
            print("\n  Cancelled - nothing was changed.")
            d = load()


# --------------------------------------------------------------------------- specs

ROLES = [("pi", "Principal Investigator"), ("postdoc", "Postdoctoral Researcher"), ("phd", "Doctoral (PhD) Student"),
         ("masters", "Masters / Project Student"), ("visitor", "Visitor / Intern")]
ALUM_CATS = [("phd", "PhD alumnus/alumna"), ("postdoc", "Postdoctoral alumnus/alumna"), ("masters", "Masters / project student"), ("other", "Other")]
ROLE_TITLES = {"pi": "Professor", "postdoc": "Postdoctoral Researcher", "phd": "Doctoral Student", "masters": "Masters Student", "visitor": "Visitor"}

MEMBER = [
    F("name", "Full name", required=True),
    F("role", "Role", "choice", choices=ROLES, default="phd"),
    F("title", "Title shown on the card (e.g. Professor, Postdoctoral Researcher)"),
    F("photo", "Photo", "image", folder="team"),
    F("email", "Email"),
    F("research", "Research interests (one line)"),
    F("degree", "PhD / degree info for the card, e.g. 'CUSAT, Dept. of Physics (2025)' (optional)"),
    F("tags", "Keyword badges", "list"),
    F("bio", "Short bio (optional)", "text"),
    F("inspire", "INSPIRE profile", "inspire"),
    F("links", "Extra links (website, Google Scholar, ORCID, ADS, GitHub ...)", "links"),
    F("pub_names", "Other spellings of the name in paper author lists, e.g. 'K. Virkar' (optional)", "list"),
]
ALUMNI = [
    F("name", "Full name", required=True),
    F("category", "Category", "choice", choices=ALUM_CATS, default="phd"),
    F("photo", "Photo", "image", folder="past_members"),
    F("thesis", "Thesis title (optional)"),
    F("year", "Year, or years (e.g. 2024 or 2021 - 2023)"),
    F("now_at", "Now at (position, institution)"),
    F("research", "Research area (used when there is no thesis title)"),
    F("tags", "Keyword badges", "list"),
    F("inspire", "INSPIRE profile", "inspire"),
    F("links", "Extra links (thesis, website, Google Scholar ...)", "links"),
    F("pub_names", "Other spellings of the name in author lists (optional)", "list"),
]
NEWS_KINDS = ["News", "Event", "Preprint", "Publication", "Talk", "Visit", "Award", "Announcement", "Outreach"]
NEWS = [
    F("date", "Date", "date", required=True),
    F("kind", "Type (News, Event, Preprint, Publication, Talk, Visit, Award, Announcement, Outreach or your own)", default="News"),
    F("title", "Headline", required=True),
    F("text", "Details (a sentence or two)", "text"),
    F("link", "Link (optional)"),
    F("link_label", "Link button text (optional, default 'Read more')"),
]
AWARD = [
    F("title", "Award / honour", required=True),
    F("who", "Recipient"),
    F("date", "Date", "date"),
    F("text", "Details (optional)", "text"),
    F("link", "Link (optional)"),
]
HIGHLIGHT = [
    F("arxiv", "arXiv id (e.g. 2604.08409) - the details can be fetched automatically"),
    F("title", "Title", required=True),
    F("authors", "Authors (blank = taken from the publication list if it is there)"),
    F("summary", "Summary / abstract", "text"),
    F("image", "Figure for the card", "image", folder="research"),
    F("date", "Date", "date"),
    F("journal", "Journal reference (optional; shown instead of 'arXiv:...')"),
    F("featured", "Show on the home page?", "bool"),
    F("links", "Extra links (code, talk, press ...)", "links"),
]
AREA = [
    F("title", "Research area name", required=True),
    F("icon", "Icon", "choice", choices=[("cmb", "CMB sphere"), ("lss", "Cosmic web"), ("21cm", "Signal wave"), ("dipole", "Dipole arrow"),
                                          ("entropy", "Bars / entropy"), ("theory", "Curve / theory"), ("star", "Star")], default="star"),
    F("summary", "Two-sentence summary", "text"),
    F("tags", "Keyword badges", "list"),
]
COLLAB = [
    F("name", "Institution / collaboration", required=True),
    F("location", "City, country"),
    F("url", "Website"),
    F("note", "Short note (who you work with, on what)", "text"),
]
RES = [F("title", "Title", required=True), F("url", "URL", required=True), F("note", "Short note (optional)")]
LECTURE = [F("title", "Lecture title", required=True), F("note", "Speaker / event", default=""), F("url", "YouTube (or other) URL", required=True)]


# --------------------------------------------------------------------------- feature menus

def do_members():
    def to_alumni(d, items, idx):
        m = items[idx]
        print("Moving %s to Former Members." % m["name"])
        cat = choose("Category", ALUM_CATS, {"postdoc": "postdoc", "phd": "phd", "masters": "masters"}.get(m.get("role"), "other"))
        a = {"id": unique_id(m["id"], d["alumni"]), "name": m["name"], "category": cat, "photo": m.get("photo", ""),
             "thesis": ask("Thesis title (optional)"), "year": ask("Year or years (e.g. 2026, or 2021 - 2024)"),
             "now_at": ask("Now at"), "research": m.get("research", ""), "tags": m.get("tags", []),
             "inspire": m.get("inspire", ""), "links": m.get("links", []), "pub_names": m.get("pub_names", []), "bio": m.get("bio", "")}
        d["alumni"].insert(0, a)
        items.pop(idx)
        commit(d, "%s moved to Former Members. (Optionally move their photo into images/past_members/ and edit the photo there.)" % m["name"])

    def fill_title(d, items, idx):
        pass

    # wrap edit to auto-fill title from role
    spec = MEMBER
    crud("Team members", lambda d: d["members"], spec, "name", ["name", "title"],
         extra=[("t", "Move someone to Former Members", to_alumni)], noun="team member",
         folder_base=lambda it: slug(it.get("name") or "photo"))
    # ensure titles exist
    d = load()
    changed = False
    for m in d["members"]:
        if not m.get("title"):
            m["title"] = ROLE_TITLES.get(m.get("role"), "")
            changed = True
    if changed:
        commit(d, "Filled in missing titles.")


def do_alumni():
    crud("Former members", lambda d: d["alumni"], ALUMNI, "name", ["name", "year", "now_at"], noun="former member",
         folder_base=lambda it: slug(it.get("name") or "photo"))


def fetch_highlight_details(d, h):
    ax = h.get("arxiv")
    if not ax:
        return
    print("  Looking up %s on INSPIRE ..." % ax)
    try:
        p = upub.fetch_by_arxiv(ax)
    except Exception as e:
        print("  (could not reach INSPIRE: %s) - fill the fields by hand." % e)
        return
    if not p:
        print("  (not found on INSPIRE yet) - fill the fields by hand.")
        return
    if not h.get("title"):
        h["title"] = p["title"]
    if not h.get("summary"):
        h["summary"] = p.get("abstract", "")
    if not h.get("authors"):
        h["authors"] = ", ".join(p["authors"][:8]) + (" et al." if p["author_count"] > 8 else "")
    if not h.get("date"):
        h["date"] = p.get("date", "")[:10]
    print("  Found: %s" % p["title"])


def do_highlights():
    d = load()
    while True:
        items = d["highlights"]
        print("\n== Research highlights (%d) ==" % len(items))
        for i, h in enumerate(items, 1):
            print("  %2d. %s%s" % (i, (h.get("title") or "")[:90], "" if h.get("featured", True) else "   [not on home page]"))
        c = menu("Research highlights", [("a", "Add a highlight (auto-fills from INSPIRE if you give the arXiv id)"), ("e", "Edit one"),
                                          ("d", "Delete one"), ("m", "Move up / down")])
        if c is None:
            return
        try:
            if c == "a":
                ax = ask("arXiv id (e.g. 2604.08409, blank to type everything by hand)")
                h = {"arxiv": re.sub(r"^(arxiv:|https?://arxiv\.org/abs/)", "", ax, flags=re.I)} if ax else {}
                if ax:
                    fetch_highlight_details(d, h)
                    h["image"] = "images/research/%s.png" % ax.replace(".", "_").replace("/", "_")
                spec = [f for f in HIGHLIGHT if f.key != "arxiv"]
                h = edit_item(spec, h, items, "title", folder_base=lambda it: (it.get("arxiv") or slug(it.get("title"))).replace(".", "_").replace("/", "_"))
                h["arxiv"] = h.get("arxiv", "") or ""
                h["id"] = unique_id(slug(h.get("arxiv") or h.get("title")), items)
                items.insert(0, h)
                commit(d, "Highlight added.")
            elif c in ("e", "d", "m"):
                if not items:
                    print("  Nothing here yet.")
                    continue
                n = ask("Which number")
                if not (n.isdigit() and 1 <= int(n) <= len(items)):
                    continue
                idx = int(n) - 1
                if c == "e":
                    items[idx] = edit_item(HIGHLIGHT, items[idx], items, "title",
                                           folder_base=lambda it: (it.get("arxiv") or slug(it.get("title"))).replace(".", "_").replace("/", "_"))
                    commit(d, "Updated.")
                elif c == "d" and yes("Delete this highlight?", False):
                    items.pop(idx)
                    commit(d, "Deleted.")
                elif c == "m":
                    t = ask("New position (1-%d)" % len(items))
                    if t.isdigit() and 1 <= int(t) <= len(items):
                        items.insert(int(t) - 1, items.pop(idx))
                        commit(d, "Moved.")
        except KeyboardInterrupt:
            print("\n  Cancelled.")
            d = load()


def do_news():
    crud("News & updates", lambda d: d["news"], NEWS, "title", ["date", "kind", "title"], noun="news item", new_first=True)


def do_awards():
    crud("Awards & honours", lambda d: d["awards"], AWARD, "title", ["date", "title", "who"], noun="award", new_first=True)


def do_areas():
    crud("Research areas", lambda d: d["research_areas"], AREA, "title", ["title"], noun="research area")


def do_collab():
    crud("Collaborations", lambda d: d["collaborations"], COLLAB, "name", ["name", "location"], noun="collaboration")


def do_resources():
    while True:
        c = menu("Resources & lectures", [("b", "Free books"), ("o", "Online resources"), ("l", "Video lectures")])
        if c == "b":
            crud("Free books", lambda d: d["resources"].setdefault("books", []), RES, "title", ["title"], noun="book")
        elif c == "o":
            crud("Online resources", lambda d: d["resources"].setdefault("online", []), RES, "title", ["title"], noun="resource")
        elif c == "l":
            crud("Video lectures", lambda d: d["lectures"], LECTURE, "title", ["title", "note"], noun="lecture")
        else:
            return


def parse_files(s):
    """Accept a folder, or one/many file paths (drag-and-drop friendly, quotes ok)."""
    try:
        parts = shlex.split(s, posix=(os.name != "nt"))
    except ValueError:
        parts = [s]
    files = []
    for p in parts:
        p = clean_path(p)
        pp = Path(p)
        if pp.is_dir():
            files += sorted(x for x in pp.iterdir() if x.suffix.lower() in IMG_EXT)
        elif pp.is_file():
            files.append(pp)
        else:
            print("  skipped (not found): %s" % p)
    return files


def do_gallery():
    d = load()
    while True:
        albums = d["albums"]
        print("\n== Gallery albums (%d) ==" % len(albums))
        for i, a in enumerate(albums, 1):
            print("  %2d. %s  (%s, %d photos)" % (i, a.get("title"), a.get("date", ""), len(a.get("photos", []))))
        c = menu("Gallery", [("a", "New album"), ("p", "Add photos to an album"), ("e", "Edit album title / date / description"),
                             ("c", "Edit a photo caption"), ("r", "Remove a photo"), ("d", "Delete an album")])
        if c is None:
            return
        try:
            if c == "a":
                a = edit_item([F("title", "Album title", required=True), F("date", "Date", "date"), F("description", "Description (optional)", "text")],
                              {}, albums, "title")
                a["photos"] = []
                albums.insert(0, a)
                commit(d, "Album created. Now add photos to it.")
                if yes("Add photos now?"):
                    add_photos(d, a)
            elif albums:
                n = ask("Which album number")
                if not (n.isdigit() and 1 <= int(n) <= len(albums)):
                    print("  Not a valid number.")
                    continue
                a = albums[int(n) - 1]
                if c == "p":
                    add_photos(d, a)
                elif c == "e":
                    new = edit_item([F("title", "Album title", required=True), F("date", "Date", "date"), F("description", "Description", "text")], a, albums, "title")
                    a.update({k: new[k] for k in ("title", "date", "description")})
                    commit(d, "Album updated.")
                elif c in ("c", "r"):
                    for i, ph in enumerate(a["photos"], 1):
                        print("   %2d. %s   %s" % (i, Path(ph["image"]).name, ph.get("caption", "")))
                    k = ask("Photo number")
                    if k.isdigit() and 1 <= int(k) <= len(a["photos"]):
                        ph = a["photos"][int(k) - 1]
                        if c == "c":
                            ph["caption"] = ask("Caption ('-' clears)", ph.get("caption", ""))
                            if ph["caption"] == "-":
                                ph["caption"] = ""
                        elif yes("Remove this photo from the album? (the file itself is kept)", False):
                            a["photos"].pop(int(k) - 1)
                        commit(d, "Photo updated.")
                elif c == "d" and yes("Delete album '%s'? (image files are kept)" % a["title"], False):
                    albums.remove(a)
                    commit(d, "Album deleted.")
        except KeyboardInterrupt:
            print("\n  Cancelled.")
            d = load()


def add_photos(d, album):
    print("  Give a folder, or one or more image files (you can drag them into this window). They are copied to images/gallery/%s/." % album["id"])
    files = parse_files(ask("  Folder / files"))
    if not files:
        print("  No images found.")
        return
    dest_dir = IMG / "gallery" / album["id"]
    dest_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        dest = dest_dir / f.name
        if not dest.exists() or dest.resolve() != f.resolve():
            shutil.copy2(f, dest)
        rel = "images/gallery/%s/%s" % (album["id"], dest.name)
        if not any(p["image"] == rel for p in album["photos"]):
            album["photos"].append({"image": rel, "caption": ""})
    commit(d, "%d photo(s) added. (Captions are optional: use 'Edit a photo caption'.)" % len(files))


SETTINGS = [
    F("group_name", "Group name"), F("brand_title", "Short name shown in the top-left of every page"),
    F("institute", "Institute"), F("city", "City, country"), F("address", "Postal address (Contact page)"),
    F("map_url", "Link to the map (Google Maps URL)"), F("email", "Main contact email"), F("group_email", "Group email (optional)"),
    F("tagline", "Tagline (under the headline)"),
    F("hero_headline", "Home page headline (put *asterisks* around the word to highlight)"),
    F("about_title", "About section title (use *asterisks* to highlight a word)"),
    F("join_title", "Bottom call-to-action title"), F("join_text", "Bottom call-to-action text", "text"),
    F("calendar_embed", "Google Calendar embed URL"), F("calendar_note", "Line above the calendar"),
    F("social", "Group links (INSPIRE group page, GitHub, YouTube ...)", "links"),
]


def do_settings():
    d = load()
    s = d["settings"]
    while True:
        opts = [(str(i), "%s  [%s]" % (f.prompt.split(" (")[0], (str(s.get(f.key, "")) if f.kind != "links" else "%d links" % len(s.get(f.key, [])))[:50])) for i, f in enumerate(SETTINGS, 1)]
        opts.append(("p", "About paragraphs (edit the 'About' text)"))
        opts.append(("t", "Tools / method badges on the About section"))
        c = menu("Site settings", opts)
        if c is None:
            return
        try:
            if c == "p":
                cur = s.get("about", [])
                print("Current paragraphs:")
                for i, p in enumerate(cur, 1):
                    print("  %d) %s" % (i, p[:110] + ("..." if len(p) > 110 else "")))
                act = ask("[a]dd paragraph, [e]dit one, [d]elete one, Enter = back").lower()
                if act == "a":
                    cur.append(edit_text("New paragraph"))
                elif act in ("e", "d"):
                    n = ask("Number")
                    if n.isdigit() and 1 <= int(n) <= len(cur):
                        if act == "e":
                            cur[int(n) - 1] = edit_text("Edit paragraph", cur[int(n) - 1])
                        else:
                            cur.pop(int(n) - 1)
                s["about"] = [p for p in cur if p]
            elif c == "t":
                s["method_tags"] = edit_list("Tools / methods", s.get("method_tags", []))
            else:
                f = SETTINGS[int(c) - 1]
                tmp = edit_item([f], {f.key: s.get(f.key, "")}, [], f.key)
                s[f.key] = tmp[f.key]
            commit(d, "Settings saved.")
        except KeyboardInterrupt:
            print("\n  Cancelled.")
            d = load()
            s = d["settings"]


def do_publications():
    while True:
        d = load()
        pub = json.loads((DATA / "publications.json").read_text(encoding="utf-8")) if (DATA / "publications.json").exists() else {}
        srcs = upub.sources_from_site(d)
        print("\nPublications: %d papers, last INSPIRE sync: %s" % (len(pub.get("papers", [])), pub.get("fetched_at") or "never (imported from old site)"))
        print("Sources: %s" % (", ".join("%s (%s)" % (s["label"], s["recid"]) for s in srcs) or "none"))
        c = menu("Publications", [("r", "Refresh from INSPIRE now"), ("s", "Add another INSPIRE profile as a source (e.g. a postdoc whose papers should be listed too)"),
                                  ("x", "Remove a source"), ("h", "Hide a paper from the website"), ("u", "Un-hide a paper"),
                                  ("m", "Add a paper manually (not on INSPIRE)")])
        if c is None:
            return
        try:
            if c == "r":
                do_refresh()
            elif c == "s":
                label = ask("Name for this source")
                rid = edit_inspire("")
                if rid and rid.isdigit():
                    if not d["settings"].get("publication_sources"):
                        d["settings"]["publication_sources"] = [{"label": x["label"], "inspire": x["recid"]} for x in srcs]
                    d["settings"]["publication_sources"].append({"label": label, "inspire": rid})
                    commit(d, "Source added. Choose 'Refresh' to fetch.")
            elif c == "x":
                cur = d["settings"].get("publication_sources") or srcs
                for i, s in enumerate(cur, 1):
                    print("  %d) %s" % (i, s.get("label")))
                n = ask("Number to remove")
                if n.isdigit() and 1 <= int(n) <= len(cur):
                    cur.pop(int(n) - 1)
                    d["settings"]["publication_sources"] = [{"label": s.get("label", ""), "inspire": s.get("inspire") or s.get("recid")} for s in cur]
                    commit(d, "Source removed.")
            elif c == "h":
                q = ask("Part of the title to search for").lower()
                hits = [p for p in pub.get("papers", []) if q and q in sitegen.clean_title(p["title"]).lower()][:15]
                for i, p in enumerate(hits, 1):
                    print("  %d) %s (%s)" % (i, sitegen.clean_title(p["title"])[:90], p.get("year")))
                n = ask("Number to hide")
                if n.isdigit() and 1 <= int(n) <= len(hits):
                    d.setdefault("publications_hidden", []).append(hits[int(n) - 1]["id"])
                    commit(d, "Hidden.")
            elif c == "u":
                hid = d.get("publications_hidden", [])
                for i, h in enumerate(hid, 1):
                    t = next((sitegen.clean_title(p["title"]) for p in pub.get("papers", []) if p["id"] == h), h)
                    print("  %d) %s" % (i, t[:90]))
                n = ask("Number to un-hide")
                if n.isdigit() and 1 <= int(n) <= len(hid):
                    hid.pop(int(n) - 1)
                    commit(d, "Un-hidden.")
            elif c == "m":
                title = ask("Title *")
                authors = [a.strip() for a in ask("Authors (comma separated, 'First Last' form)").split(",") if a.strip()]
                venue = ask("Journal reference (blank for preprint)")
                year = ask("Year", str(datetime.date.today().year))
                ax = ask("arXiv id (optional)")
                doi = ask("DOI (optional, e.g. 10.1088/...)")
                if title:
                    d.setdefault("publications_manual", []).append({
                        "id": ax or "manual-" + slug(title)[:40], "authors": authors, "author_count": len(authors), "title": title,
                        "journal": venue, "year": year, "date": year, "arxiv": ax, "doi": doi, "citations": None,
                        "type": "article" if venue else "preprint", "inspire_url": ""})
                    commit(d, "Paper added.")
        except KeyboardInterrupt:
            print("\n  Cancelled.")


def do_refresh():
    n = upub.update()
    if n:
        sitegen.build(verbose=False)
        print("  OK  %d papers. Site rebuilt." % n)


def do_check():
    d = load()
    missing = []

    def chk(path, what):
        if path and not (ROOT / path).exists():
            missing.append((path, what))
    for m in d["members"]:
        chk(m.get("photo"), "photo of " + m["name"])
    for a in d["alumni"]:
        chk(a.get("photo"), "photo of " + a["name"])
    for h in d["highlights"]:
        chk(h.get("image"), "highlight figure: " + (h.get("title") or "")[:40])
    for al in d["albums"]:
        for ph in al.get("photos", []):
            chk(ph["image"], "gallery: " + al["title"])
    chk("images/site/cmb.jpg", "banner background (optional)")
    if not missing:
        print("  All images referenced by the site are present.")
        return
    print("  Images the site expects but cannot find yet (pages show initials / placeholders until you add them):")
    for p, w in missing:
        print("   - %-48s  %s" % (p, w))


def do_git():
    if not (ROOT / ".git").exists():
        print("  This folder is not a git repository yet. In a terminal here run:\n    git init\n    git remote add origin https://github.com/<you>/<you>.github.io.git\n  then come back.")
        return
    print(subprocess.run(["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True).stdout or "  (no changes)")
    if not yes("Commit everything and push to GitHub?", False):
        return
    msg = ask("Commit message", "Update website")
    for cmd in (["git", "add", "-A"], ["git", "commit", "-m", msg], ["git", "push"]):
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        print((r.stdout + r.stderr).strip())
        if r.returncode != 0 and cmd[1] != "commit":
            print("  Stopped: %s failed." % " ".join(cmd))
            return


def do_serve(port=8000):
    import http.server
    import socketserver
    import threading
    import webbrowser
    os.chdir(ROOT)
    handler = http.server.SimpleHTTPRequestHandler
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), handler) as httpd:
        url = "http://localhost:%d/" % port
        print("  Previewing at %s   (Ctrl-C to stop)" % url)
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  Preview stopped.")


# --------------------------------------------------------------------------- main menu

def main_menu():
    print("\n  Cosmology & Statistical Physics Group - website manager")
    print("  Everything is saved to data/site.json and the pages rebuild automatically.")
    while True:
        c = menu("MAIN MENU", [
            ("1", "Team members (add / edit / move to alumni)"),
            ("2", "Former members"),
            ("3", "Research highlights"),
            ("4", "News & updates"),
            ("5", "Awards & honours"),
            ("6", "Gallery (albums & photos)"),
            ("7", "Publications (refresh from INSPIRE, hide, add)"),
            ("8", "Research areas"),
            ("9", "Collaborations"),
            ("r", "Resources & video lectures"),
            ("s", "Site settings (name, headline, about text, contact, calendar ...)"),
            ("c", "Check for missing images"),
            ("b", "Rebuild the website pages"),
            ("v", "Preview the website in my browser"),
            ("g", "Commit & push to GitHub"),
        ], back="Quit")
        if c is None:
            print("Bye!")
            return
        try:
            {"1": do_members, "2": do_alumni, "3": do_highlights, "4": do_news, "5": do_awards, "6": do_gallery,
             "7": do_publications, "8": do_areas, "9": do_collab, "r": do_resources, "s": do_settings, "c": do_check,
             "b": lambda: sitegen.build(), "v": do_serve, "g": do_git}[c]()
        except KeyboardInterrupt:
            print("\n  Cancelled.")


def main():
    arg = sys.argv[1].lower() if len(sys.argv) > 1 else "menu"
    try:
        if arg == "menu":
            main_menu()
        elif arg == "build":
            sitegen.build()
        elif arg in ("pubs", "publications"):
            do_refresh()
        elif arg == "serve":
            do_serve(int(sys.argv[2]) if len(sys.argv) > 2 else 8000)
        elif arg == "check":
            do_check()
        else:
            print(__doc__)
    except (Quit, KeyboardInterrupt):
        print("\nBye!")


if __name__ == "__main__":
    main()
