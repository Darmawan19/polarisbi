"""SEMUA aturan dan angka klasifikasi/skor ada di sini (tanpa LLM).

Penyesuaian terhadap angka default spesifikasi (setelah melihat format nyata):
- Cuaca BMKG tanpa CAP: bonus kata kunci hanya dicek di JUDUL. Deskripsi RSS BMKG hampir selalu memuat
  kalimat baku "berpotensi menimbulkan dampak berupa ... angin kencang, dan banjir lokal", sehingga bila
  deskripsi ikut dicek, semua item akan mendapat bonus dan bonus jadi tidak bermakna.
"""
from __future__ import annotations

from dataclasses import dataclass

# ---------- kategori ----------
# Urutan untuk memecah SERI total bobot kata kunci (lebih awal = menang). Tiga kategori ekonomi diurutkan dari
# yang paling spesifik: perbankan_bri, lalu pasar_keuangan, lalu ekonomi_makro. Urutan lama kategori lain
# (bencana_alam, kesehatan_wabah, industri_asuransi, regulasi) dipertahankan.
CATEGORY_PRIORITY = ("bencana_alam", "kesehatan_wabah", "industri_asuransi", "regulasi", "perbankan_bri",
                     "pasar_keuangan", "ekonomi_makro")

# Sumber terstruktur: kategori tetap, kata kunci tidak dipakai.
SOURCE_FIXED_CATEGORY = {
    "bmkg_quake": "bencana_alam",
    "bmkg_weather": "bencana_alam",
    "who_don": "kesehatan_wabah",
    "usgs_quake": "bencana_alam",
}
# Sumber berita resmi: kategori bawaan dipakai HANYA bila kata kunci tidak cocok kategori mana pun.
# (Feed dari INSIGHT_RSS_FEEDS berformat url|kategori diperlakukan sama.)
SOURCE_DEFAULT_CATEGORY = {
    "kemkes_rilis": "kesehatan_wabah",
    "worldbank_id": "ekonomi_makro",
}
# Sumber/feed berkategori bawaan: kategori bawaan hanya dikalahkan bila total bobot kata kunci tertinggi >= nilai
# ini. Mencegah satu kata umum (mis. "kredit" pada "kredit SKP dokter" di rilis Kemenkes) memindahkan kategori.
DEFAULT_OVERRIDE_MIN_WEIGHT = 2


def _w(weight: int, *words: str) -> dict[str, int]:
    return dict.fromkeys(words, weight)


# Bobot kata kunci: 1 = umum, 2 = spesifik, 3 = sangat spesifik / nama entitas.
# Kategori = total bobot kecocokan tertinggi (setiap kemunculan dihitung); seri → CATEGORY_PRIORITY.
# Pencocokan tidak peka huruf besar, utuh per kata; dalam satu kategori frasa terpanjang didahulukan
# (mis. "suku bunga kredit" dihitung sekali sebagai frasa itu, bukan juga sebagai "kredit").
CATEGORY_KEYWORDS: dict[str, dict[str, int]] = {
    "bencana_alam": _w(
        1, "banjir", "banjir bandang", "gempa", "gempa bumi", "gempabumi", "longsor", "tanah longsor", "erupsi",
        "tsunami", "gunung meletus", "puting beliung", "cuaca ekstrem", "kebakaran hutan", "karhutla", "bencana",
        "bencana alam", "flood", "floods", "flooding", "earthquake", "landslide", "eruption", "volcano",
        "cyclone", "natural disaster",
    ),
    "kesehatan_wabah": _w(
        1, "wabah", "klb", "kejadian luar biasa", "pandemi", "epidemi", "outbreak", "pandemic", "epidemic",
        "demam berdarah", "dbd", "dengue", "kolera", "cholera", "mpox", "flu burung", "avian influenza", "h5n1",
        "covid", "covid-19", "malaria", "campak", "measles", "polio", "tuberkulosis", "tbc",
    ),
    # inflasi, suku bunga acuan BI, PDB, neraca perdagangan, kurs rupiah, kebijakan fiskal
    "ekonomi_makro": {
        **_w(1, "suku bunga", "inflasi", "deflasi", "rupiah", "resesi", "nilai tukar", "kurs",
             "pertumbuhan ekonomi", "interest rate", "inflation", "recession", "exchange rate", "gdp", "fiskal",
             "fiscal"),
        **_w(2, "bi rate", "bi-rate", "suku bunga acuan", "bank indonesia", "pdb", "produk domestik bruto",
             "neraca perdagangan", "trade balance", "kebijakan fiskal", "apbn", "defisit anggaran", "kurs rupiah",
             "nilai tukar rupiah", "cadangan devisa"),
    },
    # IHSG, bursa saham, obligasi & SBN, reksa dana, volatilitas, aliran modal asing, trading halt
    "pasar_keuangan": {
        **_w(1, "saham", "bursa", "investor asing", "emiten"),
        **_w(2, "bursa saham", "bursa efek", "obligasi", "sbn", "reksa dana", "reksadana", "volatilitas",
             "imbal hasil", "yield obligasi", "bond yield", "stock market", "stock exchange", "net sell", "net buy",
             "capital outflow", "capital inflow", "auto rejection", "pasar modal"),
        **_w(3, "ihsg", "indeks harga saham gabungan", "bursa efek indonesia", "jakarta composite",
             "surat berharga negara", "aliran modal asing", "jual bersih asing", "trading halt",
             "penghentian sementara perdagangan"),
    },
    "regulasi": _w(
        1, "ojk", "pojk", "seojk", "otoritas jasa keuangan", "regulasi asuransi", "peraturan ojk",
        "financial services authority", "insurance regulation",
    ),
    "industri_asuransi": _w(
        1, "klaim", "asuransi", "asuransi jiwa", "premi", "reasuransi", "gagal bayar", "polis", "unit link", "aaji",
        "insurance", "insurer", "life insurance", "reinsurance", "claims",
    ),
    # Grup BRI + perbankan nasional (kredit, NPL, likuiditas bank, suku bunga kredit)
    "perbankan_bri": {
        **_w(1, "bank", "banking", "kredit", "dpk"),
        **_w(2, "perbankan", "npl", "kredit macet", "non performing loan", "likuiditas bank", "likuiditas perbankan",
             "suku bunga kredit", "dana pihak ketiga", "penyaluran kredit", "bpr", "kur"),
        **_w(3, "bri", "bbri", "bank rakyat indonesia", "bank bri", "kredit usaha rakyat", "bri life", "brilife",
             "bri insurance", "brins", "brimo"),
    },
}

# ---------- skor: gempa ----------
# (batas bawah magnitudo, skor) — dicek dari atas; M < 4.0 = 20.
QUAKE_MAGNITUDE_SCORES = ((7.0, 95), (6.0, 80), (5.0, 60), (4.0, 35))
QUAKE_BASE_SCORE = 20
QUAKE_TSUNAMI_BONUS = 10
QUAKE_SHALLOW_BONUS = 5
QUAKE_SHALLOW_KM = 70

# ---------- skor: cuaca BMKG ----------
WEATHER_CAP_SCORES = {"moderate": 40, "severe": 70, "extreme": 90}   # waspada / siaga / awas
WEATHER_BASE_SCORE = 30
WEATHER_KEYWORD_BONUS = 10
WEATHER_KEYWORDS = ("sangat lebat", "banjir", "puting beliung", "angin kencang", "longsor", "gelombang tinggi")

# ---------- skor: WHO ----------
WHO_BASE_SCORE = 40
WHO_INDONESIA_BONUS = 25
WHO_SEA_BONUS = 15
WHO_SEA_COUNTRIES = (
    "malaysia", "singapore", "singapura", "thailand", "viet nam", "vietnam", "philippines", "filipina",
    "cambodia", "kamboja", "lao", "laos", "myanmar", "brunei", "timor-leste", "timor leste",
)
WHO_KEYWORD_BONUS = 10
WHO_KEYWORDS = ("novel", "human-to-human", "avian", "h5n1", "cholera", "ebola", "marburg", "mpox", "polio")
INDONESIA_WORDS = ("indonesia",)

# ---------- skor: GDELT & RSS & berita resmi ----------
# Skor berita = NEWS_BASE_SCORE + bonus kategori TERTINGGI yang cocok + bonus aturan kejadian TERTINGGI yang
# cocok (tidak dijumlah antar-aturan) + bonus provinsi; dibatasi 0..100.
NEWS_BASE_SCORE = 25
NEWS_CATEGORY_BONUS = {
    "bencana_alam": 20, "kesehatan_wabah": 20, "regulasi": 20, "industri_asuransi": 20, "ekonomi_makro": 15,
    "pasar_keuangan": 15, "perbankan_bri": 15,
}
NEWS_PROVINCE_BONUS = 5


@dataclass(frozen=True)
class NewsEventRule:
    """Kejadian penting: cocok bila SETIAP grup punya minimal satu kata kunci di judul+cuplikan."""
    name: str
    groups: tuple[tuple[str, ...], ...]
    bonus: int


_BRI_GROUP = ("bri", "bbri", "bank rakyat indonesia", "bank bri", "bri life", "brilife", "bri insurance", "brins",
              "brimo")

NEWS_EVENT_RULES: tuple[NewsEventRule, ...] = (
    NewsEventRule("keputusan_bi_rate", (
        ("bi rate", "bi-rate", "suku bunga acuan", "bi7drr"),
        ("naik", "turun", "menaikkan", "menurunkan", "pertahankan", "dipertahankan", "mempertahankan", "tetap",
         "ditahan", "menahan",
         "pangkas", "memangkas", "hike", "cut", "raises", "lowers", "holds"),
    ), 15),
    NewsEventRule("ihsg_turun_tajam", (
        ("ihsg", "indeks harga saham gabungan", "jakarta composite", "bursa efek indonesia", "bursa saham"),
        ("anjlok", "ambruk", "ambles", "amblas", "terjun bebas", "merosot tajam", "rontok", "tumbang",
         "plunge", "plunges", "crash", "tumble", "tumbles"),
    ), 25),
    NewsEventRule("trading_halt", (
        ("trading halt", "penghentian sementara perdagangan", "circuit breaker", "auto rejection bawah"),
    ), 30),
    NewsEventRule("sanksi_ojk", (
        ("ojk", "otoritas jasa keuangan", "financial services authority"),
        ("sanksi", "cabut izin", "mencabut izin", "pencabutan izin", "dicabut izinnya", "pembekuan", "membekukan",
         "denda", "peringatan tertulis", "sanction", "sanctions", "revoke", "revokes", "revoked"),
    ), 20),
    NewsEventRule("material_grup_bri", (
        _BRI_GROUP,
        ("laba", "rugi", "merger", "akuisisi", "rups", "dividen", "fraud", "korupsi", "gangguan", "peretasan",
         "kebocoran data", "ransomware", "rights issue", "right issue", "pergantian direksi", "downgrade",
         "outage", "breach", "hacked", "profit", "loss"),
    ), 15),
    NewsEventRule("gangguan_penutupan_bank", (
        ("bank", "bpr", "perbankan", "banks"),
        ("dilikuidasi", "likuidasi", "cabut izin usaha", "pencabutan izin usaha", "dicabut izin usahanya",
         "penutupan bank", "bank ditutup", "gangguan layanan", "layanan terganggu", "rush", "bank run",
         "bank failure", "collapse", "collapses"),
    ), 25),
)

# ---------- label keparahan ----------
SEVERITY_THRESHOLDS = ((80, "sangat_tinggi"), (60, "tinggi"), (30, "sedang"))
SEVERITY_DEFAULT = "rendah"

# ---------- digest ----------
HIGH_SCORE = 60                 # "berskor tinggi" + ambang is_stale
DIGEST_MIN_SCORE = 30
DIGEST_MAX_ITEMS = 28           # Ronde 2: total maksimal (sebelumnya 25)
DIGEST_MAX_PER_CATEGORY = 4     # Ronde 2: kuota per kategori supaya semua aspek terwakili
DIGEST_MIN_ITEMS = 5
DIGEST_MAX_PROVINCES = 10

# ---------- dedupe ----------
DEDUPE_WINDOW_HOURS = 48
# Sumber terstruktur punya id kejadian sendiri; judulnya berulang wajar (mis. peringatan cuaca harian),
# jadi tidak ikut dedupe berdasarkan judul.
TITLE_DEDUPE_EXCLUDED_SOURCES = ("bmkg_quake", "bmkg_weather", "usgs_quake")

# ---------- pola teks yang mirip instruksi (indikasi prompt injection) ----------
INJECTION_PATTERNS = (
    r"abaikan\s+(semua\s+)?(instruksi|perintah|aturan)",
    r"lupakan\s+(semua\s+)?(instruksi|perintah|aturan)",
    r"ignore\s+(all\s+)?(the\s+)?(previous|prior|above)\s+(instructions|prompts?|rules)",
    r"disregard\s+(all\s+)?(the\s+)?(previous|prior|above)",
    r"system\s+prompt",
    r"anda\s+sekarang\s+adalah",
    r"you\s+are\s+now\s+",
    r"tulis\s+bahwa\s+",
)


def clamp_score(v: float) -> int:
    return int(max(0, min(100, round(v))))


def severity_label(score: int) -> str:
    for threshold, label in SEVERITY_THRESHOLDS:
        if score >= threshold:
            return label
    return SEVERITY_DEFAULT
