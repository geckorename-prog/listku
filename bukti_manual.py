#!/usr/bin/env python3
"""Bukti manual terakhir: 3x curl manifest per channel (UA+referrer asli playlist),
cetak kode HTTP + potongan body. Pakai: python3 bukti_manual.py daftar.txt
"""
import re
import subprocess
import sys
import time

from recheck_par import load_playlist_meta, UA_DEFAULT


def probe(url, ua, ref):
    cmd = ["curl", "-sS", "-L", "--compressed", "--max-time", "20", "-A", ua or UA_DEFAULT,
           "-o", "-", "-w", "\n__CODE__%{http_code}"]
    if ref:
        cmd += ["-e", ref]
    out = subprocess.run(cmd + [url], capture_output=True)
    try:
        body = out.stdout.decode("utf-8", "replace")
    except Exception:
        body = ""
    parts = body.rsplit("__CODE__", 1)
    code = parts[1].strip() if len(parts) == 2 else "?"
    head = re.sub(r"\s+", " ", parts[0][:70])
    return code, head


meta = load_playlist_meta()
for line in open(sys.argv[1], encoding="utf-8"):
    p = line.rstrip("\n").split("|")
    if len(p) < 3:
        continue
    name, url = p[0], p[-1]
    m = meta.get(url, (name, "", None, None))
    ua, ref = m[2], m[3]
    print(f"\n== {name} :: {url}\n   UA={ua} REF={ref}")
    for a in range(1, 4):
        code, head = probe(url, ua, ref)
        print(f"   coba{a}: HTTP {code} | {head}")
        time.sleep(2)
