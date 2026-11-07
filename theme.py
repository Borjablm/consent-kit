"""Read a site's colours from its live homepage and write a banner theme. No login or API key needed.

    python theme.py https://notegpt.com/                 # print the theme
    python theme.py https://notegpt.com/ --site notegpt  # also write it into sites/notegpt.json
    python theme.py https://notegpt.com/ --preview test/shots/notegpt.png   # banner drawn over the live page

Opens the page in headless Chrome and reads the computed styles the visitor actually sees: page
background, body text, content link colour, and the main button's colour and rounding. The banner
font is inherited from the page, so it needs no setting. Colours are checked for contrast (WCAG AA:
4.5:1 for text, 3:1 for button outlines) and fall back to the body text colour when they fail.
A theme that was tuned by hand can be kept by not passing --site.
"""
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent

READ = r"""() => {
  const rgb = s => { const m = (s || '').match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?/); return m ? {r:+m[1], g:+m[2], b:+m[3], a: m[4] === undefined ? 1 : +m[4]} : null; };
  const solid = c => c && c.a > 0.5;
  const vis = e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e); return r.width > 40 && r.height > 16 && s.visibility !== 'hidden' && s.display !== 'none'; };
  let bg = null;
  for (const el of [document.body, document.documentElement, document.querySelector('main, #page, .site, .wp-site-blocks')]) {
    if (!el) continue; const c = rgb(getComputedStyle(el).backgroundColor); if (solid(c)) { bg = c; break; }
  }
  const fg = rgb(getComputedStyle(document.querySelector('main p, article p, .entry-content p, p') || document.body).color);
  const link = [...document.querySelectorAll('main a, article a, .entry-content a, .wp-site-blocks a, a')]
    .filter(a => vis(a) && !a.closest('header, nav, footer') && a.textContent.trim().length > 2)
    .map(a => rgb(getComputedStyle(a).color))[0] || null;
  const buttons = [...document.querySelectorAll('.wp-block-button__link, .wp-element-button, a.button, .btn, button, input[type=submit], a[class*="button"], a[class*="btn"]')]
    .filter(e => vis(e) && !e.closest('#consent-kit, #azv-consent, #lai-consent, #qc-consent')).slice(0, 30)
    .map(e => { const s = getComputedStyle(e); return { bg: rgb(s.backgroundColor), fg: rgb(s.color), border: rgb(s.borderTopColor), borderWidth: parseFloat(s.borderTopWidth), radius: parseFloat(s.borderTopLeftRadius) || 0, height: e.getBoundingClientRect().height }; });
  const links = [...document.querySelectorAll('a')].filter(a => vis(a) && a.textContent.trim().length > 2).slice(0, 80).map(a => rgb(getComputedStyle(a).color));
  return { bg, fg, link, buttons, links };
}"""


def hexc(c):
    return "#%02x%02x%02x" % (round(c["r"]), round(c["g"]), round(c["b"]))


def lum(c):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c["r"]) + 0.7152 * ch(c["g"]) + 0.0722 * ch(c["b"])


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def is_greyish(c):
    return max(c["r"], c["g"], c["b"]) - min(c["r"], c["g"], c["b"]) < 24


def theme_for(raw):
    white = {"r": 255, "g": 255, "b": 255, "a": 1}
    bg = raw["bg"] or white
    fg = raw["fg"] if raw["fg"] and contrast(raw["fg"], bg) >= 4.5 else ({"r": 34, "g": 34, "b": 34, "a": 1} if lum(bg) > 0.4 else white)
    notes = []

    # Accent: the most used brand (non-grey) colour across button fills, button outlines, button text
    # and links (buttons count double), among those that read on the banner background.
    votes = {}
    def vote(c, w, why):
        if c and c["a"] > 0.5 and not is_greyish(c) and contrast(c, bg) >= 3:
            k = hexc(c)
            n, _, whys = votes.get(k, (0, c, set()))
            votes[k] = (n + w, c, whys | {why})
    for btn in raw["buttons"]:
        vote(btn["bg"], 2, "button fill")
        if btn["borderWidth"] >= 1:
            vote(btn["border"], 2, "button outline")
        vote(btn["fg"], 1, "button text")
    vote(raw["link"], 2, "content link")
    for c in raw["links"]:
        vote(c, 1, "links")
    accent = None
    if votes:
        k = max(votes, key=lambda k: votes[k][0])
        accent, src = votes[k][1], " + ".join(sorted(votes[k][2]))
    accent_hex = hexc(accent) if accent else None
    b = next((x for x in raw["buttons"] if accent_hex and accent_hex in (hexc(x["bg"]) if x["bg"] else "", hexc(x["border"]) if x["border"] else "")), raw["buttons"][0] if raw["buttons"] else None)
    t = {"bg": hexc(bg), "fg": hexc(fg), "border": hexc(fg) + "33"}
    if accent:
        on_accent = white if contrast(white, accent) >= contrast(fg, accent) else fg
        t.update({"button": hexc(accent), "buttonHoverBg": hexc(accent), "buttonHoverFg": hexc(on_accent), "buttonBg": hexc(bg)})
        notes.append(f"accent from {src}")
        if contrast(accent, bg) >= 4.5:
            t["link"] = hexc(accent)
        else:
            t["buttonText"] = hexc(fg)
            notes.append(f"accent {hexc(accent)} is {contrast(accent, bg):.1f}:1 on the background, too faint for text, so button text uses the body colour")
    else:
        t.update({"button": hexc(fg), "buttonHoverBg": hexc(fg), "buttonHoverFg": hexc(bg), "buttonBg": hexc(bg)})
        notes.append("no usable brand colour found, buttons use the text colour")

    r = b["radius"] if b else 6
    pill = b and r >= b["height"] / 2 - 1
    t["buttonRadius"] = "100px" if pill else f"{min(round(r), 24)}px"
    t["radius"] = "15px" if pill else f"{min(max(round(r) + 4, 6), 20)}px"
    t["shadow"] = "0 8px 24px rgba(0,0,0,.12)" if lum(bg) > 0.4 else "0 8px 24px rgba(0,0,0,.45)"
    return t, notes


def read(url, preview=None, texts=None):
    """Read the page's colours. With preview=path, also draw the banner with the detected theme over
    the live page in the headless browser (desktop and phone) and save screenshots. The site itself
    is never changed."""
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1366, "height": 900})
        pg.goto(url, wait_until="load", timeout=60000)
        pg.wait_for_timeout(2500)
        raw = pg.evaluate(READ)
        if preview:
            theme, _ = theme_for(raw)
            cfg = {"cookie": "ck_preview", "theme": theme, "texts": texts or {}, "links": {"en": url}}
            js = (ROOT / "consent-kit.js").read_text(encoding="utf-8")
            for width, height, suffix in ((1366, 900, ""), (375, 800, "-phone")):
                pg.set_viewport_size({"width": width, "height": height})
                pg.add_style_tag(content="#azv-consent,#lai-consent,#qc-consent,#consent-kit{display:none!important}")
                pg.evaluate("delete window.ConsentKit; document.getElementById('consent-kit-css')?.remove(); document.getElementById('consent-kit')?.remove(); document.cookie='ck_preview=; max-age=0; path=/'")
                pg.evaluate(f"window.ConsentKitConfig = {json.dumps(cfg)}; " + js)
                pg.add_style_tag(content="#consent-kit:not([hidden]){display:flex!important}")
                pg.wait_for_timeout(300)
                pg.screenshot(path=str(preview).replace(".png", f"{suffix}.png"))
        b.close()
    return raw


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0].startswith("-"):
        raise SystemExit(__doc__)
    url = args[0]
    site = args[args.index("--site") + 1] if "--site" in args else None
    preview = args[args.index("--preview") + 1] if "--preview" in args else None
    raw = read(url, preview)
    theme, notes = theme_for(raw)
    print(json.dumps(theme, indent=2))
    print("; ".join(notes))
    if site:
        path = ROOT / "sites" / f"{site}.json"
        cfg = json.loads(path.read_text(encoding="utf-8")) if path.exists() else json.loads((ROOT / "sites" / "_template.json").read_text(encoding="utf-8"))
        cfg["theme"] = theme
        path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote theme into {path.relative_to(ROOT)}")
