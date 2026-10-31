#!/usr/bin/env python3
"""Kelompokkan hasil uji kandidat domain tak dikenal (cand_result.json) per tingkat risiko.

Pakai: python3 lapor_unknown.py   -> tulis sports_unknown_hasil.txt
"""
import json
from urllib.parse import urlparse
from collections import defaultdict

GRUP = {
    "A": {  # platform/CDN resmi atau broadcaster resmi
        "fastly.live.brightcove.com", "na.linear.zype.com", "cdn3.wowza.com",
        "1hskrdto.rocketcdn.com", "1593604785.rsc.cdn77.org", "1657061170.rsc.cdn77.org",
        "2-fss-1.streamhoster.com", "edge-001.streamup.eu", "directes-tv-int.3catdirectes.cat",
        "live.mnb.mn", "tjktv-live.tjk.org", "vtvgolive-ott3.vtvdigital.vn",
        "tvr-sport.lg.mncdn.com", "webtvstream.bhtelecom.ba", "africa24.vedge.infomaniak.com",
        "qazsporttv-stream.qazcdn.com", "mts1.iptv-playoutcenter.de", "dash2.antik.sk",
        "dash3.antik.sk", "dash4.antik.sk", "media1.skifnet.by", "ngtrk.dc.beltelecom.by",
        "jrtv-live.ercdn.net", "rnttwmjcin.turknet.ercdn.net", "cdn4.yayin.com.tr",
        "wurl120sports.global.transmit.live", "xumo-drct-ch812-n4996.fast.nbcuni.com",
        "xumo-xumoent-vc-122-sjv70.fast.nbcuni.com",
        "live-manifest.production-public.tubi.io",
        "db34cc6127ac459db55cab5f97cd66b9.mediatailor.us-west-2.amazonaws.com",
        "d03ae6b5c6724c24867e97a3dc04934a.mediatailor.us-west-2.amazonaws.com",
        "886bd3fbc782459f8de7555d32d7e9ce.mediatailor.us-west-2.amazonaws.com",
        "0b73ace69ebb45eaa249bb87837cb958.mediatailor.us-west-2.amazonaws.com",
    },
    "B": {  # abu-abu: aggregator/restreamer kecil, tidak jelas pemiliknya
        "cdn.rabta.stream", "hls.tvabierta.net", "fta.ektv.in",
        "livestream.lumpentv.com.ar", "master.tucableip.com", "tvsen5.aynaott.com",
        "srvx1.selftv.video", "h.jcp.live.opencaster.com", "cdn.bestream.io",
        "cast.talenttv.lk", "mrtvott.com", "live4dai.antenaplay.ro", "tvturf4.janus.cl",
        "live-04-11-tyc-app-web.vodgc.net", "live-aburayhan1106.telewebion.ir",
        "fighthls.persiana.live", "live-us1.thaimomo.com", "samitaorigin.tangotv.in",
        "webstream.multistream.it", "streaming.astrakhan.ru", "streaming.thestream.cyou",
        "flussonic.linkintel.ru", "live-3.otcnet.ru", "cnn.livestreaminggroup.info",
        "live1.acangroup.org", "streamtv.as3sport.online",
    },
    "C": {  # tolak: proxy eksplisit / port aneh / domain meniru merek lain
        "real-vk.proxy.nellaiiptv.com", "cnn.livestreaminggroup.info:3132",
        "live1.acangroup.org:1929", "streamtv.as3sport.online:3394",
        "live-aburayhan1106.telewebion.ir",
    },
}


def grup(dom):
    if dom in GRUP["C"] or "proxy" in dom:
        return "C"
    if dom in GRUP["A"]:
        return "A"
    return "B"


res = json.load(open("cand_result.json"))
live = [r for r in res if r["ok"]]
dead = [r for r in res if not r["ok"]]
per = defaultdict(list)
for r in live:
    per[grup(urlparse(r["url"]).netloc.lower())].append(r)

out = []
out.append("HASIL UJI KANDIDAT DI LUAR DAFTAR PUTIH — kategori sports (famelack/tvgarden)")
out.append(f"Diuji: {len(res)} URL | HIDUP: {len(live)} | MATI: {len(dead)}")
out.append("")
label = {"A": "GRUP A — layak dipertimbangkan (platform/CDN resmi atau broadcaster resmi)",
         "B": "GRUP B — abu-abu (aggregator/restreamer, pemilik tidak jelas)",
         "C": "GRUP C — tolak (proxy eksplisit / port aneh / domain meniru merek)"}
for g in "ABC":
    rs = per.get(g, [])
    doms = defaultdict(list)
    for r in rs:
        doms[urlparse(r["url"]).netloc.lower()].append(r["name"])
    out.append(f"{label[g]} — {len(rs)} URL / {len(doms)} domain")
    for dom, names in sorted(doms.items()):
        out.append(f"  {dom} :: {', '.join(sorted(set(names)))}")
    out.append("")
out.append("--- MATI (manifest/segmen gagal) ---")
for r in sorted(dead, key=lambda x: x["name"]):
    out.append(f"  {r['name']} ({r['country']}) | {r['detail']} | {r['url']}")
open("sports_unknown_hasil.txt", "w").write("\n".join(out) + "\n")
for g in "ABC":
    print(f"grup {g}: {len(per.get(g, []))} URL")
print("-> sports_unknown_hasil.txt")
