#!/usr/bin/env python3
"""
Clickdy Phones - AUTOMATIC importer (no manual work, no paid API, no scraping of phone-spec sites).

Source: Wikipedia's official public API. Every article that uses the "Infobox mobile phone" template is a phone.
For each one we read the infobox (all the spec fields), clean the wiki markup and save phones-data/<slug>.json.
Images come only from Wikimedia Commons and only when their licence allows reuse (CC0 / public domain / CC BY / CC BY-SA);
the licence and author are stored and shown on the page. Text/data are credited to Wikipedia (CC BY-SA 4.0).

It runs on a schedule in GitHub Actions: first it back-fills older phones, then it keeps adding new ones and refreshing old ones.
Standard library only.
"""
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, read_json, slugify, write_json  # noqa: E402

API = os.environ.get("WIKI_API", "https://en.wikipedia.org/w/api.php")
UA = "ClickdyPhonesBot/1.0 (https://clickdy.com; phone specification importer; contact via https://clickdy.com/contact.html)"
TEMPLATES = [t.strip() for t in os.environ.get("PHONE_TEMPLATES", "Infobox mobile phone").split(",") if t.strip()]
MAX_PER_RUN = int(os.environ.get("PHONES_MAX_PER_RUN", "1000"))     # keeps each run (and each commit) a sensible size
REFRESH_DAYS = int(os.environ.get("PHONES_REFRESH_DAYS", "45"))     # re-read old pages now and then to pick up edits
BATCH = 20
DATA_DIR = os.path.join(ROOT, "phones-data")
STATE_PATH = os.path.join(ROOT, "data", "phone-import-state.json")
FREE_LICENCE = re.compile(r"^(cc0|public domain|pd\b|cc[- ]by(?:[- ]sa)?\b|attribution|gfdl-self|\{\{pd)", re.I)


# ------------------------------------------------------------------ Wikipedia API
def api(params, retries=4):
    q = dict(params, format="json", formatversion="2", maxlag="5")
    url = API + "?" + urllib.parse.urlencode(q)
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode("utf-8"))
            if isinstance(data, dict) and data.get("error", {}).get("code") == "maxlag":
                time.sleep(5 * (i + 1))
                continue
            time.sleep(0.25)
            return data
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            last = e
            time.sleep(3 * (i + 1))
    raise RuntimeError("Wikipedia API failed: %s" % last)


def list_titles(template):
    titles, cont = [], {}
    while True:
        d = api(dict({"action": "query", "list": "embeddedin", "eititle": "Template:" + template, "einamespace": "0", "eilimit": "500"}, **cont))
        titles += [x["title"] for x in d.get("query", {}).get("embeddedin", [])]
        cont = d.get("continue") or {}
        if not cont:
            return titles


def fetch_pages(titles):
    d = api({"action": "query", "prop": "revisions", "rvprop": "content|ids|timestamp", "rvslots": "main", "titles": "|".join(titles), "redirects": "1"})
    out = []
    for pg in d.get("query", {}).get("pages", []):
        revs = pg.get("revisions") or []
        if pg.get("missing") or not revs:
            continue
        out.append({"title": pg["title"], "revid": revs[0].get("revid"), "text": revs[0]["slots"]["main"]["content"]})
    return out


def fetch_images(files):
    """files = ['Foo.jpg', ...] -> {'Foo.jpg': {...}} for Commons files whose licence allows reuse."""
    res = {}
    for i in range(0, len(files), 40):
        chunk = files[i:i + 40]
        d = api({"action": "query", "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": "500", "titles": "|".join("File:" + f for f in chunk)})
        norm = {n["to"]: n["from"] for n in d.get("query", {}).get("normalized", [])}
        for pg in d.get("query", {}).get("pages", []):
            info = (pg.get("imageinfo") or [None])[0]
            if not info or pg.get("imagerepository") != "shared":      # shared = Wikimedia Commons (free files). Skip local "non-free" files.
                continue
            meta = info.get("extmetadata", {})
            lic = (meta.get("LicenseShortName", {}).get("value") or "").strip()
            if not FREE_LICENCE.search(lic):
                continue
            artist = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value") or "").strip() or "Wikimedia Commons"
            title = pg["title"]
            key = norm.get(title, title)
            fname = key[5:] if key.startswith("File:") else key
            thumb = info.get("thumburl") or info.get("url")
            if not thumb:
                continue
            res[fname.replace("_", " ")] = {
                "file": thumb, "thumb": re.sub(r"/500px-", "/250px-", thumb), "alt": "",
                "credit": "%s, %s via Wikimedia Commons" % (artist[:80], lic), "source_url": info.get("descriptionurl") or "", "license": lic}
    return res


# ------------------------------------------------------------------ wikitext helpers
def extract_infobox(text, names):
    for name in names:
        m = re.search(r"\{\{\s*" + re.escape(name).replace(r"\ ", r"[ _]") + r"\s*(?=\||\n)", text, re.I)
        if not m:
            continue
        depth, i = 0, m.start()
        while i < len(text):
            if text.startswith("{{", i):
                depth += 1
                i += 2
            elif text.startswith("}}", i):
                depth -= 1
                i += 2
                if depth == 0:
                    return text[m.end():i - 2]
            else:
                i += 1
    return None


def split_params(body):
    parts, buf, d_curly, d_sq, i = [], [], 0, 0, 0
    while i < len(body):
        two = body[i:i + 2]
        if two == "{{":
            d_curly += 1; buf.append(two); i += 2; continue
        if two == "}}":
            d_curly -= 1; buf.append(two); i += 2; continue
        if two == "[[":
            d_sq += 1; buf.append(two); i += 2; continue
        if two == "]]":
            d_sq -= 1; buf.append(two); i += 2; continue
        c = body[i]
        if c == "|" and d_curly == 0 and d_sq == 0:
            parts.append("".join(buf)); buf = []
        else:
            buf.append(c)
        i += 1
    parts.append("".join(buf))
    out = {}
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            k = re.sub(r"[\s\-]+", "_", k.strip().lower())
            if k and v.strip():
                out[k] = v.strip()
    return out


LISTY = {"ubl", "unbulleted list", "plainlist", "plain list", "flatlist", "flat list", "hlist", "bulleted list", "ublist", "unbulleted_list"}
DROP = {"efn", "refn", "sfn", "citation needed", "cn", "clarify", "when", "who", "dubious", "failed verification", "better source needed", "update inline",
        "flag", "flagicon", "flagcountry", "tooltip", "main", "see also", "cite web", "cite news", "cite book", "cite journal", "cite press release", "webarchive"}


def _template(m):
    parts = m.group(1).split("|")
    name = parts[0].strip().lower().replace("_", " ")
    args = [a.strip() for a in parts[1:]]
    pos = [a for a in args if "=" not in a or re.match(r"^\s*[\d.]+\s*$", a)]
    if name in ("cvt", "convert"):
        nums = [a for a in pos if re.match(r"^-?[\d.,]+$", a)]
        units = [a for a in pos if not re.match(r"^-?[\d.,]+$", a) and not a.startswith(("abbr", "sp"))]
        if nums and units:
            return "%s %s" % (nums[0], units[0] if units[0] != "to" else (units[1] if len(units) > 1 else ""))
        return " ".join(pos[:2])
    if name in LISTY:
        items = []
        for a in args:
            for line in a.split("\n"):
                line = re.sub(r"^[*#\s]+", "", line.strip())
                if line and "=" not in line[:12]:
                    items.append(line)
        return ", ".join(items)
    if name in ("nowrap", "small", "nobr", "abbr", "lang", "smaller", "nowrap begin"):
        return args[-1] if name == "lang" and args else (args[0] if args else "")
    if name in ("start date", "start date and age", "release date", "release", "start-date", "date", "end date"):
        nums = [a for a in args if re.match(r"^\d+$", a)]
        if len(nums) >= 3:
            return "%04d-%02d-%02d" % (int(nums[0]), int(nums[1]), int(nums[2]))
        if len(nums) == 2:
            return "%04d-%02d" % (int(nums[0]), int(nums[1]))
        return nums[0] if nums else ""
    if name == "val":
        unit = next((a.split("=", 1)[1] for a in args if a.startswith("u=")), "")
        n = next((a for a in args if re.match(r"^[\d.,]+$", a)), "")
        return ("%s %s" % (n, unit)).strip()
    if name in ("nbsp", "spaces"):
        return " "
    if name in ("×", "x", "times"):
        return " × "
    if name in DROP or name.startswith("cite"):
        return ""
    return ""


def clean(v):
    if not v:
        return ""
    v = re.sub(r"<!--.*?-->", "", v, flags=re.S)
    v = re.sub(r"<ref[^>]*/>", "", v, flags=re.I)
    v = re.sub(r"<ref[^>]*>.*?</ref>", "", v, flags=re.S | re.I)
    v = re.sub(r"<br\s*/?>", ", ", v, flags=re.I)
    for _ in range(8):
        n = re.sub(r"\{\{([^{}]*)\}\}", _template, v)
        if n == v:
            break
        v = n
    v = re.sub(r"\[\[(?:File|Image|Category):[^\]]*\]\]", "", v, flags=re.I)
    v = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", v)
    v = re.sub(r"\[https?://\S+\s+([^\]]+)\]", r"\1", v)
    v = re.sub(r"\[https?://\S+\]", "", v)
    v = re.sub(r"</?[a-zA-Z][^>]*>", "", v)
    v = re.sub(r"'{2,}", "", v)
    v = html.unescape(v).replace("\xa0", " ")
    v = re.sub(r"^[\s*#:;]+", "", v, flags=re.M)
    v = re.sub(r"\n+", ", ", v.strip())
    v = re.sub(r"\s*,\s*(,\s*)+", ", ", v)
    v = re.sub(r"\s{2,}", " ", v).strip(" ,;")
    return v


# ------------------------------------------------------------------ mapping infobox -> our schema
def pick(p, *names):
    for n in names:
        if p.get(n):
            return p[n]
    return ""


GROUPS = [
    ("Launch", [("Announced / released", ("released", "released_date", "release_date")), ("Availability by country", ("availability_by_country", "availability")),
                ("Discontinued", ("discontinued",)), ("Series", ("series", "family")), ("Model", ("model", "models")), ("Predecessor", ("predecessor",)), ("Successor", ("successor",))]),
    ("Network", [("Technology", ("networks", "network")), ("SIM", ("sim", "sim_card"))]),
    ("Body", [("Form factor", ("form_factor", "type")), ("Dimensions", ("dimensions", "size")), ("Weight", ("weight", "mass")), ("Water protection", ("water_protection", "ingress_protection")),
              ("Other", ("other",))]),
    ("Platform", [("Operating system", ("os", "operating_system")), ("Chipset", ("soc", "system_on_chip", "chipset")), ("CPU", ("cpu",)), ("GPU", ("gpu",))]),
    ("Memory", [("RAM", ("memory", "ram")), ("Storage", ("storage", "internal_storage")), ("Card slot", ("memory_card", "removable_storage"))]),
    ("Display", [("Display", ("display", "screen"))]),
    ("Cameras", [("Rear camera", ("rear_camera", "camera", "back_camera")), ("Front camera", ("front_camera",))]),
    ("Sound", [("Sound", ("sound",))]),
    ("Battery", [("Battery", ("battery",)), ("Charging", ("charging",))]),
    ("Connectivity", [("Connectivity", ("connectivity",)), ("Sensors and inputs", ("data_inputs", "sensors"))]),
]


def nums(pattern, text, flags=re.I):
    return [float(x.replace(",", "")) for x in re.findall(pattern, text, flags)]


def num_or_int(x):
    return int(x) if x == int(x) else x


def build_key(c, released):
    """c = dict of cleaned values. Only fills a field when the text clearly contains it."""
    c = {a: re.sub(r"(?<=\d),(?=\d{3}\b)", "", b) for a, b in c.items()}
    k = {}
    d = c.get("display", "")
    m = re.search(r"(\d(?:\.\d{1,2})?)\s*(?:in\b|inch|\")", d, re.I)
    if m and 2 <= float(m.group(1)) <= 12:
        k["display_in"] = float(m.group(1))
    t = re.search(r"\b(LTPO[^,;]*?(?:AMOLED|OLED)|Dynamic AMOLED(?: 2X)?|Super AMOLED|Super Retina XDR OLED|AMOLED|OLED|Super Retina XDR|IPS LCD|IPS|LCD|TFT|Retina)\b", d, re.I)
    if t:
        k["display_type"] = re.sub(r"\s+", " ", t.group(1)).strip()
    hz = nums(r"(\d{2,3})\s*Hz", d)
    if hz:
        k["refresh_hz"] = int(max(hz))
    nits = nums(r"(\d{3,4})\s*nits", d)
    if nits:
        k["peak_nits"] = int(max(nits))
    chip = c.get("soc", "")
    if chip:
        k["chipset"] = re.split(r"[;,(]| and ", chip)[0].strip()[:60] or None
        if not k["chipset"]:
            k.pop("chipset")
    mem = c.get("memory", "")
    sto = c.get("storage", "")
    ram = [int(x) for x in nums(r"(\d{1,2})\s*GB", mem)] + ([int(x) for x in nums(r"(\d{1,2})\s*GB\s*RAM", sto)] if not mem else [])
    if ram:
        k["ram_gb"] = sorted(set(ram))[:6]
    st = []
    for val, unit in re.findall(r"(\d{1,4})\s*(GB|TB)", sto or mem):
        v = int(val) * (1024 if unit.upper() == "TB" else 1)
        if v >= 4 and not (unit.upper() == "GB" and int(val) in k.get("ram_gb", []) and v <= 24 and not sto):
            st.append(v)
    if st:
        k["storage_gb"] = sorted(set(st))[:6]
    rc = c.get("rear", "")
    mps = [float(x) for x in re.findall(r"(\d{1,3}(?:\.\d+)?)\s*MP", rc, re.I)]
    if mps:
        k["main_mp"] = num_or_int(mps[0])
        k["cameras"] = min(len(mps), 5)
        k["ois"] = bool(re.search(r"\bOIS\b|optical image stabili", rc, re.I))
        k["telephoto"] = bool(re.search(r"telephoto|periscope", rc, re.I))
        v = re.search(r"\b(8K|4K|1080p|720p)\s*(?:@|at)?\s*(\d{2,3})?\s*(?:fps)?", rc, re.I)
        if v:
            k["video"] = ("%s@%sfps" % (v.group(1), v.group(2))) if v.group(2) else v.group(1)
    fc = re.findall(r"(\d{1,3}(?:\.\d+)?)\s*MP", c.get("front", ""), re.I)
    if fc:
        k["front_mp"] = num_or_int(float(fc[0]))
    bt = c.get("battery", "")
    mah = nums(r"(\d{3,5})\s*mAh", bt)
    if mah:
        k["battery_mah"] = int(mah[0])
    ch = c.get("charging", "") + " " + bt
    wl = re.search(r"(\d{1,3}(?:\.\d+)?)\s*W[^,;]{0,40}wireless|wireless[^,;]{0,40}?(\d{1,3}(?:\.\d+)?)\s*W", ch, re.I)
    if wl:
        k["wireless_w"] = num_or_int(float(wl.group(1) or wl.group(2)))
    wired = [float(x) for x in re.findall(r"(\d{1,3}(?:\.\d+)?)\s*W\b(?![^,;]{0,40}wireless)", re.sub(r"wireless[^,;]*", "", c.get("charging", ""), flags=re.I))]
    if wired:
        k["wired_w"] = num_or_int(max(wired))
    osn = re.search(r"(Android\s*\d+(?:\.\d+)?|iOS\s*\d+(?:\.\d+)?|iPadOS\s*\d+|HarmonyOS\s*[\d.]*|Windows Phone\s*[\d.]*|Symbian[^,;]*|KaiOS[^,;]*)", c.get("os", ""), re.I)
    if osn:
        k["os"] = osn.group(1).strip()
    nets = c.get("networks", "") + " " + c.get("connectivity", "")
    if nets.strip():
        if re.search(r"\b5G\b", nets):
            k["five_g"] = True
        elif re.search(r"\b4G\b|LTE|3G|HSPA|GSM", nets):
            k["five_g"] = False
        k["nfc"] = bool(re.search(r"\bNFC\b", nets)) if c.get("connectivity") else None
        if k["nfc"] is None:
            k.pop("nfc")
        wf = re.search(r"Wi-?Fi\s*(7|6E|6|5|4)", nets, re.I)
        if wf:
            k["wifi"] = "Wi-Fi " + wf.group(1).upper()
        if re.search(r"USB[- ]?(?:Type[- ]?)?C", nets, re.I):
            k["usb"] = "USB-C"
        if re.search(r"e-?SIM", nets + " " + c.get("sim", ""), re.I):
            k["esim"] = True
        if re.search(r"dual[- ]?SIM|dual SIM", nets + " " + c.get("sim", "") + " " + c.get("other", ""), re.I):
            k["dual_sim"] = True
    ip = re.search(r"\bIP\s?(\d{2}[A-Z]?)\b", c.get("water", "") + " " + c.get("other", ""), re.I)
    if ip:
        k["ip"] = "IP" + ip.group(1).upper()
    wg = re.search(r"(\d{2,4}(?:\.\d+)?)\s*g\b", c.get("weight", ""))
    if wg:
        k["weight_g"] = num_or_int(float(wg.group(1)))
    dims = re.findall(r"(\d{1,3}(?:\.\d+)?)\s*mm", c.get("dimensions", ""))
    if len(dims) >= 3:
        k["thickness_mm"] = num_or_int(float(dims[2]))
    if released and re.match(r"\d{4}", released):
        k["year"] = int(released[:4])
    return {a: b for a, b in k.items() if b is not None}


BRAND_FIX = {"samsung electronics": "Samsung", "apple inc": "Apple", "google": "Google", "google llc": "Google", "huawei technologies": "Huawei", "hmd global": "HMD",
             "hmd": "HMD", "motorola mobility": "Motorola", "xiaomi corporation": "Xiaomi", "xiaomi": "Xiaomi", "sony mobile": "Sony", "sony": "Sony",
             "lg electronics": "LG", "htc corporation": "HTC", "oneplus": "OnePlus", "nothing technology": "Nothing", "realme": "Realme", "oppo": "Oppo", "vivo": "Vivo",
             "nokia": "Nokia", "asus": "Asus", "blackberry limited": "BlackBerry", "research in motion": "BlackBerry", "tecno mobile": "Tecno", "infinix mobility": "Infinix"}
CORP = re.compile(r"\b(inc|ltd|llc|corp|corporation|co|company|limited|electronics|mobile|communications|technologies|technology|group|international|holdings)\b\.?", re.I)


def brand_of(manu, title):
    raw = clean(manu)
    raw = re.split(r"[,;/]|\band\b", raw)[0].strip() if raw else ""
    key = re.sub(r"[.,]", "", raw.lower()).strip()
    if key in BRAND_FIX:
        return BRAND_FIX[key]
    stripped = CORP.sub("", raw).strip(" .,-")
    if stripped and len(stripped) <= 24:
        return stripped
    return title.split()[0]


def parse_phone(title, text, revid):
    body = extract_infobox(text, TEMPLATES)
    if not body:
        return None, None
    p = split_params(body)
    if len(p) < 4:
        return None, None
    cleaned = {k: clean(v) for k, v in p.items()}
    c = {"display": pick(cleaned, "display", "screen"), "soc": pick(cleaned, "soc", "system_on_chip", "chipset"), "memory": pick(cleaned, "memory", "ram"),
         "storage": pick(cleaned, "storage", "internal_storage"), "rear": pick(cleaned, "rear_camera", "camera", "back_camera"), "front": pick(cleaned, "front_camera"),
         "battery": pick(cleaned, "battery"), "charging": pick(cleaned, "charging"), "os": pick(cleaned, "os", "operating_system"), "networks": pick(cleaned, "networks", "network"),
         "connectivity": pick(cleaned, "connectivity"), "sim": pick(cleaned, "sim", "sim_card"), "water": pick(cleaned, "water_protection", "ingress_protection"),
         "other": pick(cleaned, "other"), "weight": pick(cleaned, "weight", "mass"), "dimensions": pick(cleaned, "dimensions", "size")}
    brand = brand_of(p.get("manufacturer", ""), title)
    name = re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()
    if name.lower().startswith(brand.lower() + " "):
        name = name[len(brand) + 1:].strip()
    elif name.lower() == brand.lower():
        return None, None
    rel_raw = pick(cleaned, "released", "released_date", "release_date")
    dm = re.search(r"(\d{4}-\d{2}-\d{2})", rel_raw) or re.search(r"(\d{4}-\d{2})\b", rel_raw)
    released = dm.group(1) if dm else ""
    if not released:
        d2 = re.search(r"([A-Z][a-z]+)\s+(\d{1,2}),\s*(\d{4})", rel_raw) or re.search(r"(\d{1,2})\s+([A-Z][a-z]+)\s+(\d{4})", rel_raw)
        if d2:
            try:
                g = d2.groups()
                mon, day, yr = (g[0], g[1], g[2]) if g[0].isalpha() else (g[1], g[0], g[2])
                released = datetime.strptime("%s %s %s" % (mon[:3], day, yr), "%b %d %Y").strftime("%Y-%m-%d")
            except ValueError:
                pass
    if not released:
        y = re.search(r"\b(19|20)\d{2}\b", rel_raw)
        released = y.group(0) if y else ""
    specs = {}
    for group, fields in GROUPS:
        rows = {}
        for label, names in fields:
            val = pick(cleaned, *names)
            if val and val.lower() not in ("n/a", "none", "unknown", "?"):
                rows[label] = val[:700]
        if rows:
            specs[group] = rows
    key = build_key(c, released)
    variants = len(set(re.findall(r"(\d(?:\.\d+)?)\s*(?:in\b|inch)", c["display"], re.I))) >= 2
    img = clean(p.get("image", ""))
    img = re.sub(r"^(?:File|Image):", "", img, flags=re.I).split("|")[0].strip()
    sparse = sum(1 for g in specs.values() for _ in g)
    if sparse < 4:
        return None, None
    ph = {
        "slug": slugify("%s %s" % (brand, name)), "brand": brand, "name": name, "status": "published",
        "announced": released[:10] if re.match(r"\d{4}-\d{2}-\d{2}", released) else "", "released": released[:10] if re.match(r"\d{4}-\d{2}-\d{2}", released) else "",
        "price": {}, "images": [], "specs": specs, "key": key,
        "sources": [{"name": "Wikipedia: %s" % title, "url": "https://en.wikipedia.org/wiki/%s" % urllib.parse.quote(title.replace(" ", "_"))}],
        "attribution": "Specification data adapted from the Wikipedia article \"%s\" (CC BY-SA 4.0), with changes: formatting cleaned and summarised." % title,
        "variants_note": variants, "wikipedia": {"title": title, "revid": revid}, "updated": date.today().isoformat(),
        "auto": True,
    }
    if released and not ph["released"]:
        ph["key"].setdefault("year", int(released[:4]))
    return ph, img


# ------------------------------------------------------------------ state + main
def load_state():
    st = read_json(STATE_PATH, None)
    if not isinstance(st, dict):
        st = {}
    st.setdefault("pages", {})      # title -> {"slug":..., "ts": iso}
    st.setdefault("skipped", {})    # title -> iso date (not a usable phone page right now)
    return st


def main():
    st = load_state()
    now = datetime.now(timezone.utc)
    all_titles = []
    for t in TEMPLATES:
        got = list_titles(t)
        print("template '%s': %d articles" % (t, len(got)))
        all_titles += got
    all_titles = sorted(set(all_titles))
    if not all_titles:
        print("ERROR: no phone articles found. Check PHONE_TEMPLATES / Wikipedia API access.")
        return 1
    stale_before = (now - timedelta(days=REFRESH_DAYS)).isoformat()
    new = [t for t in all_titles if t not in st["pages"] and t not in st["skipped"]]
    refresh = sorted([t for t in all_titles if t in st["pages"] and st["pages"][t]["ts"] < stale_before], key=lambda t: st["pages"][t]["ts"])
    retry = [t for t in all_titles if t in st["skipped"] and st["skipped"][t] < stale_before[:10]]
    todo = (new + refresh + retry)[:MAX_PER_RUN]
    print("articles: %d | new: %d | to refresh: %d | this run: %d" % (len(all_titles), len(new), len(refresh), len(todo)))
    os.makedirs(DATA_DIR, exist_ok=True)
    added = updated = skipped = 0
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        try:
            pages = fetch_pages(chunk)
        except RuntimeError as e:
            print("batch failed, will retry next run:", e)
            continue
        parsed = []
        for pg in pages:
            ph, img = parse_phone(pg["title"], pg["text"], pg["revid"])
            if ph is None:
                st["skipped"][pg["title"]] = date.today().isoformat()
                skipped += 1
                continue
            parsed.append((pg["title"], ph, img))
        imgs = {}
        wanted = sorted({img for _, _, img in parsed if img})
        if wanted:
            try:
                imgs = fetch_images(wanted)
            except RuntimeError as e:
                print("image lookup failed (pages still saved without images):", e)
        for title, ph, img in parsed:
            if img and img.replace("_", " ") in imgs:
                im = dict(imgs[img.replace("_", " ")])
                im["alt"] = "%s %s" % (ph["brand"], ph["name"])
                ph["images"] = [im]
            path = os.path.join(DATA_DIR, ph["slug"] + ".json")
            existed = os.path.exists(path)
            old = read_json(path, None) if existed else None
            if old and not old.get("auto"):
                print("keeping hand-edited file:", ph["slug"])     # never overwrite something the owner wrote
                st["pages"][title] = {"slug": ph["slug"], "ts": now.isoformat()}
                continue
            if old and old.get("review"):
                ph["review"] = old["review"]
            if old and old.get("price"):
                ph["price"] = old["price"]
            write_json(path, ph)
            st["pages"][title] = {"slug": ph["slug"], "ts": now.isoformat()}
            st["skipped"].pop(title, None)
            updated += 1 if existed else 0
            added += 0 if existed else 1
        if (i // BATCH) % 5 == 0:
            write_json(STATE_PATH, st)
            print("  progress: %d/%d" % (min(i + BATCH, len(todo)), len(todo)))
    write_json(STATE_PATH, st)
    print("Done. added %d, refreshed %d, skipped (not a usable spec page) %d." % (added, updated, skipped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
