"""Sinyal terukur per aspek: skor 0..100, level, delta, tren, grafik 7 hari, baseline 30 hari, peta provinsi.

Semua angka dihitung deterministik dari insight_items (tanpa LLM). Rumus lengkap ada di insight/README.md
bagian "Mesin keputusan". Semua konstanta di bawah ini adalah satu-satunya tempat angka itu diatur.

Penggabungan duplikat hanya di perhitungan (data tersimpan tidak diubah):
a. Gempa lintas sumber (BMKG vs USGS): |selisih magnitudo| <= QUAKE_MAX_MAG_DIFF dan |selisih waktu terbit|
   <= QUAKE_MAX_MINUTES → satu gempa; skor = skor anggota tertinggi.
b. Berita sama dari media berbeda: kategori sama, dalam GROUP_WINDOW_HOURS dari anggota pertama kelompok, dan
   kemiripan token Jaccard judul ternormalisasi >= SIMILARITY_THRESHOLD terhadap salah satu anggota.
   Sumber terstruktur (TITLE_GROUP_EXCLUDED_SOURCES: gempa & cuaca BMKG) tidak ikut (b).
Satu kelompok = satu kejadian. Semua jumlah kejadian dan bonus volume memakai kelompok.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable

from . import db as dbm
from . import scoring_rules as R
from .classify import normalize_title

# ---------- aspek ----------
ASPECTS = ("bencana_alam", "kesehatan_wabah", "ekonomi_makro", "pasar_keuangan", "regulasi", "industri_asuransi",
           "perbankan_bri")
ASPECT_LABELS = {
    "bencana_alam": "Bencana alam", "kesehatan_wabah": "Kesehatan & wabah", "ekonomi_makro": "Ekonomi makro",
    "pasar_keuangan": "Pasar keuangan", "regulasi": "Regulasi", "industri_asuransi": "Industri asuransi",
    "perbankan_bri": "Perbankan & Grup BRI",
}

# ---------- jendela ----------
WINDOW_HOURS = 24            # jendela "sekarang"; pembanding = 24 jam sebelumnya
SPARK_DAYS = 7               # grafik kecil: skor pada akhir tiap hari WIB
BASELINE_DAYS = 30           # rata-rata skor harian
BASELINE_MIN_HISTORY_DAYS = 7
DAY_TZ = timezone(timedelta(hours=7))   # hari dihitung dalam WIB (sama dengan digest)

# ---------- skor ----------
HALF_LIFE_HOURS = 24.0       # recency_decay = 0.5 ** (umur_jam / HALF_LIFE_HOURS)
VOLUME_MIN_EFFECTIVE = 30    # kejadian dihitung untuk bonus volume bila skor efektifnya >= ini
VOLUME_MIN_EVENTS = 2        # bonus hanya bila jumlah kejadian itu >= ini
VOLUME_PER_EVENT = 3         # bonus = min(VOLUME_MAX_BONUS, VOLUME_PER_EVENT x (jumlah - 1))
VOLUME_MAX_BONUS = 15
SCORE_MAX = 100

# ---------- level & tren ----------
LEVEL_THRESHOLDS = ((75, "kritis"), (55, "waspada"), (30, "pantau"))   # dicek dari atas
LEVEL_DEFAULT = "normal"
LEVEL_ORDER = ("normal", "pantau", "waspada", "kritis")
LEVEL_LABELS = {"normal": "Normal", "pantau": "Pantau", "waspada": "Waspada", "kritis": "Kritis"}
TREND_THRESHOLD = 10         # naik bila delta >= +10, turun bila <= -10

# ---------- indeks komposit ----------
COMPOSITE_MAX_WEIGHT = 0.6   # x skor aspek tertinggi
COMPOSITE_MEAN_WEIGHT = 0.4  # x rata-rata tujuh aspek

# ---------- penggabungan duplikat ----------
QUAKE_SOURCES = ("bmkg_quake", "usgs_quake")
QUAKE_MAX_MAG_DIFF = 0.3
QUAKE_MAX_MINUTES = 30
SIMILARITY_THRESHOLD = 0.6
GROUP_WINDOW_HOURS = 48
TITLE_GROUP_EXCLUDED_SOURCES = R.TITLE_DEDUPE_EXCLUDED_SOURCES   # bmkg_quake, bmkg_weather, usgs_quake
MIN_TOKEN_LEN = 2
STOPWORDS = frozenset("""
yang di ke dari dan atau ini itu untuk dengan pada dalam akan juga tak tidak ada jadi hingga sampai oleh sebagai
bisa dapat karena agar usai saat kata soal apa begini simak lagi sudah telah masih para bagi per atas bawah baru
kini jelang demi antara serta namun tapi tetapi pun kah lah nya mulai segera resmi terkait soal hari ini
video foto berita breaking update live
the a an of to in on for and or is are was were be by with as at from its it this that after over says said
""".split())

LOOKBACK_DAYS = BASELINE_DAYS + 2   # data yang dimuat untuk baseline + pembanding


# ---------- utilitas ----------

def round_half_up(x: float) -> int:
    """Pembulatan setengah ke atas (bukan banker's rounding) supaya mudah dijelaskan."""
    return int(math.floor(x + 0.5))


def level_for(score: float) -> str:
    for threshold, name in LEVEL_THRESHOLDS:
        if score >= threshold:
            return name
    return LEVEL_DEFAULT


def level_rank(level: str) -> int:
    return LEVEL_ORDER.index(level)


def trend_for(delta: int) -> str:
    if delta >= TREND_THRESHOLD:
        return "naik"
    if delta <= -TREND_THRESHOLD:
        return "turun"
    return "stabil"


def levels_legend() -> list[dict]:
    """Batas level untuk frontend: [{level, label, min, max}] dari Normal ke Kritis."""
    asc = sorted(LEVEL_THRESHOLDS)
    names = [LEVEL_DEFAULT] + [n for _, n in asc]
    mins = [0] + [t for t, _ in asc]
    maxs = [t - 1 for t, _ in asc] + [SCORE_MAX]
    return [{"level": n, "label": LEVEL_LABELS[n], "min": lo, "max": hi} for n, lo, hi in zip(names, mins, maxs)]


def recency_decay(age_hours: float) -> float:
    return 0.5 ** (max(0.0, age_hours) / HALF_LIFE_HOURS)


def title_tokens(title: str) -> frozenset[str]:
    return frozenset(t for t in normalize_title(title).split() if len(t) >= MIN_TOKEN_LEN and t not in STOPWORDS)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ---------- model ----------

@dataclass(frozen=True)
class Item:
    id: str
    source: str
    base: str
    title: str
    url: str
    attribution: str
    published: datetime
    category: str
    province: str | None
    score: int
    magnitude: float | None
    tokens: frozenset[str]

    @property
    def published_iso(self) -> str:
        return dbm.to_iso(self.published)


@dataclass(frozen=True)
class Event:
    """Satu kejadian (kelompok) di dalam satu jendela. rep = anggota berskor tertinggi (seri: terbaru, lalu id)."""
    rep: Item
    members: tuple[Item, ...]

    @property
    def id(self) -> str:
        return self.rep.id

    @property
    def category(self) -> str:
        return self.rep.category

    @property
    def score(self) -> int:
        return self.rep.score

    @property
    def published(self) -> datetime:
        return self.rep.published

    @property
    def province(self) -> str | None:
        if self.rep.province:
            return self.rep.province
        return next((m.province for m in self.members if m.province), None)

    @property
    def sources(self) -> frozenset[str]:
        return frozenset(m.source for m in self.members)

    def effective(self, ref: datetime, weight: float = 1.0) -> float:
        age_h = (ref - self.published).total_seconds() / 3600.0
        return self.score * recency_decay(age_h) * weight

    def evidence(self) -> dict:
        r = self.rep
        return {"id": r.id, "title": r.title, "url": r.url, "source": r.source, "published_at": r.published_iso,
                "score": r.score, "severity": R.severity_label(r.score), "category": r.category}


def _rep(members: Iterable[Item]) -> Item:
    return max(members, key=lambda m: (m.score, m.published, m.id))


# ---------- muat data ----------

def _magnitude(meta_json: str | None) -> float | None:
    try:
        v = json.loads(meta_json or "{}").get("magnitude")
        return float(v) if v is not None else None
    except (ValueError, TypeError, AttributeError):
        return None


def load_items(conn, since: datetime, until: datetime) -> list[Item]:
    rows = conn.execute(
        "SELECT id, source, title, url, attribution, published_at, category, province, score, meta_json"
        " FROM insight_items WHERE published_at > ? AND published_at <= ? AND category IN (%s)"
        " ORDER BY published_at ASC, id ASC" % ",".join("?" * len(ASPECTS)),
        (dbm.to_iso(since), dbm.to_iso(until), *ASPECTS)).fetchall()
    out = []
    for r in rows:
        pub = dbm.parse_iso(r["published_at"])
        if pub is None:
            continue
        base = r["source"].split(".", 1)[0]
        out.append(Item(id=r["id"], source=r["source"], base=base, title=r["title"], url=r["url"],
                        attribution=r["attribution"], published=pub, category=r["category"],
                        province=r["province"], score=int(r["score"]),
                        magnitude=_magnitude(r["meta_json"]) if base in QUAKE_SOURCES else None,
                        tokens=title_tokens(r["title"])))
    return out


def oldest_item_time(conn) -> datetime | None:
    row = conn.execute("SELECT MIN(published_at) FROM insight_items WHERE category IN (%s)"
                       % ",".join("?" * len(ASPECTS)), ASPECTS).fetchone()
    return dbm.parse_iso(row[0]) if row and row[0] else None


# ---------- penggabungan ----------

def _quake_groups(quakes: list[Item]) -> list[list[Item]]:
    groups: list[list[Item]] = []
    max_dt = timedelta(minutes=QUAKE_MAX_MINUTES)
    for q in quakes:   # urut waktu terbit
        placed = False
        if q.magnitude is not None:
            for g in groups:
                if any(m.base == q.base for m in g):     # hanya lintas sumber
                    continue
                if any(m.magnitude is not None and abs(m.magnitude - q.magnitude) <= QUAKE_MAX_MAG_DIFF + 1e-9
                       and abs(m.published - q.published) <= max_dt for m in g):
                    g.append(q)
                    placed = True
                    break
        if not placed:
            groups.append([q])
    return groups


def _title_groups(items: list[Item], threshold: float) -> list[list[Item]]:
    """Kelompok berita mirip per kategori. Indeks token → kelompok supaya tidak membandingkan semua pasangan."""
    groups: list[list[Item]] = []
    starts: list[datetime] = []
    index: dict[tuple[str, str], list[int]] = {}
    window = timedelta(hours=GROUP_WINDOW_HOURS)
    for it in items:   # urut waktu terbit
        cands: set[int] = set()
        for tok in it.tokens:
            cands.update(index.get((it.category, tok), ()))
        best, best_sim = None, 0.0
        for gi in sorted(cands):
            if it.published - starts[gi] > window:
                continue
            sim = max(jaccard(it.tokens, m.tokens) for m in groups[gi])
            if sim >= threshold and sim > best_sim:
                best, best_sim = gi, sim
        if best is None:
            groups.append([it])
            starts.append(it.published)
            best = len(groups) - 1
        else:
            groups[best].append(it)
        for tok in it.tokens:
            lst = index.setdefault((it.category, tok), [])
            if not lst or lst[-1] != best:
                lst.append(best)
    return groups


def build_groups(items: list[Item], threshold: float | None = None) -> list[tuple[Item, ...]]:
    th = SIMILARITY_THRESHOLD if threshold is None else threshold
    quakes = [i for i in items if i.base in QUAKE_SOURCES]
    excluded = [i for i in items if i.base in TITLE_GROUP_EXCLUDED_SOURCES and i.base not in QUAKE_SOURCES]
    news = [i for i in items if i.base not in TITLE_GROUP_EXCLUDED_SOURCES and i.base not in QUAKE_SOURCES]
    groups = _quake_groups(quakes) + [[i] for i in excluded] + _title_groups(news, th)
    return [tuple(g) for g in groups]


def events_in_window(groups: list[tuple[Item, ...]], start: datetime, end: datetime) -> list[Event]:
    """Kejadian = anggota kelompok yang terbit di (start, end]. rep dipilih ulang dari anggota di jendela."""
    out = []
    for g in groups:
        members = tuple(m for m in g if start < m.published <= end)
        if members:
            out.append(Event(rep=_rep(members), members=members))
    return out


# ---------- skor aspek ----------

@dataclass
class AspectScore:
    score: int
    raw: float
    top_effective: float
    volume_count: int
    volume_bonus: int
    ranked: list[tuple[float, Event]] = field(default_factory=list)   # (skor efektif, kejadian), menurun


def aspect_score(events: list[Event], ref: datetime,
                 weight: Callable[[Event], float] | None = None) -> AspectScore:
    """min(100, skor efektif tertinggi + bonus volume). Skor efektif = skor x recency_decay x bobot."""
    ranked = sorted(((e.effective(ref, weight(e) if weight else 1.0), e) for e in events),
                    key=lambda x: (-x[0], -x[1].score, x[1].id))
    top = ranked[0][0] if ranked else 0.0
    n = sum(1 for eff, _ in ranked if eff >= VOLUME_MIN_EFFECTIVE)
    bonus = min(VOLUME_MAX_BONUS, VOLUME_PER_EVENT * (n - 1)) if n >= VOLUME_MIN_EVENTS else 0
    raw = min(float(SCORE_MAX), top + bonus)
    return AspectScore(score=round_half_up(raw), raw=raw, top_effective=top, volume_count=n, volume_bonus=bonus,
                       ranked=ranked)


def window_events(groups, ref: datetime) -> list[Event]:
    return events_in_window(groups, ref - timedelta(hours=WINDOW_HOURS), ref)


def by_aspect(events: list[Event]) -> dict[str, list[Event]]:
    out: dict[str, list[Event]] = {a: [] for a in ASPECTS}
    for e in events:
        if e.category in out:
            out[e.category].append(e)
    return out


def aspect_scores_at(groups, ref: datetime) -> dict[str, AspectScore]:
    ev = by_aspect(window_events(groups, ref))
    return {a: aspect_score(ev[a], ref) for a in ASPECTS}


def composite_score(scores: dict[str, int]) -> int:
    vals = [scores[a] for a in ASPECTS]
    return round_half_up(COMPOSITE_MAX_WEIGHT * max(vals) + COMPOSITE_MEAN_WEIGHT * (sum(vals) / len(vals)))


def day_end_refs(now: datetime, days: int, include_today: bool) -> list[tuple[str, datetime]]:
    """[(tanggal WIB, waktu acuan UTC)], terlama dulu. Hari ini → acuan = now; hari lalu → 00:00 WIB berikutnya."""
    local_today = now.astimezone(DAY_TZ).date()
    out = []
    rng = range(days - 1, -1, -1) if include_today else range(days, 0, -1)
    for back in rng:
        d = local_today - timedelta(days=back)
        if back == 0:
            ref = now
        else:
            ref = datetime(d.year, d.month, d.day, tzinfo=DAY_TZ) + timedelta(days=1)
            ref = ref.astimezone(timezone.utc)
        out.append((d.isoformat(), ref))
    return out


@dataclass
class Signals:
    now: datetime
    groups: list[tuple[Item, ...]]
    current: dict[str, list[Event]]
    previous: dict[str, list[Event]]
    now_scores: dict[str, AspectScore]
    prev_scores: dict[str, AspectScore]
    aspects: list[dict]
    composite: dict
    provinces: list[dict]
    baseline_ready: bool
    attributions: list[str]

    def aspect(self, name: str) -> dict:
        return next(a for a in self.aspects if a["aspect"] == name)


def compute_signals(conn, now: datetime) -> Signals:
    items = load_items(conn, now - timedelta(days=LOOKBACK_DAYS), now)
    oldest = oldest_item_time(conn)
    groups = build_groups(items)
    prev_ref = now - timedelta(hours=WINDOW_HOURS)
    cur_events = by_aspect(window_events(groups, now))
    prev_events = by_aspect(window_events(groups, prev_ref))
    now_scores = {a: aspect_score(cur_events[a], now) for a in ASPECTS}
    prev_scores = {a: aspect_score(prev_events[a], prev_ref) for a in ASPECTS}

    spark_refs = day_end_refs(now, SPARK_DAYS, include_today=True)
    spark_scores = [(d, aspect_scores_at(groups, ref)) for d, ref in spark_refs]

    baseline_ready = oldest is not None and now - oldest >= timedelta(days=BASELINE_MIN_HISTORY_DAYS)
    baseline_mean: dict[str, float] = {}
    if baseline_ready:
        refs = [(d, ref) for d, ref in day_end_refs(now, BASELINE_DAYS, include_today=False) if ref > oldest]
        daily = [aspect_scores_at(groups, ref) for _, ref in refs]
        for a in ASPECTS:
            baseline_mean[a] = sum(s[a].score for s in daily) / len(daily) if daily else 0.0

    aspects = []
    for a in ASPECTS:
        cur, prev = now_scores[a], prev_scores[a]
        delta = cur.score - prev.score
        events = cur_events[a]
        aspects.append({
            "aspect": a, "label": ASPECT_LABELS[a], "score": cur.score, "level": level_for(cur.score),
            "delta": delta, "trend": trend_for(delta), "item_count": len(events),
            "max_severity": R.severity_label(max(e.score for e in events)) if events else None,
            "top_event_ids": [e.id for _, e in cur.ranked[:3]],
            "volume_bonus": cur.volume_bonus,
            "sparkline": [{"date": d, "score": s[a].score} for d, s in spark_scores],
            "vs_baseline": round(cur.score - baseline_mean[a], 1) if baseline_ready else None,
            "baseline_ready": baseline_ready,
        })

    cur_c = composite_score({a: now_scores[a].score for a in ASPECTS})
    prev_c = composite_score({a: prev_scores[a].score for a in ASPECTS})
    composite = {"score": cur_c, "level": level_for(cur_c), "delta": cur_c - prev_c,
                 "trend": trend_for(cur_c - prev_c)}

    all_cur = [e for a in ASPECTS for e in cur_events[a]]
    by_prov: dict[str, list[Event]] = {}
    for e in all_cur:
        if e.province:
            by_prov.setdefault(e.province, []).append(e)
    provinces = []
    for prov, evs in by_prov.items():
        sc = aspect_score(evs, now)
        cats = sorted({e.category for e in evs}, key=ASPECTS.index)
        provinces.append({"province": prov, "score": sc.score, "level": level_for(sc.score),
                          "event_count": len(evs), "categories": cats})
    provinces.sort(key=lambda p: (-p["score"], p["province"]))

    attributions = sorted({m.attribution for e in all_cur for m in e.members if m.attribution})
    return Signals(now=now, groups=groups, current=cur_events, previous=prev_events, now_scores=now_scores,
                   prev_scores=prev_scores, aspects=aspects, composite=composite, provinces=provinces,
                   baseline_ready=baseline_ready, attributions=attributions)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-") or "all"
