"""SEMUA aturan dan angka klasifikasi/skor ada di sini (tanpa LLM).

Penyesuaian terhadap angka default spesifikasi (setelah melihat format nyata):
- Cuaca BMKG tanpa CAP: bonus kata kunci hanya dicek di JUDUL. Deskripsi RSS BMKG hampir selalu memuat
  kalimat baku "berpotensi menimbulkan dampak berupa ... angin kencang, dan banjir lokal", sehingga bila
  deskripsi ikut dicek, semua item akan mendapat bonus dan bonus jadi tidak bermakna.
"""
from __future__ import annotations

# ---------- kategori ----------
CATEGORY_PRIORITY = ("bencana_alam", "kesehatan_wabah", "industri_asuransi", "regulasi", "ekonomi_makro")

SOURCE_FIXED_CATEGORY = {
    "bmkg_quake": "bencana_alam",
    "bmkg_weather": "bencana_alam",
    "who_don": "kesehatan_wabah",
}

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "bencana_alam": (
        "banjir", "banjir bandang", "gempa", "gempa bumi", "gempabumi", "longsor", "tanah longsor", "erupsi",
        "tsunami", "gunung meletus", "puting beliung", "cuaca ekstrem", "kebakaran hutan", "karhutla", "bencana",
        "bencana alam", "flood", "floods", "flooding", "earthquake", "landslide", "eruption", "volcano",
        "tsunami", "cyclone", "natural disaster",
    ),
    "kesehatan_wabah": (
        "wabah", "klb", "kejadian luar biasa", "pandemi", "epidemi", "outbreak", "pandemic", "epidemic",
        "demam berdarah", "dbd", "dengue", "kolera", "cholera", "mpox", "flu burung", "avian influenza", "h5n1",
        "covid", "covid-19", "malaria", "campak", "measles", "polio", "tuberkulosis", "tbc",
    ),
    "ekonomi_makro": (
        "suku bunga", "bi rate", "bi-rate", "inflasi", "deflasi", "rupiah", "resesi", "nilai tukar", "kurs",
        "pertumbuhan ekonomi", "interest rate", "inflation", "recession", "exchange rate",
    ),
    "regulasi": (
        "ojk", "pojk", "seojk", "otoritas jasa keuangan", "regulasi asuransi", "peraturan ojk",
        "financial services authority", "insurance regulation",
    ),
    "industri_asuransi": (
        "klaim", "asuransi", "asuransi jiwa", "premi", "reasuransi", "gagal bayar", "polis", "unit link", "aaji",
        "insurance", "insurer", "life insurance", "reinsurance", "claims",
    ),
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

# ---------- skor: GDELT & RSS ----------
NEWS_BASE_SCORE = 25
NEWS_CATEGORY_BONUS = {
    "bencana_alam": 20, "kesehatan_wabah": 20, "regulasi": 20, "industri_asuransi": 20, "ekonomi_makro": 15,
}
NEWS_PROVINCE_BONUS = 5

# ---------- label keparahan ----------
SEVERITY_THRESHOLDS = ((80, "sangat_tinggi"), (60, "tinggi"), (30, "sedang"))
SEVERITY_DEFAULT = "rendah"

# ---------- digest ----------
HIGH_SCORE = 60                 # "berskor tinggi" + ambang is_stale
DIGEST_MIN_SCORE = 30
DIGEST_MAX_ITEMS = 25
DIGEST_MIN_ITEMS = 5
DIGEST_MAX_PROVINCES = 10

# ---------- dedupe ----------
DEDUPE_WINDOW_HOURS = 48
# Sumber terstruktur punya id kejadian sendiri; judulnya berulang wajar (mis. peringatan cuaca harian),
# jadi tidak ikut dedupe berdasarkan judul.
TITLE_DEDUPE_EXCLUDED_SOURCES = ("bmkg_quake", "bmkg_weather")

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
