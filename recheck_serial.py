#!/usr/bin/env python3
"""Recheck serial 3x untuk kandidat channel mati.

Aturan skill: drop massal / kegagalan di scan paralel bisa cuma gangguan jaringan
NAT64, jadi channel TIDAK boleh dihapus sebelum gagal konsisten 3/3 secara serial.

Pakai: python3 recheck_serial.py dead_channels_full.txt [tries]
Output: recheck_result.txt (TSV) + ringkasan di stdout.
"""
import sys, time
import check_streams_full as M

src = sys.argv[1] if len(sys.argv) > 1 else "dead_channels_full.txt"
tries = int(sys.argv[2]) if len(sys.argv) > 2 else 3
gap = 6

rows = []
with open(src) as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) >= 5:
            # format dead_channels_full.txt: name|group|status|detail|url
            rows.append({"name": p[0], "group": p[1], "url": p[4], "ua": "", "referrer": ""})
        elif len(p) == 3:
            # format ringkas: name|group|url
            rows.append({"name": p[0], "group": p[1], "url": p[2], "ua": "", "referrer": ""})

# ambil UA/referrer asli dari playlist supaya tes fair
ua_by_url = {}
with open("playlist.m3u") as f:
    cur_ua = ""
    for line in f:
        line = line.strip()
        if line.startswith("#EXTVLCOPT:http-user-agent="):
            cur_ua = line.split("=", 1)[1]
        elif line.startswith("http"):
            ua_by_url[line] = cur_ua
            cur_ua = ""
for r in rows:
    r["ua"] = ua_by_url.get(r["url"], "")

print(f"Rentetan serial {tries}x untuk {len(rows)} kandidat mati (jeda {gap}s)...\n")
out = []
for i, r in enumerate(rows, 1):
    statuses = []
    for t in range(tries):
        res = M.check(r)
        statuses.append(f"{res['status']}|{res['detail']}")
        if t < tries - 1:
            time.sleep(gap)
    alive_hits = sum(1 for s in statuses if s.startswith("Hidup") or s.startswith("DASH"))
    verdict = "HIDUP(batal hapus)" if alive_hits else "MATI(konsisten)"
    print(f"{i:>2}. [{verdict}] {r['name']} ({r['group']})")
    for t, s in enumerate(statuses, 1):
        print(f"      coba{t}: {s}")
    out.append((r, statuses, verdict))

with open("recheck_result.txt", "w") as f:
    for r, statuses, verdict in out:
        f.write(f"{verdict}\t{r['name']}\t{r['group']}\t{r['url']}\t" + " ; ".join(statuses) + "\n")

konsisten = [r for r, s, v in out if v.startswith("MATI")]
batal = [r for r, s, v in out if not v.startswith("MATI")]
print(f"\nRingkasan: {len(konsisten)} konsisten mati (aman dihapus), {len(batal)} ternyata hidup (jangan dihapus)")
print("Detail: recheck_result.txt")
if konsisten:
    with open("dead_confirmed.txt", "w") as f:
        for r in konsisten:
            f.write(f"{r['name']}|{r['group']}|{r['url']}\n")
    print("Daftar final yang dihapus: dead_confirmed.txt")
