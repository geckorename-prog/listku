#!/usr/bin/env python3
"""Rapatkan group-title jadi sedikit grup, tanpa menyentuh entri lain.

Hanya atribut group-title pada baris #EXTINF yang diubah. Semua grup lama harus
ada di MAP; grup yang tidak dikenal = abort (supaya tidak ada channel yang
kehilangan kategori).

Pakai: python regroup.py playlist.m3u [--write]
"""
import os
import re
import sys
import tempfile

MAP = {
    "TV Nasional": "TV Indonesia",
    "TVRI Daerah": "TV Indonesia",
    "TV Daerah": "TV Indonesia",
    "TV Indonesia": "TV Indonesia",
    "Hiburan": "Hiburan",
    "Movie": "Hiburan",
    "Komedi": "Hiburan",
    "Lifestyle": "Hiburan",
    "Anak": "Anak",
    "Animasi": "Anak",
    "Olahraga": "Olahraga",
    "Otomotif": "Olahraga",
    "Outdoor": "Olahraga",
    "Berita": "Berita",
    "World News": "Berita",
    "Business": "Berita",
    "Internasional": "Berita",
    "Edukasi": "Edukasi",
    "Education": "Edukasi",
    "Dokumenter": "Edukasi",
    "Culture": "Edukasi",
    "Musik": "Musik",
    "Music": "Musik",
}

pl = sys.argv[1] if len(sys.argv) > 1 else "playlist.m3u"
write = "--write" in sys.argv

lines = open(pl, encoding="utf-8").read().splitlines()
if not lines or not lines[0].startswith("#EXTM3U"):
    sys.exit("ABORT: baris pertama bukan #EXTM3U")

before, after, unknown = {}, {}, set()
out = []
for line in lines:
    if line.startswith("#EXTINF"):
        m = re.search(r'group-title="([^"]*)"', line)
        grp = m.group(1) if m else ""
        before[grp] = before.get(grp, 0) + 1
        new = MAP.get(grp)
        if new is None:
            unknown.add(grp)
        else:
            line = line.replace(f'group-title="{grp}"', f'group-title="{new}"', 1)
            after[new] = after.get(new, 0) + 1
    out.append(line)

if unknown:
    sys.exit(f"ABORT: grup belum dipetakan: {sorted(unknown)}")

print(f"grup: {len(before)} -> {len(after)}")
for g, n in sorted(after.items(), key=lambda x: -x[1]):
    src = [f"{k} {v}" for k, v in sorted(before.items()) if MAP[k] == g]
    print(f"  {g:14} {n:4}  <- {', '.join(src)}")

if not write:
    print("\ndry-run, tidak menulis. Tambah --write untuk menerapkan.")
    sys.exit(0)

fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(pl)), suffix=".tmp")
with os.fdopen(fd, "w", encoding="utf-8") as f:
    f.write("\n".join(out).rstrip("\n") + "\n")
os.chmod(tmp, 0o644)
os.replace(tmp, pl)
assert open(pl, encoding="utf-8").readline().startswith("#EXTM3U")
print(f"\nditulis: {pl} ({sum(after.values())} channel, header utuh)")
