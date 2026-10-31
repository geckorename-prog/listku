#!/usr/bin/env python3
"""Cek kesehatan playlist TEGAS: semua channel x N percobaan, tanpa early-exit.

Aturan Nanda: FLAKY = BUANG. Channel yang tidak lolos N/N (mati maupun gagal
sebagian) masuk dead_confirmed.txt, siap untuk hapus_mati.py.
Kontrol (TVRI NASIONAL + Smotrim) diuji di awal DAN akhir run; kalau kontrol
gagal, jaringan bermasalah dan hasil run tidak sah.

Pakai: python strict_check.py [playlist.m3u] [percobaan]
Output: strict_report.txt, strict_flaky.txt, strict_dead.txt, dead_confirmed.txt
"""
import concurrent.futures as cf
import re
import sys
import time

from recheck_par import check_once, load_playlist_meta, UA_DEFAULT

WORKERS = 8
CONTROLS = ("TVRI NASIONAL", "Smotrim")


def parse_playlist(path):
    lines = open(path, encoding="utf-8").read().splitlines()
    out = []
    for i, l in enumerate(lines):
        if not l.startswith("#EXTINF"):
            continue
        name = re.search(r'tvg-name="([^"]*)"', l)
        name = name.group(1) if name else l.split(",")[-1].strip()
        grp = re.search(r'group-title="([^"]*)"', l)
        grp = grp.group(1) if grp else ""
        j = i + 1
        while j < len(lines) and lines[j].startswith("#"):
            j += 1
        if j < len(lines) and lines[j].startswith("http"):
            out.append((name, grp, lines[j].strip()))
    return out


def run(items, attempts, meta):
    def job(it):
        name, group, url = it
        ua, ref = meta.get(url, (None, None, None, None))[2:]
        passes = 0
        details = []
        for a in range(attempts):
            ok, detail = check_once(url, ua or UA_DEFAULT, ref)
            passes += ok
            details.append(f"coba{a + 1}: {'Hidup' if ok else 'Mati'}|{detail}")
            if a + 1 < attempts:
                time.sleep(1.5)
        return name, group, url, passes, details

    with cf.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        return list(pool.map(job, items))


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "playlist.m3u"
    attempts = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    meta = load_playlist_meta()
    items = parse_playlist(path)
    ctrl = [it for it in items if any(c.lower() in it[0].lower() for c in CONTROLS)]
    print(f"{len(items)} channel x {attempts} percobaan ({WORKERS} worker), "
          f"kontrol: {[c[0] for c in ctrl]}", flush=True)

    pre = run(ctrl, attempts, meta)
    if not ctrl or any(r[3] < attempts for r in pre):
        print("ABORT: kontrol gagal di awal run, jaringan bermasalah. Hasil tidak sah.", flush=True)
        for r in pre:
            print(f"  kontrol {r[0]}: {r[3]}/{attempts}", flush=True)
        sys.exit(2)
    print(f"kontrol awal lolos {sum(r[3] for r in pre)}/{len(ctrl) * attempts}", flush=True)

    results = run(items, attempts, meta)
    post = run(ctrl, attempts, meta)
    if any(r[3] < attempts for r in post):
        print("ABORT: kontrol gagal di akhir run. Hasil tidak sah, ulangi.", flush=True)
        sys.exit(2)
    print(f"kontrol akhir lolos {sum(r[3] for r in post)}/{len(ctrl) * attempts}", flush=True)

    healthy = [r for r in results if r[3] == attempts]
    flaky = [r for r in results if 0 < r[3] < attempts]
    dead = [r for r in results if r[3] == 0]

    with open("strict_report.txt", "w", encoding="utf-8") as fh:
        for name, group, url, passes, details in sorted(results, key=lambda x: (x[1], x[0])):
            fh.write(f"[{passes}/{attempts}] {name} ({group}) :: {url}\n")
            for d in details:
                fh.write(f"      {d}\n")
    for fname, rows in (("strict_flaky.txt", flaky), ("strict_dead.txt", dead)):
        with open(fname, "w", encoding="utf-8") as fh:
            for name, group, url, passes, _ in rows:
                fh.write(f"{name}|{group}|{passes}/{attempts}|{url}\n")
    with open("dead_confirmed.txt", "w", encoding="utf-8") as fh:
        for name, group, url, passes, _ in flaky + dead:
            fh.write(f"{name}|{group}|{url}\n")

    print(f"\nSEHAT {attempts}/{attempts} : {len(healthy)}", flush=True)
    print(f"FLAKY (dibuang)    : {len(flaky)}", flush=True)
    print(f"MATI  (dibuang)    : {len(dead)}", flush=True)
    for name, group, url, passes, _ in sorted(flaky + dead, key=lambda x: (x[1], x[0])):
        print(f"  - [{passes}/{attempts}] {name} ({group})", flush=True)
    print("\nDetail: strict_report.txt | hapus: dead_confirmed.txt", flush=True)


if __name__ == "__main__":
    main()
