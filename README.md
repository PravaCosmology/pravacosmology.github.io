# Cosmology & Statistical Physics Group - website

A static site (plain HTML/CSS/JS) for GitHub Pages. You never edit the HTML by hand:
all content lives in `data/site.json` and `data/publications.json`, and Python regenerates every page.
Needs only Python 3.8+ (no packages).

## Everyday use
```
python manage.py
```
A menu lets you add / edit / remove: **team members, former members, research highlights, news, awards,
gallery albums & photos, research areas, collaborations, resources, site settings** and manage **publications**.
The site is rebuilt after every change. Then:

* `v` - preview locally (http://localhost:8000)
* `g` - commit & push (or use git yourself)
* `c` - list images that are referenced but missing

Command line shortcuts: `python manage.py build | pubs | serve | check`

## Publications (INSPIRE)
`python update_publications.py` (or menu 7 -> Refresh) pulls the papers of the INSPIRE author profile(s)
in Settings -> publication sources (default: the group lead, id 1046872) into `data/publications.json`.
Group members are bolded and become filter chips. You can hide a paper or add one by hand from the menu.
If INSPIRE is unreachable the existing list is kept. `.github/workflows/update-publications.yml`
does this automatically every week once the repo is on GitHub.

Every member has an INSPIRE link (give the author id in the member form; without one the site links to an
INSPIRE author search) plus any number of extra links (website, Google Scholar, ORCID, ADS, GitHub...).

## Images
All under `images/`: `team/`, `past_members/`, `research/`, `gallery/`, `collaborations/`, `site/` (`cmb.jpg` is
the page banner). Existing file names were kept. Drop a photo in and give its file name in the editor (or
give a path on your computer and it is copied for you). Missing images fall back to initials / placeholders.

## Look & feel
Colours, fonts and spacing: `assets/css/style.css` (variables at the top). Page layout: `sitegen.py`.
Dark/light toggle is built in. After changing either, run `python manage.py build`.

## Publishing
Push the folder to your `<user>.github.io` repository (or any repo with Pages enabled on the main branch, root folder).
`.nojekyll` is included.
