#!/usr/bin/env python3
"""Filter hasil cand_check: ambil yang HIDUP, belum ada di playlist (URL/nama), dedup nama.

Pakai: python3 filter_baru.py playlist.m3u cand_result.json kandidat_baru.json
"""
import json
import re
import sys
from urllib.parse import urlparse

pl, res_file, dst = sys.argv[1], sys.argv[2], sys.argv[3]
pl_text = open(pl, encoding="utf-8").read()
pl_urls = set(re.findall(r"^https?://\S+$", pl_text, re.M))
pl_names = set(n.lower() for n in re.findall(r'tvg-name="([^"]*)"', pl_text))
pl_hosts = set(urlparse(u).netloc.lower() for u in pl_urls)

res = json.load(open(res_file, encoding="utf-8"))
live = [r for r in res if r.get("ok")]

# varian headend yang tidak perlu diuji: URL dengan parameter iklan platform
def noisy(u):
    return bool(re.search(r"[?&]ads\.", u))

new, skipped_dup_url, skipped_dup_name, seen = [], 0, 0, set()
for r in sorted(live, key=lambda x: x["name"].lower()):
    u, n = r["url"], r["name"]
    if u in pl_urls:
        skipped_dup_url += 1
        continue
    if n.lower() in pl_names or n.lower() in seen:
        skipped_dup_name += 1
        continue
    if noisy(u):
        skipped_dup_name += 1
        continue
    seen.add(n.lower())
    new.append({"name": n, "url": u, "country": r.get("country", ""),
                "nanoid": r.get("nanoid", ""), "host": urlparse(u).netloc.lower(),
                "host_dikenal": urlparse(u).netloc.lower() in pl_hosts})

json.dump(new, open(dst, "w"), ensure_ascii=False, indent=1)
print(f"hidup: {len(live)} | sudah ada (URL sama): {skipped_dup_url} | "
      f"skip nama/varian iklan: {skipped_dup_name} | BARU: {len(new)} -> {dst}")
for c in new:
    tag = "host sudah dipakai playlist" if c["host_dikenal"] else "HOST BARU"
    print(f"  {c['name']} ({c['country']}) [{tag}] {c['url'][:100]}")
