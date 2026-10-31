#!/usr/bin/env python3
"""Cek kesehatan penuh sesuai aturan: HTTP 2xx/3xx + manifest HLS valid
(#EXTM3U + EXT-X-STREAM-INF/EXTINF) + segmen pertama terunduh (200/206).
Master playlist: turun ke variant pertama, lalu segmen pertamanya.
Segmen di-probe binary-safe (tidak didecode sebagai teks)."""
import re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin

playlist = sys.argv[1] if len(sys.argv) > 1 else "playlist.m3u"

with open(playlist) as f:
    lines = f.readlines()

channels = []
i = 0
while i < len(lines):
    line = lines[i].strip()
    if line.startswith("#EXTINF"):
        name_match = re.search(r",(.*?)$", line)
        group_match = re.search(r'group-title="([^"]*)"', line)
        name = name_match.group(1).strip() if name_match else "?"
        group = group_match.group(1).strip() if group_match else "?"
        i += 1
        ua = ""
        referrer = ""
        url = ""
        while i < len(lines):
            l = lines[i].strip()
            if l.startswith("#EXTVLCOPT:http-user-agent="):
                ua = l.split("=", 1)[1]
            elif l.startswith("#EXTVLCOPT:http-referrer="):
                referrer = l.split("=", 1)[1]
            elif l.startswith("http"):
                url = l
                break
            i += 1
        channels.append({"name": name, "group": group, "url": url, "ua": ua, "referrer": referrer})
    i += 1

def base_cmd(ua, referrer):
    cmd = []
    if ua:
        cmd += ["-A", ua]
    if referrer:
        cmd += ["-e", referrer]
    return cmd

def fetch_body(url, ua, referrer, max_time=15):
    """Ambil body manifest (bytes) + status code + URL efektif (setelah redirect)."""
    cmd = ["curl", "-sS", "-L", "--compressed", "--max-time", str(max_time),
           "-w", "\n__META__%{http_code}|%{url_effective}"] + base_cmd(ua, referrer) + [url]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=max_time + 5)
        out = r.stdout or b""
        if b"__META__" in out:
            body, meta = out.rsplit(b"__META__", 1)
            parts = meta.decode(errors="replace").strip().split("|")
            code = parts[0] if parts else "000"
            eff = parts[1] if len(parts) > 1 else url
            return code or "000", body, eff
        return "000", out, url
    except subprocess.TimeoutExpired:
        return "TIMEOUT", b"", url
    except Exception:
        return "000", b"", url

def probe(url, ua, referrer, max_time=15):
    """Tes segmen dengan range request, hanya ambil status code. Binary-safe."""
    cmd = ["curl", "-sS", "-L", "--max-time", str(max_time),
           "-o", "/dev/null", "-w", "%{http_code}",
           "-r", "0-2048"] + base_cmd(ua, referrer) + [url]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=max_time + 5)
        return (r.stdout or b"").decode(errors="replace").strip() or "000"
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception:
        return "000"

def first_noncomment(body):
    for l in body.decode(errors="replace").splitlines():
        l = l.strip()
        if l and not l.startswith("#"):
            return l
    return None

def last_noncomment(body):
    for l in reversed(body.decode(errors="replace").splitlines()):
        l = l.strip()
        if l and not l.startswith("#"):
            return l
    return None

def live(c):
    return c and c[0] in "23"

def fetch_with_retry(url, ua, referrer, max_time=15, tries=2, delay=3):
    """Fetch body dengan retry untuk kegagalan transien (000/TIMEOUT)."""
    last_code, last_body, last_eff = "000", b"", url
    for attempt in range(tries):
        code, body, eff = fetch_body(url, ua, referrer, max_time=max_time)
        if code not in ("000", "TIMEOUT"):
            return code, body, eff
        last_code, last_body, last_eff = code, body, eff
        if attempt < tries - 1:
            import time as _t
            _t.sleep(delay)
    return last_code, last_body, last_eff

def check(ch):
    ua, ref = ch["ua"], ch["referrer"]
    code, body, eff = fetch_with_retry(ch["url"], ua, ref)

    if not live(code):
        return {"status": f"Mati({code})", "detail": "manifest gagal"}

    if body.lstrip()[:4] == b"<MPD" or b"<MPD" in body[:2000]:
        return {"status": "DASH", "detail": "manifest DASH"}

    if b"#EXTM3U" not in body:
        return {"status": f"Mati({code})", "detail": "bukan HLS"}

    has_variant = b"#EXT-X-STREAM-INF" in body
    has_inf = b"#EXTINF" in body
    if not (has_variant or has_inf):
        return {"status": f"Mati({code})", "detail": "manifest kosong"}

    # Rantai master -> variant (bisa >1 level, mis. redirect geo Akamai)
    # Base URL untuk join relative = URL efektif setelah redirect, bukan URL asli
    vurl = eff
    vcode, vbody = code, body
    levels = 0
    while b"#EXT-X-STREAM-INF" in vbody and b"#EXTINF" not in vbody and levels < 3:
        variant = first_noncomment(vbody)
        if not variant:
            return {"status": "Mati(manifest)", "detail": "variant kosong"}
        vurl_raw = urljoin(vurl, variant)
        vcode, vbody, veff = fetch_body(vurl_raw, ua, ref, max_time=10)
        if not live(vcode):
            return {"status": "Mati(variant)", "detail": f"variant {vcode}"}
        vurl = veff
        levels += 1

    if b"#EXTINF" not in vbody:
        return {"status": "Mati(variant)", "detail": "variant bukan media"}

    seg = first_noncomment(vbody)
    seg_url = urljoin(vurl, seg) if seg else None

    if not seg_url:
        return {"status": "Mati(manifest)", "detail": "tanpa segmen"}

    scode = probe(seg_url, ua, ref, max_time=10)
    if scode in ("200", "206"):
        return {"status": "Hidup", "detail": "segmen OK"}

    # DVR/rolling window yang diurut dari TERTUA: segmen pertama sudah keluar
    # dari retensi (404) padahal live edge jalan. Coba segmen terakhir dulu
    # sebelum menyatakan mati (contoh: rt-rtd.rttv.com/dvr/...).
    last = last_noncomment(vbody)
    if last and last != seg:
        lurl = urljoin(vurl, last)
        lcode = probe(lurl, ua, ref, max_time=10)
        if lcode in ("200", "206"):
            return {"status": "Hidup", "detail": f"segmen akhir OK (DVR, awal {scode})"}

    return {"status": f"Mati(seg {scode})", "detail": "segmen gagal"}

def worker(idx_ch):
    idx, ch = idx_ch
    res = check(ch) if ch["url"] else {"status": "Mati(no-url)", "detail": "-"}
    ch.update(res)
    return ch

if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(worker, enumerate(channels)))

    print(f"Total channel: {len(results)}")
    print(f"{'No':<4} {'Status':<14} {'Nama':<35} {'Grup'}")
    print("-" * 95)
    for idx, r in enumerate(results, 1):
        print(f"{idx:<4} {r['status']:<14} {r['name'][:34]:<35} {r['group']}")

    ok = [r for r in results if r["status"] == "Hidup"]
    dash = [r for r in results if r["status"] == "DASH"]
    dead = [r for r in results if r["status"] not in ("Hidup", "DASH")]

    print(f"\nRingkasan: {len(ok)} hidup, {len(dash)} DASH (tidak diuji segmen), {len(dead)} mati dari {len(results)} channel")

    if dead:
        with open("dead_channels_full.txt", "w") as f:
            for d in dead:
                f.write(f"{d['name']}|{d['group']}|{d['status']}|{d['detail']}|{d['url']}\n")
        print("Daftar mati disimpan ke dead_channels_full.txt")

    print("\nPer grup:")
    groups = {}
    for r in results:
        g = groups.setdefault(r["group"], [0, 0, 0])
        if r["status"] == "Hidup":
            g[0] += 1
        elif r["status"] == "DASH":
            g[1] += 1
        else:
            g[2] += 1
    for g, (a, b, c) in sorted(groups.items()):
        print(f"  {g}: {a} hidup, {b} DASH, {c} mati")
