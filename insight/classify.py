"""Pembersihan teks, klasifikasi kategori, deteksi provinsi, dan skor berbasis aturan (tanpa LLM)."""
from __future__ import annotations

import html
import re
import unicodedata
from functools import lru_cache

from . import scoring_rules as R
from .provinces import detect_province

TITLE_MAX = 300
SNIPPET_MAX = 300
URL_MAX = 2000

_TAG_RE = re.compile(r"<[^>]*>")
_CTRL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_WS_RE = re.compile(r"\s+")


def clean_text(raw: str | None, max_len: int) -> str:
    """Teks polos: html.unescape → buang tag → buang karakter kontrol → rapikan spasi → potong."""
    if not raw:
        return ""
    s = html.unescape(str(raw))
    s = _TAG_RE.sub(" ", s)
    s = html.unescape(s)            # entitas yang ter-escape ganda
    s = s.replace("<", " ").replace(">", " ")  # sisa tag terpotong/tidak lengkap
    s = _CTRL_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    if len(s) > max_len:
        cut = s[: max_len - 1]
        if " " in cut[max_len // 2:]:
            cut = cut[: cut.rfind(" ")]
        s = cut.rstrip(" ,.;:") + "…"
    return s


def clean_url(url: str | None) -> str | None:
    """Hanya terima URL http/https; selain itu None (item ditolak)."""
    from .config import is_http_url

    if not url:
        return None
    u = str(url).strip()
    if len(u) > URL_MAX or any(c in u for c in "\r\n\t <>\"'") or not is_http_url(u):
        return None
    return u


def normalize_title(title: str) -> str:
    s = unicodedata.normalize("NFKD", title or "").lower()
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^\w\s]", " ", s)
    return _WS_RE.sub(" ", s).strip()


@lru_cache(maxsize=None)
def _kw_pattern(words: tuple[str, ...]) -> re.Pattern:
    alts = "|".join(re.escape(w) for w in sorted(set(words), key=len, reverse=True))
    return re.compile(r"(?<![\w])(" + alts + r")(?![\w])", re.IGNORECASE)


def keyword_hits(text: str, words: tuple[str, ...]) -> int:
    if not text or not words:
        return 0
    return len(_kw_pattern(tuple(words)).findall(text))


def has_keyword(text: str, words: tuple[str, ...]) -> bool:
    return keyword_hits(text, words) > 0


def weighted_hits(text: str, weights: dict[str, int]) -> int:
    """Total bobot semua kemunculan kata kunci (frasa terpanjang didahulukan, tidak tumpang tindih)."""
    if not text or not weights:
        return 0
    lower = {k.lower(): v for k, v in weights.items()}
    return sum(lower.get(m.lower(), 0) for m in _kw_pattern(tuple(weights)).findall(text))


def matched_categories(text: str) -> dict[str, int]:
    """{kategori: total bobot} untuk kategori yang punya minimal satu kecocokan."""
    return {cat: n for cat, words in R.CATEGORY_KEYWORDS.items() if (n := weighted_hits(text, words))}


def classify_category(source: str, text: str, default_category: str | None = None) -> str:
    """Kategori tetap per sumber → bobot kata kunci tertinggi (seri: CATEGORY_PRIORITY) → kategori bawaan
    sumber/feed → "lainnya"."""
    base = source.split(".", 1)[0]
    if base in R.SOURCE_FIXED_CATEGORY:
        return R.SOURCE_FIXED_CATEGORY[base]
    default = default_category or R.SOURCE_DEFAULT_CATEGORY.get(base)
    hits = matched_categories(text)
    if not hits or (default and max(hits.values()) < R.DEFAULT_OVERRIDE_MIN_WEIGHT):
        return default or "lainnya"
    return max(hits, key=lambda c: (hits[c], -R.CATEGORY_PRIORITY.index(c)))


def matched_event_rules(text: str) -> list[R.NewsEventRule]:
    return [rule for rule in R.NEWS_EVENT_RULES if all(has_keyword(text, g) for g in rule.groups)]


# ---------- skor per jenis sumber ----------

def score_quake(magnitude: float | None, depth_km: float | None, tsunami: bool) -> int:
    score = R.QUAKE_BASE_SCORE
    if magnitude is not None:
        for floor, s in R.QUAKE_MAGNITUDE_SCORES:
            if magnitude >= floor - 1e-9:
                score = s
                break
    if tsunami:
        score += R.QUAKE_TSUNAMI_BONUS
    if depth_km is not None and depth_km < R.QUAKE_SHALLOW_KM:
        score += R.QUAKE_SHALLOW_BONUS
    return R.clamp_score(score)


def score_weather(cap_severity: str | None, title: str) -> int:
    if cap_severity and cap_severity.strip().lower() in R.WEATHER_CAP_SCORES:
        return R.WEATHER_CAP_SCORES[cap_severity.strip().lower()]
    score = R.WEATHER_BASE_SCORE
    if has_keyword(title, R.WEATHER_KEYWORDS):
        score += R.WEATHER_KEYWORD_BONUS
    return R.clamp_score(score)


def score_who(text: str) -> int:
    score = R.WHO_BASE_SCORE
    if has_keyword(text, R.INDONESIA_WORDS):
        score += R.WHO_INDONESIA_BONUS
    if has_keyword(text, R.WHO_SEA_COUNTRIES):
        score += R.WHO_SEA_BONUS
    if has_keyword(text, R.WHO_KEYWORDS):
        score += R.WHO_KEYWORD_BONUS
    return R.clamp_score(score)


def score_news(text: str, province: str | None) -> int:
    score = R.NEWS_BASE_SCORE
    hits = matched_categories(text)
    if hits:  # satu bonus tertinggi, bukan dijumlah
        score += max(R.NEWS_CATEGORY_BONUS.get(c, 0) for c in hits)
    rules = matched_event_rules(text)
    if rules:  # satu bonus aturan kejadian tertinggi, bukan dijumlah
        score += max(r.bonus for r in rules)
    if province:
        score += R.NEWS_PROVINCE_BONUS
    return R.clamp_score(score)


def looks_like_injection(text: str) -> bool:
    return any(re.search(p, text or "", re.IGNORECASE) for p in R.INJECTION_PATTERNS)


def classify_and_score(source: str, title: str, snippet: str, meta: dict,
                       preset_category: str | None = None,
                       preset_province: str | None = None,
                       default_category: str | None = None) -> tuple[str, str | None, int]:
    """Kembalikan (category, province, score)."""
    text = f"{title}\n{snippet}"
    base = source.split(".", 1)[0]
    category = preset_category or classify_category(source, text, default_category)
    province = preset_province or detect_province(text)
    if base in ("bmkg_quake", "usgs_quake"):
        score = score_quake(meta.get("magnitude"), meta.get("depth_km"), bool(meta.get("tsunami")))
    elif base == "bmkg_weather":
        score = score_weather(meta.get("cap_severity"), title)
    elif base == "who_don":
        score = score_who(text)
    else:
        score = score_news(text, province)
    return category, province, score
