#!/usr/bin/env python3
"""Verifikasi paralel kandidat mati: 3 percobaan per channel, 6 worker.

Lebih cepat daripada recheck_serial.py (yang serial + jeda 6s) tapi tetap
menghindari kesimpulan "mati" dari satu kali gagal. Definisi mati TEGAS:
gagal di SEMUA percobaan.

Pakai: python3 recheck_par.py dead_channels_full.txt [percobaan]
Output: recheck_par_result.txt, dead_confirmed_par.txt, dead_confirmed.txt

Catatan: import modul ini AMAN (main() dijaga `if __name__ == "__main__"`),
jadi fungsi check_once() bisa dipakai skrip lain tanpa menjalankan ulang scan.
"""
import concurrent.futures as cf
import re
import subprocess
import sys
import time
from urllib.parse import urljoin

PLAYLIST = "playlist.m3u"
UA_DEFAULT = "Mozilla/5.0 (Linux; Android 16)"
WORKERS = 6


def load_playlist_meta():
    """URL -> (name, group, ua, ref) dari playlist supaya UA/referrer asli dipakai."""
    lines = open(PLAYLIST, encoding="utf-8").read().splitlines()
    meta, i = {}, 0
    while i < len(lines):
        l = lines[i]
        if l.startswith("#EXTINF"):
            name = re.search(r'tvg-name="([^"]*)"', l)
            name = name.group(1) if name else l.split(",")[-1].strip()
            grp = re.search(r'group-title="([^"]*)"', l)
            grp = grp.group(1) if grp else ""
            ua, ref, j = None, None, i + 1
            while j < len(lines) and lines[j].startswith("#"):
                if lines[j].startswith("#EXTVLCOPT:http-user-agent="):
                    ua = lines[j].split("=", 1)[1]
                elif lines[j].startswith("#EXTVLCOPT:http-referrer="):
                    ref = lines[j].split("=", 1)[1]
                j += 1
            if j < len(lines):
                meta[lines[j].strip()] = (name, grp, ua, ref)
            i = j + 1
        else:
            i += 1
    return meta


def curl(args, timeout=20):
    try:
        r = subprocess.run(["curl", "-sS", "-L", "--compressed", "--max-time", str(timeout),
                            "-w", "\n%{http_code}|%{url_effective}"] + args,
                           capture_output=True, timeout=timeout + 6)
        out = r.stdout.decode("utf-8", "replace")
        body, _, tail = out.rpartition("\n")
        code, _, eff = tail.partition("|")
        return code.strip(), eff.strip(), body
    except Exception:
        return "000", "", ""


def seg_code(url, ua, ref, timeout=15):
    cmd = ["curl", "-sS", "-L", "--max-time", str(timeout), "-r", "0-4096", "-o", "/dev/null",
           "-w", "%{http_code}", "-A", ua]
    if ref:
        cmd += ["-e", ref]
    cmd.append(url)
    try:
        return subprocess.run(cmd, capture_output=True, timeout=timeout + 5).stdout.decode().strip()
    except Exception:
        return "000"


def check_once(url, ua=None, ref=None):
    """True kalau manifest valid dan ada segmen yang bisa diambil (200/206)."""
    ua = ua or UA_DEFAULT
    hdr = ["-A", ua]
    if ref:
        hdr += ["-e", ref]
    code, eff, body = curl(hdr + [url])
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
            c2, e2, media = curl(hdr + [v])
            if c2 == "000" or "#extm3u" not in media.lower():
                continue
            if "#EXT-X-STREAM-INF" in media:
                ls = media.split("\n")
                nested = None
                for i, l in enumerate(ls):
                    if l.startswith("#EXT-X-STREAM-INF") and i + 1 < len(ls) and ls[i + 1].strip() and not ls[i + 1].startswith("#"):
                        nested = urljoin(e2 or v, ls[i + 1].strip())
                        break
                if not nested:
                    continue
                c3, e3, media = curl(hdr + [nested])
                if c3 == "000" or "#extm3u" not in media.lower():
                    continue
                mbase = e3 or nested
            else:
                mbase = e2 or v
        segs = [l.strip() for l in media.split("\n") if l.strip() and not l.startswith("#")]
        if not segs:
            continue
        for cand in (segs[0], segs[-1]):
            sc = seg_code(urljoin(mbase, cand), ua, ref)
            if sc.startswith(("2", "3")):
                return True, f"manifest {code} seg {sc}"
    return False, f"manifest {code} segmen gagal"


def recheck(item, attempts, meta):
    name, group, url = item
    m = meta.get(url, (name, group, None, None))
    ua = m[2] or UA_DEFAULT
    ref = m[3]
    log = []
    for a in range(1, attempts + 1):
        ok, detail = check_once(url, ua, ref)
        log.append(f"coba{a}: {'Hidup' if ok else 'Mati'}|{detail}")
        if ok:
            return name, group, url, True, log
        if a < attempts:
            time.sleep(2 * a)
    return name, group, url, False, log


def main():
    fname = sys.argv[1] if len(sys.argv) > 1 else "dead_channels_full.txt"
    attempts = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    meta = load_playlist_meta()

    items = []
    for line in open(fname, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line.strip():
            continue
        p = line.split("|")
        if len(p) >= 5:
            items.append((p[0], p[1], p[4]))
        elif len(p) == 3:
            items.append((p[0], p[1], p[2]))

    print(f"Verifikasi paralel {len(items)} kandidat x {attempts} percobaan ({WORKERS} worker)...\n")
    results = []
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = [pool.submit(recheck, it, attempts, meta) for it in items]
        for f in cf.as_completed(futs):
            results.append(f.result())

    alive = [r for r in results if r[3]]
    dead = [r for r in results if not r[3]]

    with open("recheck_par_result.txt", "w", encoding="utf-8") as fh:
        for n, g, u, ok, log in sorted(results, key=lambda x: (not x[3], x[1], x[0])):
            fh.write(f"[{'HIDUP(batal hapus)' if ok else 'MATI(konsisten)'}] {n} ({g})\n")
            for l in log:
                fh.write(f"      {l}\n")

    for out in ("dead_confirmed_par.txt", "dead_confirmed.txt"):
        with open(out, "w", encoding="utf-8") as fh:
            for n, g, u, ok, log in dead:
                fh.write(f"{n}|{g}|{u}\n")

    print(f"HIDUP (flaky, jangan dihapus): {len(alive)}")
    print(f"MATI konsisten (aman dihapus) : {len(dead)}")
    for n, g, u, ok, log in sorted(dead, key=lambda x: x[0]):
        print(f"  - {n} ({g}) :: {u}")
    print("\nDetail: recheck_par_result.txt | daftar hapus: dead_confirmed.txt")


if __name__ == "__main__":
    main()
