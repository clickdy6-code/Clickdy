"""
Clickdy Phones - data + scoring library (standard library only).

Every phone is one JSON file in phones-data/. The site is generated from those files.
Nothing here is copied from another site: the "Clickdy Score" is our own transparent,
spec-based formula (it is NOT a lab test or hands-on review, and the pages say so).
"""
import math
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, read_json, slugify  # noqa: E402

DATA_DIR = os.path.join(ROOT, "phones-data")

SUB_NAMES = ["Performance", "Camera", "Display", "Battery", "Connectivity"]


# ------------------------------------------------------------------ helpers
def clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def interp(x, pts):
    """Piecewise-linear lookup. pts = [(x, y), ...] sorted by x. Returns None if x is None."""
    if x is None:
        return None
    if x <= pts[0][0]:
        return float(pts[0][1])
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return float(pts[-1][1])


def wavg(pairs):
    """Weighted average that ignores missing (None) components."""
    use = [(w, v) for w, v in pairs if v is not None]
    if not use:
        return None
    return sum(w * v for w, v in use) / sum(w for w, _ in use)


def num(v):
    try:
        if v is None or v == "" or isinstance(v, bool):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def as_list(v):
    if v is None or v == "":
        return []
    if isinstance(v, (list, tuple)):
        return [x for x in v if x is not None]
    return [v]


def fmt_num(v):
    v = num(v)
    if v is None:
        return ""
    return str(int(v)) if v == int(v) else ("%g" % v)


# ------------------------------------------------------------------ chipset tiers (editable estimates)
# Order matters: most specific first. The number is an *estimated performance tier* out of 100,
# based on the chip's generation and class. It is not a benchmark result.
CHIPSET_RULES = [
    (r"a19 pro", 99), (r"\ba19\b", 97), (r"a18 pro", 96), (r"\ba18\b", 93), (r"a17 pro", 92), (r"\ba16\b", 88),
    (r"\ba15\b", 84), (r"\ba14\b", 78), (r"\ba13\b", 72), (r"\ba12\b", 66),
    (r"snapdragon 8 elite gen ?5|snapdragon 8 elite 2", 100), (r"snapdragon 8 elite", 98),
    (r"snapdragon 8 gen ?3", 94), (r"snapdragon 8 gen ?2", 90), (r"snapdragon 8\+ gen ?1", 86), (r"snapdragon 8 gen ?1", 84),
    (r"snapdragon 7\+ gen ?3", 80), (r"snapdragon 7s? gen ?3", 74), (r"snapdragon 7\+ gen ?2", 76), (r"snapdragon 7s? gen ?2", 68),
    (r"snapdragon 7 gen ?1", 66), (r"snapdragon 6 gen ?4", 58), (r"snapdragon 6 gen ?3", 56), (r"snapdragon 6s? gen ?1", 52),
    (r"snapdragon 4 gen ?2", 40), (r"snapdragon 4 gen ?1", 36), (r"snapdragon 888", 78), (r"snapdragon 870", 74), (r"snapdragon 865", 72),
    (r"snapdragon 855", 66), (r"snapdragon 778g", 62), (r"snapdragon 765g?", 58), (r"snapdragon 750g", 52), (r"snapdragon 6\d\d", 50),
    (r"snapdragon 4\d\d", 36),
    (r"exynos 2500", 91), (r"exynos 2400", 88), (r"exynos 2200", 82), (r"exynos 2100", 78), (r"exynos 1580", 68), (r"exynos 1480", 64),
    (r"exynos 1380", 58), (r"exynos 1280", 52), (r"exynos 99\d\d|exynos 9820", 66),
    (r"tensor g5", 90), (r"tensor g4", 85), (r"tensor g3", 80), (r"tensor g2", 72), (r"tensor g1|google tensor$", 66),
    (r"kirin 90\d\d", 86), (r"kirin 9\d\d", 80), (r"kirin 8\d\d", 68),
    (r"helio g99", 50), (r"helio g9[0-8]", 46), (r"helio g\d\d", 40), (r"unisoc", 32), (r"\bt6\d\d\b", 32),
]


def chipset_score(name):
    if not name:
        return None
    n = str(name).lower()
    m = re.search(r"dimensity\s*(\d{3,4})", n)
    if m:
        d = int(m.group(1))
        for floor, sc in ((9500, 98), (9400, 96), (9300, 93), (9200, 90), (9000, 86), (8400, 80), (8300, 78), (8200, 75), (8100, 72),
                          (8000, 70), (7400, 68), (7300, 66), (7200, 64), (7050, 60), (7000, 58), (6300, 50), (6100, 48), (1000, 70), (900, 56), (800, 50), (700, 46)):
            if d >= floor:
                return float(sc)
        return 40.0
    for pat, sc in CHIPSET_RULES:
        if re.search(pat, n):
            return float(sc)
    m = re.search(r"\ba(\d{2})\b", n)
    if m and "apple" in n:
        return clamp(60 + (int(m.group(1)) - 12) * 5, 55, 99)
    return None


# ------------------------------------------------------------------ loading
def load_phones():
    phones, seen = [], set()
    if not os.path.isdir(DATA_DIR):
        return phones
    for fname in sorted(os.listdir(DATA_DIR)):
        if not fname.endswith(".json") or fname.startswith("_"):
            continue
        raw = read_json(os.path.join(DATA_DIR, fname), None)
        if not isinstance(raw, dict):
            print("skip (not valid JSON):", fname)
            continue
        if raw.get("status", "published") != "published":
            continue
        brand, name = str(raw.get("brand", "")).strip(), str(raw.get("name", "")).strip()
        if not brand or not name or not isinstance(raw.get("specs"), dict):
            print("skip (needs brand, name and specs):", fname)
            continue
        slug = slugify(raw.get("slug") or ("%s %s" % (brand, name)))
        if slug in seen or slug in ("brand", "brands", "best", "finder", "compare", "page"):
            print("skip (duplicate or reserved slug):", fname)
            continue
        seen.add(slug)
        key = raw.get("key") if isinstance(raw.get("key"), dict) else {}
        p = {
            "slug": slug, "brand": brand, "name": name, "full": "%s %s" % (brand, name),
            "brand_slug": slugify(brand),
            "announced": str(raw.get("announced") or "")[:10], "released": str(raw.get("released") or "")[:10],
            "price": raw.get("price") if isinstance(raw.get("price"), dict) else {},
            "images": [i for i in as_list(raw.get("images")) if isinstance(i, dict) and i.get("file")],
            "specs": raw["specs"], "key": key,
            "review": raw.get("review") if isinstance(raw.get("review"), dict) and raw["review"].get("body_html") else None,
            "sources": [s for s in as_list(raw.get("sources")) if isinstance(s, dict)],
            "updated": str(raw.get("updated") or "")[:10], "tagline": str(raw.get("tagline") or ""),
        }
        p["date"] = p["released"] or p["announced"]
        y = num(key.get("year"))
        p["year"] = int(y) if y else (int(p["date"][:4]) if re.match(r"\d{4}", p["date"]) else None)
        p["usd"] = num(p["price"].get("usd"))
        p["pkr"] = num(p["price"].get("pkr"))
        compute(p)
        phones.append(p)
    phones.sort(key=lambda p: (p["date"] or "0000", p["full"]), reverse=True)
    return phones


# ------------------------------------------------------------------ the Clickdy Score
def compute(p):
    k = p["key"]
    disp_in, refresh, nits = num(k.get("display_in")), num(k.get("refresh_hz")), num(k.get("peak_nits"))
    dtype = str(k.get("display_type") or "").lower()
    type_s = None if not dtype else (100 if re.search(r"oled|amoled|ltpo|dynamic", dtype) else 55 if re.search(r"ips|lcd|tft", dtype) else 62)
    display = wavg([(0.35, interp(nits, [(400, 15), (800, 40), (1500, 70), (2500, 92), (4000, 100)])),
                    (0.30, interp(refresh, [(60, 10), (90, 50), (120, 85), (144, 95), (165, 100)])),
                    (0.20, type_s),
                    (0.15, interp(disp_in, [(5.0, 40), (6.1, 65), (6.7, 85), (7.2, 92)]))])

    ram = max([num(x) or 0 for x in as_list(k.get("ram_gb"))] or [0]) or None
    sto = max([num(x) or 0 for x in as_list(k.get("storage_gb"))] or [0]) or None
    perf = wavg([(0.72, chipset_score(k.get("chipset"))),
                 (0.20, interp(ram, [(3, 20), (4, 32), (6, 50), (8, 66), (12, 86), (16, 96), (24, 100)])),
                 (0.08, interp(sto, [(32, 20), (64, 35), (128, 55), (256, 75), (512, 92), (1024, 100)]))])

    mp = num(k.get("main_mp"))
    camera = None
    if mp is not None:
        camera = interp(mp, [(8, 30), (13, 40), (50, 72), (108, 80), (200, 86)])
        cams = num(k.get("cameras")) or 0
        camera += {0: 0, 1: 0, 2: 4, 3: 9}.get(int(cams), 12)
        camera += 8 if k.get("ois") else 0
        camera += 6 if k.get("telephoto") else 0
        camera += 3 if (num(k.get("front_mp")) or 0) >= 32 else 0
        v = str(k.get("video") or "").lower()
        camera += 3 if "8k" in v else 2 if re.search(r"4k\s*@?\s*(60|120)", v) else 0
        camera = clamp(camera)

    mah, wired, wireless = num(k.get("battery_mah")), num(k.get("wired_w")), num(k.get("wireless_w"))
    battery = None
    if mah is not None or wired is not None:
        battery = wavg([(0.62, interp(mah, [(3000, 15), (4000, 45), (5000, 75), (6000, 92), (7000, 100)])),
                        (0.30, interp(wired, [(10, 15), (18, 30), (33, 50), (67, 80), (100, 95), (120, 100)]))])
        if battery is not None and wireless:
            battery = clamp(battery + 8)

    conn = None
    if any(k.get(x) is not None for x in ("five_g", "wifi", "nfc", "usb")):
        c = 38 if k.get("five_g") else 0
        wf = re.search(r"wi-?fi\s*(\d)", str(k.get("wifi") or ""), re.I)
        if wf:
            gen = int(wf.group(1))
            c += {7: 28, 6: 24 if re.search(r"6e", str(k.get("wifi")), re.I) else 20, 5: 12}.get(gen, 6)
        c += 12 if k.get("nfc") else 0
        c += 8 if re.search(r"usb[- ]?c|type-c", str(k.get("usb") or ""), re.I) else 0
        c += 6 if k.get("esim") else 0
        c += 4 if k.get("dual_sim") else 0
        conn = clamp(c)

    subs = [perf, camera, display, battery, conn]
    weights = [0.27, 0.23, 0.19, 0.21, 0.10]
    have = [(w, s) for w, s in zip(weights, subs) if s is not None]
    overall = round(sum(w * s for w, s in have) / sum(w for w, _ in have)) if len(have) >= 3 else None
    p["sub"] = [None if s is None else int(round(s)) for s in subs]
    p["score"] = overall
    p["value"] = None
    if overall is not None and p["usd"]:
        expected = 38 + 13 * math.log2(max(p["usd"], 60) / 150.0)
        p["value"] = int(round(clamp(50 + (overall - expected) * 1.5)))
    p["tags"] = best_for(p)
    p["pros"], p["cons"] = pros_cons(p)


def score_class(s):
    return "s-hi" if s is not None and s >= 85 else "s-mid" if s is not None and s >= 70 else "s-lo"


def best_for(p):
    k, sub, tags = p["key"], p["sub"], []
    perf, cam, disp, batt = sub[0] or 0, sub[1] or 0, sub[2] or 0, sub[3] or 0
    if perf >= 88 and (num(k.get("refresh_hz")) or 0) >= 120:
        tags.append("Gaming")
    if cam >= 82:
        tags.append("Photography")
    if batt >= 85:
        tags.append("Battery life")
    if (p["value"] or 0) >= 72:
        tags.append("Value for money")
    if disp_in(k) and disp_in(k) <= 6.3:
        tags.append("Compact")
    if disp_in(k) and disp_in(k) >= 6.8:
        tags.append("Big screen")
    return tags[:4]


def disp_in(k):
    return num(k.get("display_in"))


def pros_cons(p):
    k, pros, cons = p["key"], [], []
    mah, wired, wl = num(k.get("battery_mah")), num(k.get("wired_w")), num(k.get("wireless_w"))
    hz, nits, mp = num(k.get("refresh_hz")), num(k.get("peak_nits")), num(k.get("main_mp"))
    ram = max([num(x) or 0 for x in as_list(k.get("ram_gb"))] or [0])
    sto_min = min([num(x) or 0 for x in as_list(k.get("storage_gb"))] or [0])
    price = p["usd"]
    if mah and mah >= 5500:
        pros.append("Large %s mAh battery" % fmt_num(mah))
    if wired and wired >= 65:
        pros.append("Fast %sW wired charging" % fmt_num(wired))
    if wl and wl >= 15:
        pros.append("%sW wireless charging" % fmt_num(wl))
    if hz and hz >= 120:
        pros.append("Smooth %s Hz display" % fmt_num(hz))
    if nits and nits >= 2000:
        pros.append("Very bright display (%s nits peak)" % fmt_num(nits))
    if k.get("ip") and re.search(r"ip6[78]", str(k["ip"]), re.I):
        pros.append("%s water and dust resistance" % k["ip"])
    if ram >= 12:
        pros.append("Generous %s GB RAM option" % fmt_num(ram))
    if mp and mp >= 100:
        pros.append("High-resolution %s MP main camera" % fmt_num(mp))
    if k.get("telephoto"):
        pros.append("Dedicated telephoto camera")
    if k.get("ois"):
        pros.append("Optical image stabilization")
    if (p["sub"][0] or 0) >= 90:
        pros.append("Flagship-class chipset (%s)" % k.get("chipset"))
    if k.get("five_g") is False:
        cons.append("No 5G support")
    if k.get("nfc") is False:
        cons.append("No NFC for contactless payments")
    if hz and hz <= 60 and (price is None or price >= 200):
        cons.append("Only a 60 Hz display")
    if re.search(r"ips|lcd|tft", str(k.get("display_type") or ""), re.I) and price and price >= 450:
        cons.append("LCD display at a premium price")
    if mah and mah < 4200:
        cons.append("Battery capacity is on the small side (%s mAh)" % fmt_num(mah))
    if wired and wired < 25 and price and price >= 300:
        cons.append("Slow %sW wired charging for the price" % fmt_num(wired))
    if k.get("wireless_w") in (0, None) and price and price >= 800 and k.get("wireless_w") == 0:
        cons.append("No wireless charging")
    if k.get("ip") in ("", "None", "No") and price and price >= 400:
        cons.append("No official dust and water resistance rating")
    if sto_min and sto_min <= 64 and (price is None or price >= 200):
        cons.append("Base storage is only %s GB" % fmt_num(sto_min))
    if ram and ram <= 4:
        cons.append("Only %s GB RAM" % fmt_num(ram))
    wt, th = num(k.get("weight_g")), num(k.get("thickness_mm"))
    if wt and wt >= 220:
        cons.append("Heavy at %s g" % fmt_num(wt))
    if th and th >= 9:
        cons.append("Thicker than most phones (%s mm)" % fmt_num(th))
    if price and price >= 1000:
        cons.append("Premium price tag")
    if k.get("telephoto") is False and price and price >= 700:
        cons.append("No dedicated telephoto camera")
    return pros[:5], cons[:4]


# ------------------------------------------------------------------ text generation (all derived from the data)
def human_date(iso, with_day=False):
    m = re.match(r"(\d{4})-(\d{2})(?:-(\d{2}))?", iso or "")
    if not m:
        return ""
    months = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    y, mo, d = int(m.group(1)), int(m.group(2)), m.group(3)
    if not 1 <= mo <= 12:
        return str(y)
    return ("%s %d, %d" % (months[mo], int(d), y)) if (with_day and d) else ("%s %d" % (months[mo], y))


def money(p):
    parts = []
    if p["usd"]:
        parts.append("$%s" % format(int(p["usd"]), ","))
    if p["pkr"]:
        parts.append("Rs %s" % format(int(p["pkr"]), ","))
    return " / ".join(parts)


def chips(p):
    k, out = p["key"], []
    d = " ".join(x for x in (('%s"' % fmt_num(k.get("display_in"))) if disp_in(k) else "", k.get("display_type") or "",
                              ("%s Hz" % fmt_num(k.get("refresh_hz"))) if k.get("refresh_hz") else "") if x)
    if d:
        out.append(("Display", d))
    if k.get("chipset"):
        out.append(("Chipset", str(k["chipset"])))
    ram, sto = as_list(k.get("ram_gb")), as_list(k.get("storage_gb"))
    if ram or sto:
        out.append(("Memory", " / ".join(x for x in (("%s GB RAM" % fmt_num(max(ram, key=lambda v: num(v) or 0))) if ram else "",
                                                       ("%s GB" % fmt_num(max(sto, key=lambda v: num(v) or 0))) if sto else "") if x)))
    if k.get("main_mp"):
        out.append(("Camera", "%s MP main" % fmt_num(k["main_mp"])))
    if k.get("battery_mah"):
        out.append(("Battery", "%s mAh%s" % (fmt_num(k["battery_mah"]), (" · %sW" % fmt_num(k["wired_w"])) if k.get("wired_w") else "")))
    return out


def _join(parts):
    parts = [x for x in parts if x]
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def analysis(p):
    """Readable paragraphs built only from the phone's own data."""
    k, paras = p["key"], []
    when = human_date(p["announced"] or p["released"])
    first = "The %s was announced in %s." % (p["full"], when) if when else "The %s is a smartphone." % p["full"]
    if disp_in(k):
        first += " It has a %s-inch %s display%s%s." % (
            fmt_num(k["display_in"]), (k.get("display_type") or "").strip(),
            (" with a %s Hz refresh rate" % fmt_num(k["refresh_hz"])) if k.get("refresh_hz") else "",
            (" and up to %s nits of peak brightness" % fmt_num(k["peak_nits"])) if k.get("peak_nits") else "")
        first = first.replace("  ", " ").replace("display with", "display with")
    ram, sto = as_list(k.get("ram_gb")), as_list(k.get("storage_gb"))
    if k.get("chipset"):
        mem = []
        if ram:
            mem.append("up to %s GB of RAM" % fmt_num(max(ram, key=lambda v: num(v) or 0)))
        if sto:
            mem.append("up to %s GB of storage" % fmt_num(max(sto, key=lambda v: num(v) or 0)))
        first += " It is powered by the %s%s." % (k["chipset"], (", with " + _join(mem)) if mem else "")
    paras.append(first)

    cam = []
    if k.get("main_mp"):
        cam.append("a %s MP main camera%s" % (fmt_num(k["main_mp"]), " with optical stabilization" if k.get("ois") else ""))
    cams = num(k.get("cameras"))
    if cams and cams > 1:
        cam.append("%s rear cameras in total%s" % (fmt_num(cams), ", including a telephoto lens" if k.get("telephoto") else ""))
    if cam:
        c = "On the back, it offers " + _join(cam) + "."
        if k.get("front_mp"):
            c += " The front camera is %s MP." % fmt_num(k["front_mp"])
        if k.get("video"):
            c += " Video recording goes up to %s." % k["video"]
        paras.append(c)

    if k.get("battery_mah"):
        ch = []
        if k.get("wired_w"):
            ch.append("%sW wired" % fmt_num(k["wired_w"]))
        if num(k.get("wireless_w")):
            ch.append("%sW wireless" % fmt_num(k["wireless_w"]))
        paras.append("A %s mAh battery keeps it running%s." % (fmt_num(k["battery_mah"]), (", with " + _join(ch) + " charging") if ch else ""))

    body = []
    if k.get("ip"):
        body.append("has an %s rating" % k["ip"])
    if k.get("weight_g"):
        body.append("weighs %s g" % fmt_num(k["weight_g"]))
    if k.get("thickness_mm"):
        body.append("measures %s mm in thickness" % fmt_num(k["thickness_mm"]))
    if k.get("os"):
        body.append("runs %s" % k["os"])
    if body:
        paras.append("The phone " + _join(body) + ".")

    if p["score"] is not None:
        tier = "flagship-level" if p["score"] >= 85 else "upper mid-range" if p["score"] >= 72 else "mid-range" if p["score"] >= 58 else "entry-level"
        paras.append("On paper, its specifications place it in the %s group, with a Clickdy Score of %d out of 100. "
                     "This score is based only on the spec sheet, not on lab tests." % (tier, p["score"]))
    return paras


def faq(p):
    k, n, items = p["key"], p["name"], []
    if money(p):
        items.append(("What is the price of the %s?" % p["full"],
                      "The %s has a listed price of about %s%s. Prices vary by country, storage option and retailer." % (
                          p["full"], money(p), (" (%s)" % p["price"].get("note")) if p["price"].get("note") else "")))
    if k.get("chipset"):
        items.append(("What chipset does the %s use?" % p["full"], "The %s is powered by the %s." % (p["full"], k["chipset"])))
    if k.get("battery_mah"):
        a = "The %s has a %s mAh battery" % (p["full"], fmt_num(k["battery_mah"]))
        if k.get("wired_w"):
            a += " with %sW wired charging" % fmt_num(k["wired_w"])
        if k.get("wireless_w"):
            a += " and %sW wireless charging" % fmt_num(k["wireless_w"])
        items.append(("How big is the battery of the %s?" % p["full"], a + "."))
    if disp_in(k):
        items.append(("What display does the %s have?" % p["full"],
                      "It has a %s-inch %s display%s." % (fmt_num(k["display_in"]), k.get("display_type") or "", (" with a %s Hz refresh rate" % fmt_num(k["refresh_hz"])) if k.get("refresh_hz") else "")))
    if k.get("five_g") is not None:
        items.append(("Does the %s support 5G?" % p["full"], "Yes, the %s supports 5G." % p["full"] if k["five_g"] else "No, the %s does not support 5G." % p["full"]))
    if k.get("wireless_w") is not None:
        wl = num(k.get("wireless_w")) or 0
        items.append(("Does the %s have wireless charging?" % p["full"],
                      ("Yes, it supports %sW wireless charging." % fmt_num(wl)) if wl else "No, the %s does not list wireless charging." % p["full"]))
    if k.get("ip"):
        items.append(("Is the %s waterproof?" % p["full"], "The %s has an %s rating. Check the official guidance before swimming with any phone." % (p["full"], k["ip"])))
    d = human_date(p["released"], True) or human_date(p["announced"], True)
    if d:
        items.append(("When was the %s released?" % p["full"], "The %s %s %s." % (p["full"], "was released on" if p["released"] else "was announced on", d)))
    return items[:7]


def similar(p, phones, n=4):
    out = []
    for q in phones:
        if q["slug"] == p["slug"]:
            continue
        d = 0.0
        if p["score"] is not None and q["score"] is not None:
            d += abs(p["score"] - q["score"])
        if p["usd"] and q["usd"]:
            d += 14 * abs(math.log(p["usd"] / q["usd"]))
        d -= 3 if q["brand_slug"] == p["brand_slug"] else 0
        out.append((d, q))
    out.sort(key=lambda t: t[0])
    return [q for _, q in out[:n]]


# ------------------------------------------------------------------ "best of" lists
def best_lists(phones, year):
    def has(p, i):
        return p["sub"][i] is not None
    lists = [
        ("best-camera-phones", "Best Camera Phones in %d" % year, "The phones with the strongest camera hardware on paper, ranked by Clickdy camera score.",
         lambda p: has(p, 1), lambda p: (p["sub"][1], p["score"] or 0)),
        ("best-battery-phones", "Best Battery Life Phones in %d" % year, "Big batteries and fast charging, ranked by Clickdy battery score.",
         lambda p: has(p, 3), lambda p: (p["sub"][3], p["score"] or 0)),
        ("best-gaming-phones", "Best Gaming Phones in %d" % year, "Powerful chipsets and smooth high-refresh displays, ranked by performance score.",
         lambda p: has(p, 0) and (num(p["key"].get("refresh_hz")) or 0) >= 90, lambda p: (p["sub"][0], p["sub"][2] or 0)),
        ("best-flagship-phones", "Best Flagship Phones in %d" % year, "Top-tier phones ranked by overall Clickdy Score.",
         lambda p: p["score"] is not None and (p["score"] >= 82 or (p["usd"] or 0) >= 800), lambda p: (p["score"], 0)),
        ("best-big-screen-phones", "Best Big Screen Phones in %d" % year, "Phones with large displays of 6.7 inches or more.",
         lambda p: (disp_in(p["key"]) or 0) >= 6.7 and p["score"] is not None, lambda p: (p["score"], 0)),
        ("best-compact-phones", "Best Compact Phones in %d" % year, "Smaller phones with displays up to 6.3 inches.",
         lambda p: 0 < (disp_in(p["key"]) or 99) <= 6.3 and p["score"] is not None, lambda p: (p["score"], 0)),
    ]
    for cap in (200, 300, 400, 500, 700, 1000):
        lists.append(("best-phones-under-%d" % cap, "Best Phones Under $%d in %d" % (cap, year),
                      "The best-scoring phones with a listed price of $%d or less." % cap,
                      (lambda c: lambda p: p["usd"] is not None and p["usd"] <= c and p["score"] is not None)(cap), lambda p: (p["score"], p["value"] or 0)))
    lists.append(("best-value-phones", "Best Value Phones in %d" % year, "Phones that deliver the most for their price, ranked by Clickdy value score.",
                  lambda p: p["value"] is not None, lambda p: (p["value"], p["score"] or 0)))
    out = []
    for slug, title, desc, flt, keyf in lists:
        items = sorted([p for p in phones if flt(p)], key=keyf, reverse=True)[:10]
        if len(items) >= 3:
            out.append({"slug": slug, "title": title, "desc": desc, "items": items})
    return out
