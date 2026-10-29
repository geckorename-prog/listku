#!/usr/bin/env python3
"""Re-check channel yang mati dengan retry agresif, 2 putaran.
Channel yang gagal di KEDUA putaran = benar-benar mati."""
import sys
sys.path.insert(0, ".")
from check_streams_full import fetch_with_retry, check, live, fetch_body
import time

with open("dead_channels_full.txt") as f:
    dead = [l.strip().split("|", 4) for l in f if l.strip()]

# url -> info
urls = {}
for name, group, status, detail, url in dead:
    urls[url] = (name, group)

def recheck(url, tries=3, delay=5):
    """Cek ulang: manifest + segmen dengan retry 3x."""
    ch = {"url": url, "ua": "", "referrer": ""}
    last = {"status": "Mati(?)", "detail": "-"}
    for i in range(tries):
        res = check(ch)
        if res["status"] == "Hidup":
            return "Hidup", res["detail"]
        last = res
        time.sleep(delay)
    return last["status"], last["detail"]

print(f"Re-check {len(urls)} channel mati, 2 putaran...")
final_dead = {}
for url, (name, group) in urls.items():
    s1, d1 = recheck(url)
    tag = "HIDUP" if s1 == "Hidup" else f"mati({s1})"
    print(f"  {name:<36} putaran1: {tag}", flush=True)
    if s1 != "Hidup":
        final_dead[url] = (name, group, s1)

# Putaran 2 hanya untuk yang masih mati
confirm = {}
for url, (name, group, s1) in final_dead.items():
    s2, d2 = recheck(url, tries=2, delay=8)
    status = "MATI PERMANEN" if s2 != "Hidup" else "flaky (hidup di putaran 2)"
    confirm[url] = (name, group, s1, s2, status)
    print(f"  {name:<36} putaran2: {s2} -> {status}", flush=True)

print(f"\n=== VERDICT: {len(confirm)} kandidat mati permanen dari {len(urls)} ===")
with open("verified_dead.txt", "w") as f:
    for url, (name, group, s1, s2, st) in confirm.items():
        if st == "MATI PERMANEN":
            print(f"MATI: {name} ({group}) — {s1}/{s2} — {url}")
            f.write(f"{name}|{group}|{url}\n")
    print("Tersimpan ke verified_dead.txt")
