# listku

Playlist IPTV pribadi (Nanda) + alat uji/rawat-nya.

## Cara pakai di player
```
https://raw.githubusercontent.com/geckorename-prog/listku/main/playlist.m3u
```
Baris pertama wajib `#EXTM3U url-tvg="..."`. Jangan pakai URL `blob/...` (itu HTML, player menolak).

## Alat (semua dijalankan dari folder ini)
| Skrip | Fungsi |
|---|---|
| `check_streams_full.py playlist.m3u` | Scan kesehatan seluruh playlist (manifest + varian + segmen 200/206, fallback segmen terakhir untuk DVR). Hasil: tabel + `dead_channels_full.txt`. |
| `recheck_par.py dead_channels_full.txt 3` | Verifikasi ulang kandidat mati, 6 worker × 3 percobaan, pakai UA/referrer asli playlist. Hasil: `recheck_par_result.txt`, `dead_confirmed.txt`. **Ini yang dipakai** (versi serial ±90 detik/channel). |
| `recheck_serial.py dead_channels_full.txt 3` | Versi serial (lambat, untuk kandidat sedikit). |
| `hapus_mati.py playlist.m3u dead_confirmed.txt` | Hapus channel terkonfirmasi mati (tolak jalan kalau header hilang, atomic, chmod 644). |
| `cand_check.py kategori.json [--all]` | Uji kandidat channel baru dari JSON kategori tvgarden/famelack: filter daftar putih, verifikasi HLS penuh. Hasil: `cand_result.json`. |
| `add_channels.py daftar.json` | Sisip channel baru ke akhir blok grup-nya (idempotent by URL). |
| `lapor_unknown.py` | Kelompokkan hasil `cand_result.json` per tingkat risiko (A layak / B abu-abu / C tolak). |

## Aturan yang dipakai saat menambah channel
1. Hanya domain daftar putih (CDN resmi/broadcaster resmi/platform berlisensi) — lihat `cand_check.py` bagian `WHITELIST`.
2. Wajib lolos verifikasi HLS: manifest valid **dan** segmen pertama/terakhir 200/206. DASH & ClearKey tidak dimasukkan.
3. Daftar tolak mutlak (bozztv, cinerama.uz, freem3u, pishow, smartplaytv, dst.) — lihat `BANNED` di `cand_check.py`.
4. Channel baru → push tanpa nunggu konfirmasi kalau lolos verifikasi; domain baru di luar daftar putih → laporkan dulu ke Nanda.
5. Hapus channel hanya kalau gagal di SEMUA percobaan (dengan channel kontrol yang lolos) — hasil scan paralel sering menandai channel hidup sebagai mati saat jaringan hiccup.

## Catatan
- Kategori yang dipakai: TV Nasional, TVRI Daerah, TV Daerah, Anak, Animasi, Movie, Hiburan, Olahraga, Otomotif, Internasional, Culture, Dokumenter, Education, Business, World News, Music, Komedi, Lifestyle, Outdoor.
- File log/hasil scan tidak di-commit (lihat `.gitignore`).
