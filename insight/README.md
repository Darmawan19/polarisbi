# Insight Hub (`insight/`)

Mengumpulkan berita dan data publik yang mempengaruhi bisnis asuransi jiwa di Indonesia (bencana, wabah,
ekonomi, regulasi, industri asuransi), memberi skor berbasis aturan, lalu membuat brief harian, mingguan,
dan bulanan dengan bagian **"Dampak untuk BRI Life"**.

Dipasang di `api/main.py` lewat `setup_insight(app)` setelah `setup_auth(app)`. Semua rute ada di
`/api/insight/*`, jadi otomatis dilindungi `AuthMiddleware` (login + CSRF header `X-Requested-With: polarisbi`
untuk POST).

| Endpoint | Peran |
|---|---|
| `GET /api/insight/feed` | semua pengguna login |
| `GET /api/insight/digest?period=daily\|weekly\|monthly` | semua pengguna login |
| `POST /api/insight/digest/generate` | analyst, admin |
| `POST /api/insight/refresh` | admin |
| `GET /api/insight/sources` | semua pengguna login |
| `GET /api/insight/exposure` | semua pengguna login |

Aksi refresh dan generate dicatat ke `audit_log` polaris_auth (event `insight_refresh`,
`insight_digest_generate`) lewat fungsi publik `polaris_auth.service.audit`.

## Variabel lingkungan (semua opsional)

| Variabel | Default | Keterangan |
|---|---|---|
| `INSIGHT_DB_PATH` | `data/insight.db` | SQLite terpisah dari DB login & DuckDB |
| `INSIGHT_SOURCES` | `bmkg_quake,bmkg_weather,who_don,gdelt` | sumber bawaan yang aktif |
| `INSIGHT_RSS_FEEDS` | kosong | `label=url;label2=url2`; sumber `rss.<slug-label>` aktif otomatis bila terisi. Hanya http/https |
| `INSIGHT_HTTP_TIMEOUT` | `10` | detik per request |
| `INSIGHT_CAP_MAX_PER_CYCLE` | `20` | maks file CAP BMKG per siklus |
| `INSIGHT_RETENTION_DAYS` | `180` | item lebih tua dihapus |
| `INSIGHT_SCHEDULER` | `off` | `on` = refresh otomatis (hanya sumber, BUKAN brief) |
| `INSIGHT_REFRESH_MINUTES` | `30` | interval scheduler, minimum 5 |
| `INSIGHT_GENERATE_COOLDOWN_SECONDS` | `60` | cooldown `force=true` per periode |
| `INSIGHT_EXPOSURE_PROVIDER` | `demo` | nama provider exposure (nilai tak dikenal → `demo` + peringatan di log) |

LLM memakai `llm.py` di root repo (`ANTHROPIC_API_KEY`, `CLAUDE_MODEL`). Tanpa kunci, brief tetap dibuat
dengan templat (`status: "fallback"`).

## Sumber dan atribusi wajib

Atribusi disimpan per item (`attribution`) dan dikembalikan di feed serta `attributions` pada digest.
Frontend **wajib** menampilkannya.

| Kunci | Endpoint | Atribusi | Status verifikasi (2026-11-03) |
|---|---|---|---|
| `bmkg_quake` | `data.bmkg.go.id/DataMKG/TEWS/gempaterkini.json` + `gempadirasakan.json` | Sumber: BMKG | format diverifikasi |
| `bmkg_weather` | `www.bmkg.go.id/alerts/nowcast/id/rss.xml` + file CAP per item | Sumber: BMKG | RSS & CAP diverifikasi |
| `who_don` | `www.who.int/api/news/diseaseoutbreaknews` (JSON OData) | Sumber: WHO | diverifikasi; RSS DON lama sudah 404 |
| `gdelt` | `api.gdeltproject.org/api/v2/doc/doc` (artlist JSON) | Sumber: GDELT Project | endpoint hidup, tapi hanya mengembalikan `{}`/429 saat diuji; parser mengikuti dokumentasi |
| `rss.<slug>` | URL dari `INSIGHT_RSS_FEEDS` | Sumber: &lt;label&gt; | parser RSS 2.0 diuji dengan RSS nyata WHO; Atom didukung |

Catatan per sumber:
- **BMKG cuaca**: RSS tidak memuat keparahan; keparahan diambil dari CAP (`Moderate`=40, `Severe`=70,
  `Extreme`=90). CAP hanya diambil untuk guid baru (cache di `insight_cap_cache`, termasuk kegagalan),
  maks `INSIGHT_CAP_MAX_PER_CYCLE`, berurutan dengan jeda 300 ms, berhenti saat 429/error. URL CAP
  disusun ulang dari pola tetap `https://www.bmkg.go.id/alerts/nowcast/id/<nama>_alert.xml`; link lain tidak
  pernah diambil. Batas BMKG 60 request/menit/IP — jangan refresh lebih sering dari 5 menit.
- **GDELT**: batas 1 request per 5 detik. Lima query (ditetapkan server) dikirim berurutan dengan jeda 5,5 detik,
  berhenti saat 429 atau anggaran waktu 40 detik habis.
- Hanya judul, cuplikan ≤300 karakter (teks polos), URL, waktu, dan sumber yang disimpan — bukan artikel penuh.
- URL item hanya untuk ditampilkan; server tidak pernah mengambilnya.

## Menambah sumber baru

1. Buat `insight/sources/<nama>.py` berisi kelas dengan atribut `name`, `label`, `attribution` dan
   `async def fetch(self, client: httpx.AsyncClient) -> list[RawItem]` (lihat `sources/base.py`).
   Pakai `get_bytes()` (batas ukuran, error aman) dan `parse_xml()` (menolak ENTITY). URL hanya dari
   konstanta/konfigurasi, jangan dari input pengguna atau isi berita.
2. Lempar `SourceError` bila sumber gagal total; kegagalan tidak memengaruhi sumber lain.
3. Daftarkan di `BUILTIN` (`sources/__init__.py`) dan `config.BUILTIN_SOURCES`.
4. Bila perlu aturan skor khusus, tambahkan angkanya di `scoring_rules.py` dan cabangnya di
   `classify.classify_and_score`.
5. Simpan contoh respons nyata (kecil, tanpa data pribadi) di `tests/fixtures/insight/` dan tulis tes parser.

## Mengganti ExposureProvider ke data warehouse

`exposure.py` mendefinisikan protocol:

```python
class ExposureProvider(Protocol):
    is_demo: bool
    def get_exposure(self, provinces: Iterable[str] | None = None) -> list[dict]:
        # baris {province, product, active_policies}; province = nama kanonik di provinces.PROVINCES
```

1. Implementasikan mis. `WarehouseExposureProvider` dengan `is_demo = False` yang mengembalikan **agregat**
   jumlah polis aktif per provinsi & produk (tanpa data nasabah).
2. Daftarkan di `exposure.PROVIDERS` (mis. kunci `"warehouse"`), lalu set `INSIGHT_EXPOSURE_PROVIDER=warehouse`.
3. `exposure_is_demo` di respons otomatis mengikuti `provider.is_demo`.

Data demo (`demo_exposure.csv`) sepenuhnya FIKTIF: 38 provinsi × "Produk Demo A/B/C", 200–20.000 polis.

## Digest

- Jendela bergulir yang berakhir saat generate: daily 24 jam, weekly 7 hari, monthly 30 hari.
  `bucket_key` dari tanggal WIB (UTC+7): `YYYY-MM-DD`, `YYYY-Www` (minggu ISO), `YYYY-MM`.
- `GET /digest` mengembalikan digest untuk bucket saat ini; bila belum dibuat → `not_generated`.
- Item: skor ≥30, maks 25, urut skor lalu waktu (kurang dari 5 → ambil teratas apa pun). Item yang teksnya
  mirip instruksi (indikasi prompt injection) tidak dimasukkan ke brief.
- `impact` dihitung deterministik di backend, bukan LLM.
- Keluaran LLM divalidasi: JSON & skema, `item_ids` harus dikenal, panjang dibatasi, dan setiap angka harus
  ada di data masukan; bila tidak, bagian itu diganti teks templat. Gagal total → templat (`fallback`).
- `force=true` membuat ulang, dibatasi cooldown (429 `cooldown` + `retry_after_seconds`).
- `is_stale=true` bila ada item baru (fetched_at > generated_at) berskor ≥60 yang terbit sejak `period_start`.

## Privasi

- LLM hanya menerima berita publik (judul, cuplikan, metadata) dan **angka agregat** exposure per provinsi &
  produk. Tidak ada data nasabah.
- Teks dari sumber luar diperlakukan sebagai tidak dipercaya: dibersihkan sebelum disimpan, tidak pernah
  dieksekusi, tidak pernah dipakai sebagai URL untuk diambil server, dan dibungkus penanda DATA dalam prompt.
- Bila exposure sudah memakai data internal asli: kirim ke LLM **hanya agregat** (seperti sekarang), atau
  gunakan model lokal/on-premise bila kebijakan data mensyaratkannya.
- Kunci API tidak pernah dicatat ke log; pesan error sumber tidak memuat secret.

## Tes

```
.venv\Scripts\python.exe -m pytest -q tests/test_insight_*.py
```

Tes tidak memakai jaringan (httpx.MockTransport + fixture) dan memakai DB sementara (`tmp_path`).
