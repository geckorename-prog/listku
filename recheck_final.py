#!/usr/bin/env python3
"""Re-check final: channel mati dari run terakhir, cek ulang 3x dengan UA playlist asli."""
import sys, time, re
sys.path.insert(0, ".")
from check_streams_full import check

# Baca playlist, map URL -> (name, ua, referrer)
with open("playlist.m3u") as f:
    lines = f.readlines()
chans = {}
i = 0
while i < len(lines):
    line = lines[i].strip()
    if line.startswith("#EXTINF"):
        name_m = re.search(r",(.*?)$", line)
        name = name_m.group(1).strip() if name_m else "?"
        i += 1
        ua, ref, url = "", "", ""
        while i < len(lines):
            l = lines[i].strip()
            if l.startswith("#EXTVLCOPT:http-user-agent="):
                ua = l.split("=", 1)[1]
            elif l.startswith("#EXTVLCOPT:http-referrer="):
                ref = l.split("=", 1)[1]
            elif l.startswith("http"):
                url = l
                break
            i += 1
        if url:
            chans[url] = (name, ua, ref)
    i += 1

with open("dead_channels_full.txt") as f:
    dead = [l.strip().split("|", 4) for l in f if l.strip()]

print(f"Re-check {len(dead)} channel mati, 3 attempt per channel, serial...")
still_dead = []
for name, group, status, detail, url in dead:
    n, ua, ref = chans.get(url, (name, "", ""))
    ch = {"url": url, "ua": ua, "referrer": ref}
    verdict = "MATI"
    res = {"status": "?"}
    for attempt in range(3):
        res = check(ch)
        if res["status"] == "Hidup":
            verdict = "HIDUP"
            break
        time.sleep(4)
    print(f"  {name:<36} {verdict} ({res['status']})", flush=True)
    if verdict == "MATI":
        still_dead.append((name, group, url))

print(f"\n=== FINAL: {len(still_dead)} channel benar-benar mati ===")
with open("final_dead.txt", "w") as f:
    for name, group, url in still_dead:
        print(f"MATI FINAL: {name} ({group}) — {url}")
        f.write(f"{name}|{group}|{url}\n")
