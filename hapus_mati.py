#!/usr/bin/env python3
"""Hapus channel mati (hasil dead_confirmed.txt) dari playlist.m3u.

Format input: name|group|url  ATAU name|group|status|detail|url
Aturan aman: header #EXTM3U WAJIB dipertahankan, blok berisi
#EXTINF + #EXTVLCOPT + URL + baris kosong dibuang utuh, dedup by URL.

Pakai: python3 hapus_mati.py playlist.m3u dead_confirmed.txt
"""
import os, sys, tempfile

pl = sys.argv[1] if len(sys.argv) > 1 else "playlist.m3u"
src = sys.argv[2] if len(sys.argv) > 2 else "dead_confirmed.txt"

targets = {}
for line in open(src):
    line = line.rstrip("\n")
    if not line.strip():
        continue
    p = line.split("|")
    if len(p) >= 5:
        targets[p[4]] = p[0]
    elif len(p) == 3:
        targets[p[2]] = p[0]

lines = open(pl).read().splitlines()
header = lines[0] if lines and lines[0].startswith("#EXTM3U") else None
if header is None:
    sys.exit("ABORT: baris pertama bukan #EXTM3U")

out = []
removed = []
i = 1 if header else 0
while i < len(lines):
    l = lines[i]
    if l.startswith("#EXTINF"):
        block = [l]
        j = i + 1
        url = None
        while j < len(lines):
            s = lines[j]
            if s.startswith("#EXTINF"):
                break
            block.append(s)
            if s.startswith("http"):
                url = s.strip()
                j += 1
                break
            j += 1
        # buang ekor kosong berlebih dari blok, simpan sebagai pemisah
        if url in targets:
            removed.append((targets[url], url))
        else:
            while block and not block[-1].strip():
                block.pop()
            out.extend(block)
            out.append("")
        i = j
    else:
        i += 1

assert removed, "tidak ada channel yang cocok untuk dihapus"
text = header + "\n" + "\n".join(out).rstrip("\n") + "\n"
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(pl)), suffix=".tmp")
with os.fdopen(fd, "w") as f:
    f.write(text)
os.chmod(tmp, 0o644)
os.replace(tmp, pl)

print(f"dihapus {len(removed)} channel:")
for n, u in removed:
    print(f"  - {n} :: {u}")
print(f"sisa channel: {sum(1 for x in out if x.startswith('#EXTINF'))}")
print(f"header: {header[:40]}")
