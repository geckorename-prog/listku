#!/usr/bin/env python3
"""Sisipkan kanal baru ke playlist.m3u di akhir blok grup yang sama.

Format entri mengikuti konvensi file: EXTINF (+tvg-name/group-title) -> EXTVLCOPT UA -> URL -> baris kosong.
Kalau grup belum ada, entri ditaruh di akhir berkas.
"""
import os
import sys
import tempfile

PLAYLIST = "playlist.m3u"
UA = "Mozilla/5.0 (Linux; Android 16)"

# name, group, url
NEW = [
    ("Sky News International", "World News", "https://linear901-oo-hls0-prd-gtm.delivery.skycdp.com/17501/sde-fast-skynews/master.m3u8"),
]


def block(name, group, url):
    return (f'#EXTINF:-1 tvg-name="{name}" group-title="{group}",{name}\n'
            f'#EXTVLCOPT:http-user-agent={UA}\n'
            f'{url}\n\n')


lines = open(PLAYLIST, encoding="utf-8").readlines()

# tolak kalau URL sudah ada (idempotent)
existing = set(l.split()[0] for l in lines if l.startswith("http"))
todo = [n for n in NEW if n[2] not in existing]
skip = [n for n in NEW if n[2] in existing]
if skip:
    print("sudah ada, dilewati:", ", ".join(n[0] for n in skip))
if not todo:
    print("tidak ada yang perlu ditambah")
    sys.exit(0)

# indeks entri: baris EXTINF -> (awal, akhir blok termasuk baris kosong)
entries = []  # (start_idx, end_idx, group)
i = 0
while i < len(lines):
    if lines[i].startswith("#EXTINF"):
        start = i
        j = i + 1
        while j < len(lines) and not lines[j].startswith("#EXTINF"):
            j += 1
        # mundurkan baris kosong di ekor blok supaya sisipan rapi
        end = j
        entries.append((start, end, lines[start]))
        i = j
    else:
        i += 1

ins = {}  # posisi insert -> daftar blok
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
os.replace(tmp, PLAYLIST)

print(f"disisipkan {len(todo)} kanal ke {PLAYLIST}")
