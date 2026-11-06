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
| `GET /api/insight/overview` | semua pengguna login (mesin keputusan) |
| `GET /api/insight/products/{code}` | semua pengguna login (404 `product_not_found`) |
| `GET /api/insight/decisions/history` | semua pengguna login |
| `POST /api/insight/decisions/{key}/status` | analyst, admin |

Aksi dicatat ke `audit_log` polaris_auth lewat fungsi publik `polaris_auth.service.audit`: `insight_refresh`,
`insight_digest_generate` (pengguna), `insight_digest_auto` (actor `system`, ringkasan otomatis), dan
`insight_decision_status` (perubahan status keputusan).

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
| `INSIGHT_PRODUCT_PROVIDER` | `demo` | provider katalog produk mesin keputusan (tak dikenal → `demo` + peringatan) |
| `INSIGHT_PRODUCT_CSV` | `insight/data/demo_products.csv` | lokasi katalog produk untuk provider `demo` |
| `INSIGHT_PRODUCT_PROVINCE_CSV` | `insight/data/demo_product_province.csv` | lokasi sebaran polis per provinsi untuk provider `demo` |

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

## Mesin keputusan (sinyal, peta panas produk, rekomendasi)

> **DEMO dan DRAF.** Katalog produk, sensitivitas, dan sebaran polis adalah **data fiktif** (`product_data_is_demo:
> true`) sampai ada sumber asli. Setiap rekomendasi adalah **draf untuk ditinjau manusia** (`is_draft: true`).
> Semua angka dihitung kode deterministik; modul `signals.py`, `products.py`, dan `playbook.py` tidak mengimpor
> atau memanggil LLM (dijaga tes).

Modul: `signals.py` (sinyal per aspek), `products.py` (provider produk + peta panas), `playbook.py` (aturan),
`overview.py` (rangkaian + cache). Semua konstanta ada di bagian atas modul masing-masing.

### Penggabungan duplikat (hanya di perhitungan; data tersimpan tidak diubah)

1. **Gempa lintas sumber** (`bmkg_quake` vs `usgs_quake`): satu gempa bila |Δ magnitudo| ≤ 0,3, |Δ waktu
   terbit| ≤ 30 menit, dan sumbernya berbeda. Kejadian memakai anggota berskor tertinggi.
2. **Berita sama dari media berbeda**: kategori sama, terbit ≤ 48 jam dari anggota pertama kelompok, dan
   kemiripan Jaccard token judul ≥ `SIMILARITY_THRESHOLD` (0,6) terhadap salah satu anggota. Judul dinormalisasi:
   huruf kecil, tanpa aksen dan tanda baca, tanpa kata umum (`STOPWORDS`), token ≥ 2 huruf. Cuaca dan gempa BMKG
   tidak ikut aturan ini (judulnya berulang wajar).
3. Satu kelompok = satu kejadian. Di setiap jendela, kejadian = anggota kelompok yang terbit di jendela itu;
   wakilnya anggota berskor tertinggi (seri: terbaru). Jumlah sumber berbeda dicatat per kejadian.
   **Semua jumlah kejadian dan bonus volume memakai kejadian, bukan item mentah.**

**Kalibrasi ambang (6 Nov 2026, 422 item asli dari 12 feed `INSIGHT_RSS_FEEDS`):** pasangan lintas sumber
dengan Jaccard ≥ 0,4 / 0,5 / 0,6 / 0,7 = 40 / 20 / 11 / 6. Semua pasangan ≥ 0,6 memang berita yang sama
(mis. cadangan devisa di 3 media, 0,78–0,80). Rentang 0,5–0,6 sebagian besar benar, tetapi ada salah gabung
("Daftar Terbaru Bunga Deposito Bank Digital" vs "Daftar Terbaru Bank Tutup", 0,56); di bawah 0,5 salah gabung
makin sering ("Rupiah dibuka …" vs "Rupiah ditutup …"). Ambang tetap **0,6**: presisi diutamakan, sebagian
duplikat dengan judul sangat berbeda (mis. dua judul "OJK cabut izin BPR") tetap terhitung terpisah.
Fixture tes (`tests/test_insight_decision_engine.py`) memakai parafrase judul nyata tersebut.

### Rumus sinyal per aspek

Aspek: `bencana_alam`, `kesehatan_wabah`, `ekonomi_makro`, `pasar_keuangan`, `regulasi`, `industri_asuransi`,
`perbankan_bri` (`lainnya` tidak dihitung). Untuk waktu acuan `t`, jendela = (t − 24 jam, t].

| Besaran | Rumus |
|---|---|
| recency_decay | `0,5 ^ (umur_jam / 24)`, umur dari waktu terbit wakil kejadian ke `t` |
| skor efektif | `skor kejadian × recency_decay` (× bobot geografis untuk sel produk) |
| bonus volume | `min(15, 3 × (n − 1))` bila `n ≥ 2`, selain itu 0; `n` = jumlah kejadian berskor efektif ≥ 30 |
| skor aspek | `min(100, skor efektif tertinggi + bonus volume)`, dibulatkan setengah ke atas |
| level | Normal < 30, Pantau 30–54, Waspada 55–74, Kritis ≥ 75 (legenda di `levels`) |
| delta | skor pada `t` − skor pada `t − 24 jam` (fungsi yang sama) |
| tren | naik bila delta ≥ +10, turun bila ≤ −10, selain itu stabil |
| komposit | `round(0,6 × skor aspek tertinggi + 0,4 × rata-rata tujuh aspek)`; level, delta, tren sama |
| sparkline | skor pada akhir tiap hari WIB selama 7 hari (hari ini = sekarang) |
| vs_baseline | skor − rata-rata skor akhir hari selama 30 hari sebelumnya (hanya hari setelah item tertua). `null` dan `baseline_ready: false` bila riwayat item < 7 hari |
| peta provinsi | per provinsi yang punya kejadian 24 jam: skor dengan fungsi yang sama atas kejadian tujuh aspek di provinsi itu, jumlah kejadian, daftar kategori |

Per aspek juga: `item_count` (kejadian 24 jam), `max_severity` (label keparahan skor kejadian tertinggi),
`top_event_ids` (3 kejadian dengan skor efektif tertinggi), `volume_bonus`.

### Katalog produk dan peta panas

`ProductExposureProvider` (`list_products`, `product_province_policies`, `is_demo`). `DemoProductProvider` membaca
`insight/data/demo_products.csv` dan `insight/data/demo_product_province.csv` (38 provinsi, total per produk =
`active_policies`, Jawa terbesar, Credit Life lebih tersebar karena KUR; Unit-Link 0 polis di 6 provinsi terpencil).

| Kode | Produk | Bencana | Wabah | Makro | Pasar | Regulasi | Ind. asuransi | Perbankan |
|---|---|---|---|---|---|---|---|---|
| DEMO-CL | Credit Life (Kredit KUR dan KPR) | 0,7 | 0,8 | 0,8 | 0,2 | 0,5 | 0,4 | 0,9 |
| DEMO-BS | Tabungan dan Endowment Bancassurance | 0,3 | 0,3 | 0,7 | 0,5 | 0,5 | 0,5 | 0,8 |
| DEMO-UL | Unit-Link | 0,1 | 0,2 | 0,5 | 1,0 | 0,8 | 0,5 | 0,4 |
| DEMO-PR | Proteksi Individu (Term Life) | 0,5 | 0,9 | 0,3 | 0,1 | 0,5 | 0,4 | 0,3 |
| COZY | Employee Benefit Kelompok (COZY) | 0,5 | 0,8 | 0,5 | 0,1 | 0,5 | 0,4 | 0,3 |
| DEMO-PA | Personal Accident Digital | 0,9 | 0,3 | 0,2 | 0,1 | 0,4 | 0,3 | 0,2 |

**Semua nilai di atas dan jumlah polis adalah asumsi awal dan data fiktif; wajib ditinjau Risk Management,
Aktuaria, dan pemilik produk.**

- `cell(p, a) = round(sensitivitas(p, a) × skor aspek untuk produk p)`.
- Aspek geografis (`bencana_alam`, `kesehatan_wabah`): skor aspek untuk produk p dihitung ulang dari kejadian
  dengan bobot `min(1, share_p / GEO_FULL_SHARE)` per kejadian, `GEO_FULL_SHARE = 0,02`; `share_p` = porsi
  polis produk p di provinsi kejadian. Kejadian tanpa provinsi berbobot 1. Aspek lain memakai skor aspek global.
- **Kalibrasi `GEO_FULL_SHARE`** (CSV demo, satu gempa berskor efektif 80 per provinsi, produk tertaut = sel
  bencana_alam ≥ 40). Provinsi tanpa produk tertaut dari 38: 0,05 → 30; 0,03 → 23; **0,02 → 17**; 0,015 → 12.
  Kriteria: setiap provinsi dengan porsi polis produk berkepekaan tinggi (Credit Life 0,7, PA 0,9) ≥ 1,5% harus
  menautkan produk itu, dan provinsi dengan porsi < 0,5% tidak menautkan produk. Hanya 0,02 dan 0,015 yang
  memenuhi keduanya; dipilih 0,02 (nilai terbesar = paling konservatif) supaya provinsi berporsi ~1% (mis.
  Kepulauan Riau, Bengkulu) tidak ikut tertaut. Dengan 0,02: Sulawesi Tengah menautkan Credit Life (sel 41),
  Aceh dan NTT menautkan Credit Life + PA, Jawa Timur keempat produk berkepekaan ≥ 0,5; Sulawesi Utara (porsi
  Credit Life 1,32%) dan Papua (0,64%) tidak menautkan produk. Sel maksimum per produk = sensitivitas × 80,
  sehingga Tabungan (0,3) dan Unit-Link (0,1) tidak pernah tertaut oleh bencana tunggal berskor 80.
- Per produk: `score` = sel tertinggi, `level`, `delta`/`trend` (dibanding 24 jam lalu), `drivers` (2 aspek
  dengan sel tertinggi), `cells` (tujuh aspek), `top_province` (provinsi dengan `sensitivitas × skor efektif ×
  bobot` tertinggi pada aspek geografis). Urutan matriks: `score` menurun, seri mengikuti urutan katalog.
- Produk "terkait" sebuah aspek: sel aspek itu ≥ 40, urut sel menurun.

**Mengganti CSV dengan sumber asli:** implementasikan provider dengan `is_demo = False` yang mengembalikan
katalog dan **agregat** polis aktif per provinsi (tanpa data nasabah), daftarkan di `products.PROVIDERS`
(mis. `"warehouse"`), lalu set `INSIGHT_PRODUCT_PROVIDER=warehouse`. `product_data_is_demo` mengikuti
`provider.is_demo`. Untuk sekadar mengganti file, pakai `INSIGHT_PRODUCT_CSV` / `INSIGHT_PRODUCT_PROVINCE_CSV`
(format kolom sama; baris berawalan `#` diabaikan).

### Aturan rekomendasi (`playbook.py`, aturan sebagai data)

Setiap aspek dengan level ≥ Pantau menghasilkan satu keputusan: Waspada/Kritis → `perlu_keputusan`,
Pantau → `pantau`.

| rule_id | Judul | Penanggung jawab | Horizon |
|---|---|---|---|
| `bencana_alam.kesiagaan_klaim` | Siapkan kesiagaan klaim di {provinsi teratas} | Klaim dan Risk Management | hari ini |
| `kesehatan_wabah.kesiapan_klaim` | Tinjau kesiapan klaim kesehatan dan kematian akibat wabah | Aktuaria, Underwriting, Klaim | 7 hari |
| `ekonomi_makro.asumsi_kredit` | Tinjau dampak kondisi makro terhadap asumsi dan kualitas kredit | Aktuaria dan Risk | 7 hari |
| `pasar_keuangan.unit_link` | Pantau dana Unit-Link dan portofolio investasi | Investasi dan Distribusi | hari ini |
| `regulasi.dampak_peraturan` | Analisis dampak peraturan baru terhadap produk dan proses | Kepatuhan, Legal, pemilik produk | 30 hari |
| `industri_asuransi.kompetitor` | Cermati perkembangan industri dan kompetitor | Produk dan Strategi | 30 hari |
| `perbankan_bri.grup_bri` | Pantau perkembangan Grup BRI dan perbankan nasional | Distribusi Bancassurance dan Risk | 7 hari |
| `lintas_aspek.eskalasi` | Eskalasi ke rapat risiko terpadu (bila ≥ 3 aspek Waspada atau lebih) | Direksi dan Risk | hari ini |

Daftar tindakan per aturan ada di `ASPECT_RULES` / `CROSS_RULE`.

- `key` = `rule_id:scope`, stabil tanpa timestamp; scope = slug provinsi teratas (hanya bencana alam) atau `all`.
- `priority_score` = bobot level (Pantau 1, Waspada 2, Kritis 3; lintas aspek 9) × 1000 + skor aspek
  (lintas aspek: komposit) × 10 + 500 bila **lonjakan** (delta aspek ≥ +25, juga ditandai di `flags`).
- `priority` = **peringkat** 1, 2, 3, … menurut `priority_score` menurun (seri: `key`), tanpa lubang. Maks 8 keputusan.
- `confidence`: jumlah sumber berbeda pada kejadian bukti (kelompok setelah penggabungan): ≥ 3 tinggi, 2 sedang,
  1 rendah (`source_count` ikut dikirim).
- `why` memuat angka hasil hitung (skor, level, jumlah kejadian, delta, provinsi teratas, jumlah produk terkait);
  `evidence` maks 5 kejadian (`id, title, url, source, published_at, score, severity, category`).
- `headline`: "N keputusan dibutuhkan: judul A; judul B", atau "Tidak ada keputusan mendesak. N aspek dipantau.",
  atau "Tidak ada keputusan mendesak. Semua aspek normal."

### `GET /api/insight/overview`

`generated_at, window_hours, composite {score, level, delta, trend}, counts {perlu_keputusan, dipantau, normal},
headline, aspects[], provinces[], products[], decisions[], baseline_ready, exposure_is_demo, product_data_is_demo,
attributions, degraded_sources, levels`. `counts.perlu_keputusan`/`dipantau` = jumlah keputusan per level;
`counts.normal` = jumlah aspek (dari tujuh) berlevel Normal. Hasil hitung di-cache 30 detik per penanda data
(waktu refresh terakhir, jumlah dan waktu item terbaru). Database kosong → semua Normal, tanpa keputusan.

`GET /api/insight/products/{code}`: baris matriks produk + `sensitivity`, `province_distribution`
(`province, policies, share`), `decisions` (keputusan yang memuat produk itu), `product_data_is_demo`.

### Log keputusan dan status (`decisions.py`)

Status: `baru` (bawaan), `ditinjau`, `disetujui`, `ditunda`, `ditolak`.

- **Kapan keputusan aktif disimpan (upsert):** (a) lewat pemicu pasca-refresh yang sudah ada
  (`pipeline.register_after_refresh(decisions.after_refresh)`, callback terisolasi; error tidak menggagalkan
  refresh), dan (b) secara malas setiap kali mesin menghitung ulang untuk `GET overview`/detail produk
  (`overview.on_compute`). Sumber lambat (GDELT, Kemenkes) selesai di latar belakang hingga ~47 detik setelah
  refresh dan pemicu berjalan sesudahnya, jadi keputusan dari data sumber lambat bisa sedikit terlambat
  dibanding berita cepat.
- **Upsert tidak menimpa status.** Yang diperbarui hanya `rule_id`, `last_seen_at`, `last_level`, `last_title`.
  Keputusan yang tidak lagi aktif tetap ada di log dengan `last_seen_at` terakhirnya.
- **Perubahan status:** `POST /api/insight/decisions/{key}/status` body `{"status": "...", "note": "..."}`
  (catatan opsional, maks 500 karakter). Hanya **analyst** dan **admin** (viewer 403 `forbidden`), wajib header
  CSRF `X-Requested-With: polarisbi` (403 `csrf`). Status tidak valid → 422 `invalid_status`; catatan terlalu
  panjang → 422 `invalid_note`; key tidak dikenal → 404 `decision_not_found`. Dicatat ke `audit_log` lewat
  `polaris_auth.service.audit` dengan event `insight_decision_status` (`key=… from=… to=…`).
- `GET /api/insight/decisions/history?limit=50` (maks 200): keputusan terbaru (`last_seen_at` menurun) beserta
  `events` (jejak perubahan, terlama dulu) dan daftar `statuses`.
- Di `overview` dan detail produk, tiap keputusan digabung dengan `status`, `status_note`, `status_updated_at`,
  `status_updated_by`, `first_seen_at` dari log. Bagian status ini **tidak** ikut cache 30 detik.

Skema (tabel baru, `CREATE TABLE IF NOT EXISTS`, tabel lama tidak diubah):
- `insight_decision(key PK, rule_id, first_seen_at, last_seen_at, last_level, last_title, status, note,
  updated_by, updated_at)`.
- `insight_decision_event(id, key, dari_status, ke_status, note, actor, at)`: **append-only** (trigger menolak
  UPDATE/DELETE). Satu baris saat keputusan pertama terlihat (actor `system`, `null → baru`) dan satu baris per
  perubahan status.

### Batas beban perhitungan

Perhitungan berjalan sekali untuk request bersamaan (lock hitung tunggal; request lain memakai hasilnya),
di-cache 30 detik per penanda data (maks 16 entri), dan memuat paling banyak `MAX_LOAD_ITEMS` (20.000) item
terbaru dari 32 hari terakhir.

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
