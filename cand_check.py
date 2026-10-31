#!/usr/bin/env python3
"""Uji kandidat channel dari JSON tvgarden/famelack (multi-URL per channel).

Pakai: python3 cand_check.py sports.json [--all]
  default : hanya URL dari domain daftar-putih (lihat WHITELIST)
  --all   : uji semua URL (termasuk domain tak dikenal) — hanya untuk laporan

Aturan teknis (jangan diubah, sudah ketemu lewat banyak kegagalan):
- manifest wajib `--compressed` (banyak CDN gzip) dan `-L` (redirect).
- join URL relatif pakai url_effective SETELAH redirect, bukan URL asli.
- segmen diuji dengan `-o /dev/null -w %{http_code}` (biner, jangan didekode).
- kalau segmen pertama gagal, coba segmen TERAKHIR (DVR/rolling window).
- DASH (.mpd / <MPD) TIDAK diuji — playlist target hanya HLS.
"""
import json, re, subprocess, sys, concurrent.futures as cf
from urllib.parse import urljoin, urlparse

UA = "Mozilla/5.0 (Linux; Android 16)"

WHITELIST = (
    "cloudfront.net", "akamaized.net", "akamaized.com", "akamai.net", "lldns.net",
    "azionedge.net", "streamlock.net", "uplynk.com",
    "amagi.tv", "tubi.video", "frequency.stream", "klowdtv.com", "samsung.wurl.com",
    "plex.tv", "mangomolo.com", "mgmlcdn.com", "spacetoongo.com",
    "boldmss.com", "mediacdn.ru", "cdnvideo.ru", "klicgo.net",
    "staratv.id", "carubantv.id", "shift.tv", "malimarcdn.com",
    "dens.tv", "tvri.go.id", "ebs.co.kr", "daaiplus.com", "pbs.org",
    "vos360.video", "ors.at", "city.bg", "ktv.go.kr",
    # disetujui Nanda Okt 2026 (hasil uji "grup A" kategori sports)
    "brightcove.com", "zype.com", "wowza.com", "rocketcdn.com", "cdn77.org",
    "streamhoster.com", "streamup.eu", "3catdirectes.cat", "live.mnb.mn",
    "tjktv-live.tjk.org", "vtvgolive-ott3.vtvdigital.vn", "tvr-sport.lg.mncdn.com",
    "webtvstream.bhtelecom.ba", "africa24.vedge.infomaniak.com",
    "qazsporttv-stream.qazcdn.com", "mts1.iptv-playoutcenter.de", "antik.sk",
    "media1.skifnet.by", "ngtrk.dc.beltelecom.by", "ercdn.net", "yayin.com.tr",
    "transmit.live", "nbcuni.com", "tubi.io", "mediatailor.us-west-2.amazonaws.com",
)
BANNED = (
    "bozztv.com", "samcast.com.br", "voxtvhd.com.br", "onnethn.com", "paroledivita.org",
    "catcast.tv", "shidurlive.com", "foxkidstv.be",
    "freem3u.xyz", "x1colegal.com", "hopslan.com", "alpaca.t62a.com", "bitred.cl",
    "stream.ads.ottera.tv", "otteravision.com", "getpublica.com",
    "smartplaytv.in", "wracanal10.com", "mjunoon.tv", "pishow.tv", "fasttvcdn.com",
    "cinerama.uz", "manasat.com", "freetv.fun",
)
TOKENY = re.compile(r"[?&](session|token|network_id|vid|bpkio_serviceid)=", re.I)


def curl(args, timeout=25):
    try:
        r = subprocess.run(["curl", "-sS", "-L", "--compressed", "--max-time", str(timeout),
                            "-A", UA, "-w", "\n%{http_code}|%{url_effective}"] + args,
                           capture_output=True, timeout=timeout + 5)
        out = r.stdout.decode("utf-8", "replace")
        body, _, tail = out.rpartition("\n")
        code, _, eff = tail.partition("|")
        return code.strip(), eff.strip(), body
    except Exception as e:
        return "000", "", f"ERR {type(e).__name__}"


def seg_ok(url, timeout=15):
    try:
        r = subprocess.run(["curl", "-sS", "-L", "--max-time", str(timeout), "-r", "0-4096",
                            "-o", "/dev/null", "-w", "%{http_code}", "-A", UA, url],
                           capture_output=True, timeout=timeout + 5)
        return r.stdout.decode().strip()
    except Exception:
        return "000"


def check(url):
    code, eff, body = curl([url])
    if code == "000":
        return False, "manifest 000"
    low = body.lower()
    if "channel blocked" in low or len(body) < 20:
        return False, f"manifest {code} body kosong/blocked"
    if "<mpd" in low:
        return False, "DASH (bukan HLS)"
    if "#extm3u" not in low:
        return False, f"manifest {code} bukan HLS"

    base = eff or url
    variants = []
    if "#EXT-X-STREAM-INF" in body:
        ls = body.split("\n")
        for i, l in enumerate(ls):
            if l.startswith("#EXT-X-STREAM-INF") and i + 1 < len(ls) and ls[i + 1].strip() and not ls[i + 1].startswith("#"):
                variants.append(urljoin(base, ls[i + 1].strip()))
    else:
        variants.append(base)

    for v in variants[:3]:
        if v is base:
            media, mbase = body, base
        else:
            c2, e2, media = curl([v])
            if c2 == "000" or "#extm3u" not in media.lower():
                continue
            if "#EXT-X-STREAM-INF" in media:  # nested master
                ls = media.split("\n")
                nested = None
                for i, l in enumerate(ls):
                    if l.startswith("#EXT-X-STREAM-INF") and i + 1 < len(ls) and ls[i + 1].strip() and not ls[i + 1].startswith("#"):
                        nested = urljoin(e2 or v, ls[i + 1].strip()); break
                if not nested:
                    continue
                c3, e3, media = curl([nested])
                if c3 == "000" or "#extm3u" not in media.lower():
                    continue
                mbase = e3 or nested
            else:
                mbase = e2 or v
        segs = [l.strip() for l in media.split("\n") if l.strip() and not l.startswith("#")]
        if not segs:
            continue
        for cand in (segs[0], segs[-1]):
            sc = seg_ok(urljoin(mbase, cand))
            if sc.startswith(("2", "3")):
                return True, f"manifest {code} seg {sc}"
    return False, f"manifest {code} segmen gagal"


def main():
    path = sys.argv[1]
    allmode = "--all" in sys.argv
    data = json.load(open(path))
    jobs = []
    for ch in data:
        for u in ch.get("stream_urls", []):
            dom = urlparse(u).netloc.lower()
            if any(b in dom for b in BANNED) or TOKENY.search(u):
                continue
            wl = any(w in dom for w in WHITELIST)
            if not wl and not allmode:
                continue
            jobs.append((ch, u, wl))
    print(f"kandidat diuji: {len(jobs)}", file=sys.stderr)
    res = []
    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        fut = {pool.submit(check, u): (ch, u, wl) for ch, u, wl in jobs}
        for f in cf.as_completed(fut):
            ch, u, wl = fut[f]
            ok, detail = f.result()
            res.append({"name": ch["name"], "country": ch.get("country", ""),
                        "nanoid": ch.get("nanoid", ""), "url": u,
                        "whitelisted": wl, "ok": ok, "detail": detail})

    live = [r for r in res if r["ok"]]
    dead = [r for r in res if not r["ok"]]
    print(f"=== HIDUP: {len(live)} | MATI: {len(dead)} ===")
    for r in sorted(live, key=lambda x: x["name"]):
        tag = "WL" if r["whitelisted"] else "??"
        print(f"LIVE [{tag}] {r['name']} ({r['country']}) | {r['detail']} | {r['url']}")
    print("\n--- mati ---")
    for r in sorted(dead, key=lambda x: x["name"]):
        print(f"DEAD {r['name']} ({r['country']}) | {r['detail']} | {r['url']}")
    json.dump(res, open("cand_result.json", "w"), indent=1)
    print("\nDetail: cand_result.json")


if __name__ == "__main__":
    main()
