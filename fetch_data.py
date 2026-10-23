import json, re, time, html
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

UA = {"User-Agent": "Mozilla/5.0 (compatible; DataBot/1.0)"}

FEEDS = [
 ("indonesia","Antara","https://www.antaranews.com/rss/terkini.xml"),
 ("dunia","BBC News","https://feeds.bbci.co.uk/news/world/rss.xml"),
 ("dunia","The Verge","https://www.theverge.com/rss/index.xml"),
 ("dunia","The Hacker News","https://feeds.feedburner.com/TheHackersNews"),
 ("indonesia","CNN Indonesia","https://www.cnnindonesia.com/nasional/rss"),
 ("dunia","Al Jazeera","https://www.aljazeera.com/xml/rss/all.xml"),
 ("dunia","TechCrunch","https://techcrunch.com/feed/"),
 ("dunia","BleepingComputer","https://www.bleepingcomputer.com/feed/"),
 ("indonesia","Detik","https://rss.detik.com/index.php/detikcom"),
 ("dunia","The Guardian","https://www.theguardian.com/world/rss"),
 ("indonesia","Antara Tekno","https://www.antaranews.com/rss/tekno.xml"),
 ("dunia","Krebs on Security","https://krebsonsecurity.com/feed/"),
 ("indonesia","Liputan6","https://feed.liputan6.com/rss/news"),
 ("dunia","Antara Dunia","https://www.antaranews.com/rss/dunia.xml"),
 ("dunia","Ars Technica","https://feeds.arstechnica.com/arstechnica/index"),
 ("dunia","SecurityWeek","https://feeds.feedburner.com/securityweek"),
 ("indonesia","Tempo","https://rss.tempo.co/nasional"),
 ("dunia","DW","https://rss.dw.com/xml/rss-en-all"),
 ("indonesia","Detik Inet","https://rss.detik.com/index.php/inet"),
 ("dunia","Dark Reading","https://www.darkreading.com/rss.xml"),
 ("indonesia","Republika","https://www.republika.co.id/rss"),
 ("dunia","CNN Indonesia Dunia","https://www.cnnindonesia.com/internasional/rss"),
 ("indonesia","CNN Indonesia Tekno","https://www.cnnindonesia.com/teknologi/rss"),
 ("indonesia","Suara","https://www.suara.com/rss/news"),
 ("dunia","France 24","https://www.france24.com/en/rss"),
 ("dunia","Detik Dunia","https://rss.detik.com/index.php/internasional"),
 ("dunia","Engadget","https://www.engadget.com/rss.xml"),
 ("indonesia","CNBC Indonesia","https://www.cnbcindonesia.com/news/rss"),
]
SYM = [("^JKSE","IHSG"),("BBCA.JK","BCA"),("BBRI.JK","BRI"),("BMRI.JK","Mandiri"),
 ("BBNI.JK","BNI"),("TLKM.JK","Telkom"),("ASII.JK","Astra"),("GOTO.JK","GoTo"),
 ("BREN.JK","Barito Renewables"),("AMMN.JK","Amman Mineral"),("UNVR.JK","Unilever"),
 ("ADRO.JK","Adaro"),("ANTM.JK","Antam")]

CAP, PER_CAT, KEEP_DAYS = 8, 60, 4

def get(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def clean(s):
    s = re.sub(r"<[^>]+>", " ", html.unescape(s or ""))
    return re.sub(r"\s+", " ", s).strip()

def parse_date(s):
    if not s: return None
    s = s.strip()
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try: d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception: return None
    if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)

def parse_feed(raw):
    root = ET.fromstring(raw)
    out = []
    for it in root.iter():
        tag = it.tag.split("}")[-1]
        if tag not in ("item", "entry"): continue
        f = {}
        link, img = "", ""
        for ch in it:
            n = ch.tag.split("}")[-1]
            if n == "link":
                link = ch.get("href") or (ch.text or "").strip() or link
            elif n in ("content", "thumbnail") and ch.get("url"):
                img = img or ch.get("url")
            elif n == "enclosure" and ch.get("url") and "image" in (ch.get("type") or "image"):
                img = img or ch.get("url")
            else:
                f.setdefault(n, ch.text or "")
        body = f.get("encoded") or f.get("content") or ""
        desc = f.get("description") or f.get("summary") or ""
        if not img:
            m = re.search(r'<img[^>]+src=["\']([^"\']+)', body + desc, re.I)
            img = m.group(1) if m else ""
        d = parse_date(f.get("pubDate") or f.get("published") or f.get("updated") or f.get("date"))
        t = clean(f.get("title"))
        if t and link and d:
            out.append({"t": t, "l": link, "d": d, "img": img, "x": clean(desc or body)[:300]})
    return out[:15]

def build_news():
    now = datetime.now(timezone.utc)
    items, ok = [], 0
    for c, s, u in FEEDS:
        try:
            got = parse_feed(get(u))
        except Exception as e:
            print("GAGAL", s, e); continue
        ok += 1
        got = [g for g in got if (now - g["d"]).days < KEEP_DAYS and g["d"] <= now + timedelta(hours=1)]
        got.sort(key=lambda g: g["d"], reverse=True)
        for g in got[:CAP]:
            items.append({**g, "c": c, "s": s})
    if ok == 0 or not items:
        return None
    items.sort(key=lambda g: g["d"], reverse=True)
    final = []
    for cat in ("dunia", "indonesia"):
        final += [i for i in items if i["c"] == cat][:PER_CAT]
    for i in final: i["d"] = i["d"].strftime("%Y-%m-%dT%H:%M:%SZ")
    wib = (now + timedelta(hours=7)).strftime("%Y-%m-%d")
    return {"day": wib, "ok": ok, "updated": int(time.time()), "items": final}

def quote(sym):
    err = None
    for host in ("query1", "query2"):
        try:
            u = f"https://{host}.finance.yahoo.com/v8/finance/chart/{sym}?range=1d&interval=1d"
            m = json.loads(get(u, 15))["chart"]["result"][0]["meta"]
            p = m["regularMarketPrice"]
            pv = m.get("chartPreviousClose") or m.get("previousClose")
            return p, ((p - pv) / pv * 100 if pv else None)
        except Exception as e:
            err = e
    print("GAGAL", sym, err)
    return None

def build_stocks():
    st = []
    for y, n in SYM:
        q = quote(y)
        if q:
            st.append({"k": y.replace(".JK", "").replace("^JKSE", "IHSG"), "n": n,
                       "p": q[0], "c": None if q[1] is None else round(q[1], 2)})
        time.sleep(0.5)
    return {"updated": int(time.time()), "stocks": st} if st else None

def save(name, data):
    if data is None:
        print("lewati", name, "(data kosong, berkas lama dipertahankan)"); return
    with open(name, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print("tersimpan", name)

if __name__ == "__main__":
    save("berita.json", build_news())
    save("saham.json", build_stocks())
