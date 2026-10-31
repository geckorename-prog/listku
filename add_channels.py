#!/usr/bin/env python3
"""Sisipkan kanal baru ke playlist.m3u di akhir blok grup-nya (idempotent by URL).

Pakai: python3 add_channels.py daftar.json
  daftar.json = [{"name": "...", "group": "Olahraga", "url": "https://..."}, ...]

Menolak jalan kalau baris pertama playlist bukan #EXTM3U.
"""
import json
import os
import re
import sys
import tempfile

PLAYLIST = "playlist.m3u"
UA = "Mozilla/5.0 (Linux; Android 16)"


def block(name, group, url):
    return (f'#EXTINF:-1 tvg-name="{name}" group-title="{group}",{name}\n'
            f'#EXTVLCOPT:http-user-agent={UA}\n'
            f'{url}\n\n')


src = sys.argv[1] if len(sys.argv) > 1 else "daftar.json"
NEW = [(c["name"], c["group"], c["url"]) for c in json.load(open(src, encoding="utf-8"))]

lines = open(PLAYLIST, encoding="utf-8").readlines()
if not lines or not lines[0].startswith("#EXTM3U"):
    sys.exit("ABORT: baris pertama bukan #EXTM3U")

existing = {l.split()[0] for l in lines if l.startswith("http")}
todo = [n for n in NEW if n[2] not in existing]
skip = [n for n in NEW if n[2] in existing]
if skip:
    print("sudah ada, dilewati:", ", ".join(n[0] for n in skip))
if not todo:
    print("tidak ada yang perlu ditambah")
    sys.exit(0)

entries = []  # (start_idx, end_idx, extinf_line)
i = 0
while i < len(lines):
    if lines[i].startswith("#EXTINF"):
        start = i
        j = i + 1
        while j < len(lines) and not lines[j].startswith("#EXTINF"):
            j += 1
        entries.append((start, j, lines[start]))
        i = j
    else:
        i += 1

ins = {}
for name, group, url in todo:
    anchor = None
    for start, end, extinf in entries:
        if f'group-title="{group}"' in extinf:
            anchor = end
    if anchor is None:
        anchor = len(lines)
    ins.setdefault(anchor, []).append(block(name, group, url))

out = []
for idx, line in enumerate(lines):
    if idx in ins:
        while out and out[-1].strip() == "":
            out.pop()
        for b in ins[idx]:
            out.append(b)
    out.append(line)
if len(lines) in ins:
    while out and out[-1].strip() == "":
        out.pop()
    for b in ins[len(lines)]:
        out.append(b)

if out and not out[-1].endswith("\n"):
    out[-1] += "\n"

d = os.path.dirname(os.path.abspath(PLAYLIST)) or "."
fd, tmp = tempfile.mkstemp(dir=d, prefix=".playlist-", suffix=".tmp")
with os.fdopen(fd, "w", encoding="utf-8") as f:
    f.writelines(out)
os.chmod(tmp, 0o644)
os.replace(tmp, PLAYLIST)

print(f"disisipkan {len(todo)} kanal ke {PLAYLIST}")
print("total channel:", sum(1 for l in out if l.startswith("#EXTINF")))
