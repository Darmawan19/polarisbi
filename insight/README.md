# Insight Hub (`insight/`)

Mengumpulkan berita dan data publik yang mempengaruhi bisnis asuransi jiwa di Indonesia (bencana, wabah,
ekonomi makro, pasar keuangan, regulasi, industri asuransi, perbankan & Grup BRI), memberi skor berbasis aturan,
lalu membuat brief harian, mingguan, dan bulanan dengan bagian **"Dampak untuk BRI Life"**. Sejak Ronde 2 brief
dibuat **otomatis** setelah tiap pengambilan data.

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

Aksi dicatat ke `audit_log` polaris_auth lewat fungsi publik `polaris_auth.service.audit`: `insight_refresh`,
`insight_digest_generate` (pengguna), dan `insight_digest_auto` (actor `system`, ringkasan otomatis).

### Field tambahan Ronde 2 (hanya tambahan; field lama tidak berubah)

| Respons | Field baru |
|---|---|
| digest | `generated_trigger`: `"auto"` \| `"manual"` \| `null` (belum dibuat). Brief lama tanpa nilai → `"manual"`. `generated_by` tetap `llm`/`template`. |
| digest `content` | `aspects`: `[{category, items, max_score}]`; tiap `key_events[]` punya `category` (kategori item pertama) |
| refresh `results[]` | `background` (sumber lambat dilanjutkan di latar belakang), `degraded` (sumber membatasi laju) |
| sources `[]` | `degraded`, `degraded_reason` (nilai `status` tetap `ok`/`stale`/`error`/`disabled`) |
| feed / kategori | nilai kategori baru `pasar_keuangan`, `perbankan_bri` |

## Variabel lingkungan (semua opsional)

| Variabel | Default | Keterangan |
|---|---|---|
| `INSIGHT_DB_PATH` | `data/insight.db` | SQLite terpisah dari DB login & DuckDB |
| `INSIGHT_SOURCES` | `bmkg_quake,bmkg_weather,who_don,gdelt,usgs_quake,kemkes_rilis,worldbank_id` | sumber bawaan yang aktif |
| `INSIGHT_RSS_FEEDS` | kosong | feed tambahan (mis. media komersial); lihat format di bawah |
| `INSIGHT_HTTP_TIMEOUT` | `10` | detik per request (bawaan klien; sumber tertentu punya timeout sendiri) |
| `INSIGHT_CAP_MAX_PER_CYCLE` | `20` | maks file CAP BMKG per siklus |
| `INSIGHT_RETENTION_DAYS` | `180` | item lebih tua dihapus |
| `INSIGHT_SCHEDULER` | **`on`** (Ronde 2; sebelumnya `off`) | refresh otomatis berkala; `off` untuk mematikan |
| `INSIGHT_SCHEDULER_STARTUP_DELAY` | `10` | detik sebelum refresh pertama setelah startup |
| `INSIGHT_REFRESH_MINUTES` | `30` | interval scheduler, minimum 5 |
| `INSIGHT_GENERATE_COOLDOWN_SECONDS` | `60` | cooldown pembuatan ulang (`force`) per periode; berlaku juga untuk auto-digest |
| `INSIGHT_EXPOSURE_PROVIDER` | `demo` | nama provider exposure (nilai tak dikenal → `demo` + peringatan di log) |
| `INSIGHT_AUTO_DIGEST` | `on` | ringkasan otomatis setelah tiap refresh |
| `INSIGHT_AUTO_DAILY_MIN_MINUTES` | `60` | umur minimum brief harian yang stale sebelum dibuat ulang otomatis |
| `INSIGHT_AUTO_LONG_MIN_HOURS` | `24` | sama, untuk brief mingguan & bulanan |
| `INSIGHT_AUTO_MAX_CALLS_PER_DAY` | `30` | batas panggilan LLM oleh auto-digest per hari (hari WIB) |

LLM memakai `llm.py` di root repo (`ANTHROPIC_API_KEY`, `CLAUDE_MODEL`). Tanpa kunci, brief tetap dibuat
dengan templat (`status: "fallback"`).

### Format `INSIGHT_RSS_FEEDS`

Entri dipisah `;`. Setiap entri salah satu dari:

```
https://contoh.co.id/rss                       → label = host tanpa "www." (contoh.co.id)
https://contoh.co.id/rss|pasar_keuangan        → dengan kategori bawaan
Kontan=https://contoh.co.id/rss                → format lama label=url tetap berlaku
Kontan=https://contoh.co.id/rss|pasar_keuangan
```

Kunci sumber = `rss.<slug-label>`. Entri ditolak bila bukan http/https, host berupa IP literal / `localhost`,
atau kategori tidak dikenal. Kategori bawaan feed dipakai bila kata kunci tidak cocok (lihat aturan
klasifikasi). Media komersial (Kontan, Bisnis, CNBC Indonesia, Antara, dst.) **tidak aktif bawaan**; aktifkan
lewat env ini dan pastikan ketentuan penggunaan feed-nya dipenuhi.

## Kategori dan aturan klasifikasi

Kategori: `bencana_alam`, `kesehatan_wabah`, `ekonomi_makro`, `pasar_keuangan`, `regulasi`,
`industri_asuransi`, `perbankan_bri`, `lainnya`. Semua angka ada di `scoring_rules.py` (tanpa LLM).

| Kategori | Cakupan |
|---|---|
| `ekonomi_makro` | inflasi, suku bunga acuan BI / BI-Rate, PDB, neraca perdagangan, kurs rupiah, kebijakan fiskal/APBN |
| `pasar_keuangan` | IHSG, bursa saham, obligasi & SBN, reksa dana, volatilitas pasar, aliran modal asing, trading halt |
| `perbankan_bri` | BRI, Bank Rakyat Indonesia, BBRI, KUR, BRI Life, BRI Insurance, BRImo, serta perbankan nasional (kredit, NPL, likuiditas bank, suku bunga kredit, BPR) |

Urutan penentuan kategori:
1. **Kategori tetap per sumber** (`SOURCE_FIXED_CATEGORY`): `bmkg_quake`, `bmkg_weather`, `usgs_quake` →
   `bencana_alam`; `who_don` → `kesehatan_wabah`.
2. **Bobot kata kunci** (`CATEGORY_KEYWORDS`): bobot 1 = umum, 2 = spesifik, 3 = nama entitas/sangat spesifik.
   Setiap kemunculan dijumlahkan per kategori; dalam satu kategori frasa terpanjang didahulukan
   ("suku bunga kredit" dihitung sekali). Kategori dengan **total bobot tertinggi** menang.
3. **Seri** → kategori yang lebih awal di `CATEGORY_PRIORITY`:
   `bencana_alam, kesehatan_wabah, industri_asuransi, regulasi, perbankan_bri, pasar_keuangan, ekonomi_makro`.
   Jadi di antara tiga kategori ekonomi: `perbankan_bri` → `pasar_keuangan` → `ekonomi_makro` (yang lebih
   spesifik menang); urutan kategori lama tidak berubah.
4. **Kategori bawaan** sumber (`SOURCE_DEFAULT_CATEGORY`: `kemkes_rilis` → `kesehatan_wabah`, `worldbank_id` →
   `ekonomi_makro`) atau feed (`url|kategori`) dipakai bila tidak ada kata kunci yang cocok, **atau** bila bobot
   tertinggi < `DEFAULT_OVERRIDE_MIN_WEIGHT` (2). Ini mencegah satu kata umum memindahkan kategori (contoh nyata:
   "kredit SKP dokter" di rilis Kemenkes).
5. Selain itu `lainnya`.

Contoh: "Saham BBRI menguat" → `perbankan_bri` (BBRI 3 > saham 1); "saham bank" → seri 1:1 → `perbankan_bri`;
"BI rate naik, inflasi tertahan, rupiah menguat" → `ekonomi_makro`.

## Skor

- Gempa (BMKG & USGS): magnitudo `≥7.0`=95, `≥6.0`=80, `≥5.0`=60, `≥4.0`=35, lainnya 20; +10 tsunami; +5 bila
  kedalaman < 70 km; maks 100.
- Cuaca BMKG: CAP `Moderate`=40, `Severe`=70, `Extreme`=90; tanpa CAP 30 (+10 kata kunci di judul).
- WHO DON: 40, +25 Indonesia, +15 negara ASEAN, +10 kata kunci penyakit berbahaya.
- Berita (GDELT, RSS, Kemenkes, World Bank):
  `skor = 25 + bonus kategori tertinggi yang cocok + bonus aturan kejadian tertinggi yang cocok + 5 bila ada provinsi`,
  dibatasi 0–100. Bonus kategori: bencana_alam/kesehatan_wabah/regulasi/industri_asuransi 20,
  ekonomi_makro/pasar_keuangan/perbankan_bri 15.

Aturan kejadian (`NEWS_EVENT_RULES`, data yang mudah diedit; cocok bila setiap grup punya minimal satu kata):

| Aturan | Grup kata kunci (ringkas) | Bonus |
|---|---|---|
| `keputusan_bi_rate` | BI-Rate / suku bunga acuan **dan** naik/turun/pertahankan/tetap/pangkas | 15 |
| `ihsg_turun_tajam` | IHSG / BEI / bursa saham **dan** anjlok/ambruk/terjun bebas/merosot tajam/crash | 25 |
| `trading_halt` | trading halt / penghentian sementara perdagangan / circuit breaker | 30 |
| `sanksi_ojk` | OJK **dan** sanksi/cabut izin/pembekuan/denda/peringatan tertulis | 20 |
| `material_grup_bri` | BRI/BBRI/BRI Life/BRImo **dan** laba/rugi/merger/akuisisi/RUPS/dividen/fraud/gangguan/peretasan/kebocoran data | 15 |
| `gangguan_penutupan_bank` | bank/BPR/perbankan **dan** dilikuidasi/cabut izin usaha/penutupan/gangguan layanan/rush | 25 |

Contoh: "IHSG anjlok, BEI berlakukan trading halt" → 25 + 15 + 30 = 70.

## Sumber, verifikasi, dan atribusi wajib

Atribusi disimpan per item (`attribution`) dan dikembalikan di feed serta `attributions` pada digest.
Frontend **wajib** menampilkannya. Setiap sumber bawaan diverifikasi dengan benar-benar mengambil URL-nya
(curl, 2026-11-03); contoh respons yang sudah dipangkas ada di `tests/fixtures/insight/`.

### Terverifikasi dan aktif bawaan

| Kunci | URL | Format nyata | Kategori | Atribusi |
|---|---|---|---|---|
| `bmkg_quake` | `https://data.bmkg.go.id/DataMKG/TEWS/gempaterkini.json` + `gempadirasakan.json` | JSON | bencana_alam (tetap) | Sumber: BMKG |
| `bmkg_weather` | `https://www.bmkg.go.id/alerts/nowcast/id/rss.xml` + file CAP | RSS 2.0 + CAP XML | bencana_alam (tetap) | Sumber: BMKG |
| `who_don` | `https://www.who.int/api/news/diseaseoutbreaknews` | JSON OData | kesehatan_wabah (tetap) | Sumber: WHO |
| `usgs_quake` (baru) | `https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson` | GeoJSON FeatureCollection (`properties.mag/place/time/url/title/tsunami`, `geometry.coordinates=[lon,lat,depth]`); disaring ke `place` yang memuat "Indonesia" atau nama laut Indonesia | bencana_alam (tetap) | Sumber: USGS |
| `kemkes_rilis` (baru) | `https://kemkes.go.id/id/rss/article/rilis-berita` (ditemukan dari halaman resmi `kemkes.go.id/id/rss/all`) | RSS 2.0, `application/xml`, ~33 MB / ~8.000 item, ~18 detik ke byte pertama → dibaca bertahap, maks 40 item, di latar belakang | kesehatan_wabah (bawaan) | Sumber: Kementerian Kesehatan RI |
| `worldbank_id` (baru) | `https://search.worldbank.org/api/v2/news?format=json&rows=20&lang_exact=English&countcode=ID&fl=id,url,title,descr,lnchdt,displayconttype,count` | JSON `{documents: {<id>: {url, title.cdata!, descr.cdata!, lnchdt, ...}, facets}}`, urut terbaru | ekonomi_makro (bawaan) | Sumber: World Bank |
| `gdelt` | `https://api.gdeltproject.org/api/v2/doc/doc` (artlist JSON) | endpoint hidup, tetapi saat diuji ulang hanya `{}`/HTTP 429; parser mengikuti dokumentasi resmi | dari kata kunci | Sumber: GDELT Project |

GDELT tetap aktif seperti sebelumnya (bukan sumber baru); format daftar artikelnya **belum terverifikasi**.

### Tidak terverifikasi → TIDAK diaktifkan

| Kandidat | Yang dicoba | Alasan |
|---|---|---|
| Bank Indonesia (siaran pers, BI-Rate) | `www.bi.go.id` beranda & `…/news-release/default.aspx` | dengan User-Agent server: koneksi di-reset; beranda (UA browser) tidak memuat tautan RSS. Tidak ada feed yang bisa diverifikasi |
| BPS (rilis) | `www.bps.go.id/id/pressrelease/rss`, beranda | mengembalikan HTML (Next.js), tanpa RSS; API resmi BPS butuh kunci |
| OJK (siaran pers) | `www.ojk.go.id/id/rss/…`, `…/siaran-pers/default.aspx` | WAF: "Request Rejected" |
| Kemenkeu | `www.kemenkeu.go.id/rss`, beranda | HTML, tanpa tautan RSS |
| BNPB | `bnpb.go.id/rss`, `bnpb.go.id/berita` | HTTP 403 Cloudflare challenge |
| PVMBG / MAGMA Indonesia | `magma.esdm.go.id/rss`, `…/api/v1/home/gunung-api` | 404 / API butuh token |
| AAJI | `www.aaji.or.id/feed`, beranda | dialihkan ke halaman 404; tanpa tautan RSS |
| IMF | `www.imf.org/en/News/rss?language=eng`, RSS publikasi | HTTP 403 Access Denied (Akamai) |
| World Bank RSS | `…/en/news/all?format=rss`, `…/en/rss/news` | HTML / 404 → diganti API JSON di atas |

### Daftar domain yang diizinkan (SSRF)

Server hanya mengambil URL dari konstanta atau konfigurasi. `sources/base.py:check_host_allowed` menolak
permintaan bila host tidak persis ada di daftar ini (tanpa wildcard subdomain), berupa IP literal,
`localhost`/`*.local`/`*.internal`, atau skemanya bukan http/https. Redirect diikuti **manual** (maks 3) dan
setiap hop diperiksa ulang.

`config.BUILTIN_ALLOWED_HOSTS`:
`data.bmkg.go.id`, `www.bmkg.go.id`, `www.who.int`, `api.gdeltproject.org`, `earthquake.usgs.gov`,
`kemkes.go.id`, `search.worldbank.org`.

Host dari `INSIGHT_RSS_FEEDS` diizinkan hanya untuk feed itu sendiri (dipercaya karena diatur operator).
Batasan: nama host tidak di-resolve, jadi feed yang namanya mengarah ke IP privat tidak terdeteksi —
operator harus mengisi env ini hanya dengan feed tepercaya.

### Catatan per sumber

- **BMKG cuaca**: RSS tidak memuat keparahan; keparahan diambil dari CAP. CAP hanya diambil untuk guid baru
  (cache di `insight_cap_cache`), maks `INSIGHT_CAP_MAX_PER_CYCLE`, berurutan dengan jeda 300 ms, berhenti saat
  429/error. URL CAP disusun ulang dari pola tetap. Batas BMKG 60 request/menit/IP.
- **GDELT**: batas 1 request per 5 detik. **8 query** (satu per aspek: bencana, wabah, ekonomi makro, pasar
  keuangan, regulasi, industri asuransi, Grup BRI, perbankan nasional) dikirim berurutan dengan jeda 5,5 detik.
  HTTP 429 → tunggu 15 detik dan ulangi sekali; 429 lagi → siklus berhenti dan sumber ditandai **degraded**
  (bukan error). Anggaran waktu 100 detik, berjalan di latar belakang.
- **USGS & BMKG gempa**: gempa yang sama bisa muncul dari keduanya (id dan judul berbeda), tidak di-dedupe.
- Hanya judul, cuplikan ≤300 karakter (teks polos), URL, waktu, dan sumber yang disimpan, bukan artikel penuh.
- URL item hanya untuk ditampilkan; server tidak pernah mengambilnya.

### Timeout per sumber

Setiap adapter punya `timeout_seconds` sendiri (bawaan 30 detik bila tidak diisi): USGS & World Bank 25,
RSS env 25, Kemenkes 50, GDELT 130. Melewatinya → hanya sumber itu yang gagal ("melewati batas waktu sumber").

## Refresh, pemicu pasca-refresh, dan ringkasan otomatis

```
scheduler (startup +10 dtk, lalu tiap 30 mnt)  ┐
POST /api/insight/refresh (admin)              ┴→ pipeline.refresh(defer_slow=True)
   ├─ sumber cepat (BMKG, WHO, USGS, World Bank, RSS env) ditunggu → respons dikirim
   └─ latar belakang: sumber lambat (GDELT, Kemenkes; atribut slow=True)
          └─ pemicu pasca-refresh (register_after_refresh), berurutan, terisolasi
                 └─ auto_digest.after_refresh → daily → weekly → monthly
```

- **Lock**: refresh utama memakai lock non-blocking yang sama untuk POST dan scheduler (refresh kedua → 409 /
  siklus scheduler dilewati). Sumber lambat punya lock sendiri; bila siklus lambat sebelumnya masih berjalan,
  siklus lambat baru dilewati (tidak pernah ganda).
- **Lama POST refresh**: hanya menunggu sumber cepat. Diukur 2026-11-03 terhadap sumber nyata: respons 8,5 detik;
  sumber latar belakang selesai sekitar 47 detik setelah mulai (GDELT 429 → degraded). Batas keras sumber cepat tetap 60 detik.
- **Pemicu** (`pipeline.register_after_refresh(callback)`): `callback(result)` (sync atau async) dipanggil
  setelah setiap siklus selesai, termasuk sumber lambat. `result` = `{"results": [...], "finished_at"}` lengkap.
  Error tiap callback ditangkap dan dicatat ke log; tidak pernah menggagalkan refresh atau callback lain.
  Pemicu berjalan di latar belakang, sehingga POST refresh tidak menunggu pembuatan brief.
- **Auto-digest** (`auto_digest.py`), per periode (bucket WIB saat ini), berurutan:
  1. tidak ada kejadian di jendela periode → lewati;
  2. belum ada brief → buat;
  3. brief ada, `is_stale`, dan umurnya ≥ ambang (`INSIGHT_AUTO_DAILY_MIN_MINUTES` untuk harian,
     `INSIGHT_AUTO_LONG_MIN_HOURS` untuk mingguan/bulanan) → buat ulang (memakai cooldown yang sama dengan
     `force`; bila masih cooldown → dilewati dengan hasil `cooldown`);
  4. selain itu lewati.
  LLM dipakai bila kunci API ada **dan** panggilan LLM otomatis hari ini (WIB) < `INSIGHT_AUTO_MAX_CALLS_PER_DAY`.
  Bila kuota habis: brief **baru** tetap dibuat dengan templat, tetapi brief yang sudah ada **tidak** ditimpa
  templat (hasil `llm_budget`). Lock anti-duplikat sama dengan endpoint manual. Setiap pembuatan dicatat di tabel
  `insight_auto_digest_log` (dasar hitungan kuota) dan audit `insight_digest_auto` (actor `system`).
  Kuota hanya menghitung panggilan otomatis; endpoint generate manual tidak berubah.

## Menambah sumber baru

1. Buat `insight/sources/<nama>.py` berisi kelas dengan atribut `name`, `label`, `attribution`, opsional
   `timeout_seconds` dan `slow = True` (dijalankan di latar belakang), serta
   `async def fetch(self, client: httpx.AsyncClient) -> list[RawItem]` (lihat `sources/base.py`).
   Pakai `get_bytes()` / `stream_xml_entries()` (batas ukuran, allowlist, redirect diperiksa, error aman) dan
   `parse_xml()` (menolak ENTITY). URL hanya dari konstanta/konfigurasi.
2. **Verifikasi** URL dengan benar-benar mengambilnya, tambahkan host ke `config.BUILTIN_ALLOWED_HOSTS`, simpan
   contoh respons (dipangkas, tanpa data pribadi) di `tests/fixtures/insight/`, dan tulis tes parser.
3. Lempar `SourceError` bila sumber gagal total; isi `degraded_reason` bila sumber hanya membatasi laju.
4. Daftarkan di `BUILTIN` (`sources/__init__.py`) dan `config.BUILTIN_SOURCES`; tentukan kategori tetap
   (`SOURCE_FIXED_CATEGORY`) atau bawaan (`SOURCE_DEFAULT_CATEGORY`) di `scoring_rules.py`.

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
- Pemilihan item (Ronde 2): skor ≥30, urut skor lalu waktu, **maks 4 per kategori dan maks 28 total** supaya
  semua aspek terwakili (kurang dari 5 → ambil teratas apa pun, tanpa kuota). Item yang teksnya mirip instruksi
  (indikasi prompt injection) tidak dimasukkan ke brief dan tidak dihitung sebagai kejadian oleh auto-digest.
- `content.aspects` dan `key_events[].category` dihitung deterministik dari item terpilih (bukan dari LLM).
- `impact` dihitung deterministik di backend, bukan LLM.
- Keluaran LLM divalidasi: JSON & skema, `item_ids` harus dikenal, panjang dibatasi, dan setiap angka harus
  ada di data masukan; bila tidak, bagian itu diganti teks templat. Gagal total → templat (`fallback`).
- `force=true` membuat ulang, dibatasi cooldown (429 `cooldown` + `retry_after_seconds`).
- `is_stale=true` bila ada item baru (fetched_at > generated_at) berskor ≥60 yang terbit sejak `period_start`.

## Skema DB (tambahan Ronde 2, tabel lama tidak diubah kecuali satu kolom)

- `insight_digests.generated_trigger TEXT` (ditambahkan otomatis lewat `ALTER TABLE ADD COLUMN`, idempoten).
- `insight_source_health(source, degraded, degraded_reason, updated_at)`: penanda degraded per sumber.
- `insight_auto_digest_log(id, at, period, bucket_key, action, llm_called, result)`: jejak auto-digest.

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

Tes tidak memakai jaringan (httpx.MockTransport + fixture), memakai DB sementara (`tmp_path`), dan **memaksa
`INSIGHT_SCHEDULER=off`** (`tests/conftest.py` dan fixture `insight_env`); auto-digest dimatikan kecuali di tes
yang menyalakannya secara eksplisit.
