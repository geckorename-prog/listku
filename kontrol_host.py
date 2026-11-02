#!/usr/bin/env python3
"""Pilih kontrol tambahan: channel SEHAT (3/3 di strict_report) yang berbagi host/CDN
dengan kandidat buang. Dipakai sebelum uji serial berkontrol.

Pakai: python3 kontrol_host.py playlist.m3u dead_confirmed.txt kontrol_host.txt
"""
import re
import sys

KEYS = {
    "telvue.com": "telvue",
    "5c2974786200d.streamlock.net": "streamlock-5c29",
    "streamlock.net": "streamlock",
    "iptv-playoutcenter.de": "playoutcenter",
    "live.aliman.id": "aliman",
    "rodjatv.com": "rodja",
    "siar.us": "siar.us",
    "akamaized.net": "akamaized",
    "cloudfront.net": "cloudfront",
    "vg-": "vglive",
}


def entries(path):
    lines = open(path, encoding="utf-8").read().splitlines()
    out, i = [], 0
    while i < len(lines):
        if lines[i].startswith("#EXTINF"):
            name = re.search(r'tvg-name="([^"]*)"', lines[i])
            name = name.group(1) if name else lines[i].split(",")[-1].strip()
            j = i + 1
            while j < len(lines) and lines[j].startswith("#"):
                j += 1
            if j < len(lines) and lines[j].startswith("http"):
                out.append((name, lines[j].strip()))
            i = j + 1
        else:
            i += 1
    return out


def healthy(path):
    ok = set()
    for line in open(path, encoding="utf-8"):
        m = re.match(r"\[(\d+)/(\d+)\] (.*?) \((.*?)\) :: (.*)", line.rstrip())
        if m and m.group(1) == m.group(2):
            ok.add(m.group(3))
    return ok


pl, cand_file, dst = sys.argv[1], sys.argv[2], sys.argv[3]
cand_urls = {l.rstrip().split("|")[-1] for l in open(cand_file, encoding="utf-8") if l.strip()}
cand_names = {l.split("|")[0] for l in open(cand_file, encoding="utf-8") if l.strip()}
cand_hosts = {}
for u in cand_urls:
    h = re.sub(r"^https?://", "", u).split("/")[0]
    cand_hosts[u] = h
ok_names = healthy("strict_report.txt")
ents = entries(pl)

picked = []
CAP = 2
for u, h in cand_hosts.items():
    for key in KEYS:
        if key in h or key in u:
            cnt = 0
            for n, nu in ents:
                if n in cand_names or nu in cand_urls:
                    continue
                if n not in ok_names:
                    continue
                hh = re.sub(r"^https?://", "", nu).split("/")[0]
                if (key in hh or key in nu) and cnt < CAP:
                    picked.append(n)
                    cnt += 1
            break

seen, rows = set(), []
for n in picked:
    if n in seen:
        continue
    seen.add(n)
    rows.append(n)
with open(dst, "w", encoding="utf-8") as fh:
    for n, u in ents:
        if n in seen:
            fh.write(f"{n}|KONTROL|{u}\n")
print(f"kontrol host sejenis: {len(rows)} -> {dst}")
for n in rows:
    print("  " + n)
