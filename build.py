"""Build the public bookmarks site from Brave's Default profile.

Run:  python build.py
Reads Brave's Bookmarks file, drops anything private or not fit for a public
page, strips tracking parameters, and writes bookmarks.json, README.md and
index.html next to this script.
"""
import html
import json
import os
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

SRC = os.path.expandvars(
    r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data\Default\Bookmarks")
OUT = os.path.dirname(os.path.abspath(__file__))

# Whole folders that are personal by nature or not fit to publish.
EXCLUDE_FOLDERS = {
    "Google Drive & Sheets",      # private docs and sheets
    "Email & Social",             # inboxes, chats
    "Numbers & SMS",              # SMS-verification / burner numbers
    "Accounts & Proxies",         # bought accounts, proxies
    "Tracked Ads & Examples",     # competitor tracking (business research)
    "Product Ideas",              # product research (business research)
}

# Any URL containing one of these is dropped.
EXCLUDE_URL_PARTS = [
    # local / own servers / own sites
    "127.0.0.1", "localhost", "82.29.169.60", "147.93.44.26", "hstgr.cloud",
    "muhammaddahab.com", "wikipen.net/wp-admin", "liptoy.com", "weakwan.com",
    "hpanel.hostinger.com", "dash.cloudflare.com", "console.cloud.google.com",
    # personal account pages, documents, sessions
    "chatgpt.com/c/", "drive.google.com", "docs.google.com", "onedrive.live.com",
    "mail.google.com", "mail.hostinger.com", "web.telegram.org",
    "draft.blogger.com", "admanager.google.com", "fba-formula.circle.so/messages",
    "istockphoto.com/collaboration", "app.foreplay.co/share", "app.milanote.com",
    "aramex.com/eg/ar/track", "5sim.net/order", "generateprivacypolicy.com/download",
    "initialSessionID", "monetoad.com", "boompen.com",
    # finance accounts and risky crypto
    "garantex.org", "qiwi.com", "binance.com", "myaccount.payoneer.com",
    "alahlynet.com.eg", "jup.ag",
    # piracy / fraud-adjacent / not for a public page
    "1337x.to", "thepiratebay.org", "getpaidstock.com", "namso-gen.com",
    "ssnregistry.org", "create-edu-email", "create-free-edu-mail",
    "watch?v=W7eDliqKKQM", "arbitragev2.com", "filehorse.com",
    # junk: browser-internal, raw images/files, empty searches
    "chrome://", "chrome-extension://", "view-source:", "i.ytimg.com",
    "import.cdn.thinkific.com", "google.com/search", "webcache.googleusercontent",
]

# Query parameters that only track the click.
TRACKING = re.compile(
    r"^(utm_.*|gclid|gad_source|_gl|fbclid|srsltid|referralCode|recommended_by|"
    r"search_id|surface_detail|pli|rlz|aqs|oq|sourceid|ie|ref_|term|adid|"
    r"campaignid|branded_enterprise|BOID|code|campaign_id|android-min-version|"
    r"ios-min-version|is_sa|x_api_client_id|x_api_client_location|lfhs|"
    r"projectId|authuser|client|channel|inv|invt|tab|ReturnUrl|callbackUrl|cms_platform|th)$")

# Hosts where the whole query string is noise.
DROP_QUERY_HOSTS = {"www.pond5.com", "www.shopify.com", "apps.shopify.com",
                    "www.codecademy.com", "web-hosting.thetop10sites.com",
                    "developers.google.com", "orders.bizee.com", "datnguyentv.com",
                    "store.bdthemes.com", "codecanyon.net", "ecomhunt.com",
                    "advaultservices.gumroad.com", "www.monsterinsights.com",
                    "www.elyosr-sports.com", "www.brandcrowd.com",
                    "www.elegantthemes.com", "gemini.google.com"}


def clean_url(url):
    p = urlsplit(url)
    if p.netloc in DROP_QUERY_HOSTS and "speed/pagespeed" not in p.path:
        query = ""
    elif "speed/pagespeed" in p.path:
        query = ""
    else:
        query = urlencode([(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                           if not TRACKING.match(k)])
    frag = p.fragment
    if frag.startswith(":~:text") or frag.startswith("e52ca"):
        frag = ""
    return urlunsplit((p.scheme, p.netloc, p.path, query, frag))


def clean_name(name):
    return re.sub(r"\s*\((?:2|empty)\)$", "", name).strip()


def collect():
    with open(SRC, encoding="utf-8") as f:
        data = json.load(f)
    groups, seen, dropped = {}, set(), 0

    def walk(node, path):
        nonlocal dropped
        for child in node.get("children", []):
            if child.get("type") == "folder":
                walk(child, path + [child["name"]])
                continue
            url = child["url"]
            if (path and path[0] in EXCLUDE_FOLDERS) or any(x in url for x in EXCLUDE_URL_PARTS):
                dropped += 1
                continue
            url = clean_url(url)
            key = url.rstrip("/").replace("://www.", "://").replace("http://", "https://")
            if key in seen:
                dropped += 1
                continue
            seen.add(key)
            cat = path[0] if path else "Other"
            sub = " / ".join(path[1:])
            groups.setdefault(cat, []).append(
                {"name": clean_name(child["name"]), "url": url, "sub": sub})

    for root in data["roots"].values():
        if isinstance(root, dict):
            walk(root, [])
    return groups, dropped


def write_readme(groups, total):
    lines = ["# Favorites — Muhammad Dahab", "",
             f"{total} hand-picked links, live at **https://fav.muhammaddahab.com**.", "",
             "Exported from my browser bookmarks with `build.py`. Private links "
             "(personal dashboards, documents, accounts) are filtered out.", ""]
    for cat, items in groups.items():
        lines += [f"## {cat}", ""]
        for it in items:
            sub = f" _({it['sub']})_" if it["sub"] else ""
            lines.append(f"- [{it['name']}]({it['url']}){sub}")
        lines.append("")
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def write_html(groups, total):
    nav = "".join(
        f'<a href="#c{i}">{html.escape(c)} <span>{len(v)}</span></a>'
        for i, (c, v) in enumerate(groups.items()))
    sections = []
    for i, (cat, items) in enumerate(groups.items()):
        cards = []
        for it in items:
            host = urlsplit(it["url"]).netloc.removeprefix("www.")
            name, _, desc = it["name"].partition(" – ")
            hay = html.escape(f"{it['name']} {host} {cat} {it['sub']}".lower(), quote=True)
            cards.append(
                f'<li data-q="{hay}"><a href="{html.escape(it["url"], quote=True)}" '
                f'target="_blank" rel="noopener">'
                f'<img src="https://icons.duckduckgo.com/ip3/{html.escape(host)}.ico" '
                f'alt="" loading="lazy" width="20" height="20">'
                f'<span class="t"><b>{html.escape(name)}</b>'
                f'{"<i>" + html.escape(desc) + "</i>" if desc else ""}'
                f'<small>{html.escape(host)}</small></span></a></li>')
        sections.append(
            f'<section id="c{i}"><h2>{html.escape(cat)} <span>{len(items)}</span></h2>'
            f'<ul>{"".join(cards)}</ul></section>')
    with open(os.path.join(OUT, "template.html"), encoding="utf-8") as f:
        page = f.read()
    page = (page.replace("{{TOTAL}}", str(total)).replace("{{NAV}}", nav)
                .replace("{{SECTIONS}}", "".join(sections)))
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)


def main():
    groups, dropped = collect()
    total = sum(len(v) for v in groups.values())
    with open(os.path.join(OUT, "bookmarks.json"), "w", encoding="utf-8") as f:
        json.dump(groups, f, ensure_ascii=False, indent=2)
    write_readme(groups, total)
    write_html(groups, total)
    print(f"kept {total}, dropped {dropped}")


if __name__ == "__main__":
    main()
