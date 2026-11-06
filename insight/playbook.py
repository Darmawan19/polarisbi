"""Rekomendasi keputusan berbasis aturan (DRAF untuk ditinjau manusia; is_draft=true). Tanpa LLM.

- Setiap aspek dengan level >= Pantau menghasilkan satu keputusan lewat aturannya (ASPECT_RULES).
  Level aspek Waspada/Kritis → "perlu_keputusan"; Pantau → "pantau".
- Aturan lintas aspek (CROSS_RULE): bila >= CROSS_MIN_ASPECTS aspek berlevel Waspada atau lebih.
- Lonjakan: delta aspek >= SPIKE_DELTA → flag "lonjakan" dan bonus urutan.
- priority_score = LEVEL_WEIGHT[level aspek] x 1000 + skor aspek x 10 + bonus lonjakan.
  priority (di respons) = PERINGKAT 1, 2, 3, ... dari priority_score menurun (seri: key), tanpa lubang.
- confidence dari jumlah sumber berbeda pada kejadian bukti (kelompok yang sudah digabung):
  >= 3 tinggi, 2 sedang, 1 rendah.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import products as P
from . import signals as S

LEVEL_WEIGHT = {"pantau": 1, "waspada": 2, "kritis": 3}
CROSS_WEIGHT = 9             # aturan lintas aspek selalu di urutan teratas
PRIORITY_LEVEL_FACTOR = 1000
PRIORITY_SCORE_FACTOR = 10
SPIKE_DELTA = 25
SPIKE_BONUS = 500
CROSS_MIN_ASPECTS = 3
MAX_DECISIONS = 8
MAX_EVIDENCE = 5
MAX_PROVINCES = 5
CONFIDENCE_HIGH_SOURCES = 3
CONFIDENCE_MEDIUM_SOURCES = 2

DECISION_LEVEL = {"pantau": "pantau", "waspada": "perlu_keputusan", "kritis": "perlu_keputusan"}
HORIZON_LABELS = {"hari_ini": "hari ini", "7_hari": "7 hari", "30_hari": "30 hari"}


@dataclass(frozen=True)
class Rule:
    rule_id: str
    aspect: str | None
    title: str                       # boleh memuat {provinsi}
    actions: tuple[str, ...]
    owner: str
    horizon: str                     # kunci HORIZON_LABELS
    scope: str = "all"               # "province" → key memakai provinsi teratas


ASPECT_RULES: tuple[Rule, ...] = (
    Rule("bencana_alam.kesiagaan_klaim", "bencana_alam", "Siapkan kesiagaan klaim di {provinsi}", (
        "Aktifkan pemantauan klaim dan kematian dari wilayah terdampak.",
        "Siapkan jalur klaim darurat dan komunikasi ke cabang bank dan mitra.",
        "Tinjau akumulasi risiko produk terkait di wilayah terdampak.",
    ), "Klaim dan Risk Management", "hari_ini", scope="province"),
    Rule("kesehatan_wabah.kesiapan_klaim", "kesehatan_wabah",
         "Tinjau kesiapan klaim kesehatan dan kematian akibat wabah", (
             "Pantau tren klaim rawat inap dan meninggal.",
             "Tinjau ketentuan underwriting untuk kelompok dan proteksi.",
             "Siapkan komunikasi ke mitra korporasi.",
         ), "Aktuaria, Underwriting, Klaim", "7_hari"),
    Rule("ekonomi_makro.asumsi_kredit", "ekonomi_makro",
         "Tinjau dampak kondisi makro terhadap asumsi dan kualitas kredit", (
             "Evaluasi asumsi investasi dan lapse.",
             "Pantau kualitas kredit debitur untuk Credit Life.",
             "Siapkan skenario sensitivitas untuk rapat risiko.",
         ), "Aktuaria dan Risk", "7_hari"),
    Rule("pasar_keuangan.unit_link", "pasar_keuangan", "Pantau dana Unit-Link dan portofolio investasi", (
        "Pantau NAB dan arus penebusan.",
        "Siapkan komunikasi nasabah unit-link.",
        "Laporkan ke komite investasi.",
    ), "Investasi dan Distribusi", "hari_ini"),
    Rule("regulasi.dampak_peraturan", "regulasi", "Analisis dampak peraturan baru terhadap produk dan proses", (
        "Petakan ketentuan baru ke produk terkait.",
        "Tetapkan penanggung jawab kepatuhan dan tenggat.",
        "Siapkan rencana penyesuaian.",
    ), "Kepatuhan, Legal, pemilik produk", "30_hari"),
    Rule("industri_asuransi.kompetitor", "industri_asuransi", "Cermati perkembangan industri dan kompetitor", (
        "Tinjau implikasi terhadap strategi produk dan harga.",
        "Bagikan ringkasan ke tim produk dan distribusi.",
    ), "Produk dan Strategi", "30_hari"),
    Rule("perbankan_bri.grup_bri", "perbankan_bri", "Pantau perkembangan Grup BRI dan perbankan nasional", (
        "Tinjau dampak pada pipeline Credit Life dan Bancassurance.",
        "Koordinasi dengan tim kemitraan bank.",
    ), "Distribusi Bancassurance dan Risk", "7_hari"),
)
RULES_BY_ASPECT = {r.aspect: r for r in ASPECT_RULES}

CROSS_RULE = Rule("lintas_aspek.eskalasi", None, "Eskalasi ke rapat risiko terpadu", (
    "Konsolidasi dampak lintas aspek.",
    "Putuskan langkah mitigasi terpadu.",
), "Direksi dan Risk", "hari_ini")

NO_PROVINCE_LABEL = "wilayah terdampak"


def confidence(n_sources: int) -> str:
    if n_sources >= CONFIDENCE_HIGH_SOURCES:
        return "tinggi"
    if n_sources >= CONFIDENCE_MEDIUM_SOURCES:
        return "sedang"
    return "rendah"


def _provinces(ranked: list[tuple[float, S.Event]]) -> list[str]:
    out: list[str] = []
    for _, e in ranked:
        if e.province and e.province not in out:
            out.append(e.province)
    return out[:MAX_PROVINCES]


def _why(aspect: dict, n_products: int, provinces: list[str]) -> str:
    prov = f" Provinsi teratas: {', '.join(provinces[:3])}." if provinces else ""
    return (f"Skor {aspect['label'].lower()} {aspect['score']} ({S.LEVEL_LABELS[aspect['level']]}), "
            f"{aspect['item_count']} kejadian dalam {S.WINDOW_HOURS} jam, delta {aspect['delta']:+d} dibanding "
            f"{S.WINDOW_HOURS} jam sebelumnya.{prov} {n_products} produk terkait.")


def _decision(rule: Rule, *, level: str, priority_score: int, title: str, why: str, scope: str,
              provinces: list[str], product_codes: list[str], evidence_events: list[S.Event], flags: list[str],
              aspect: str | None) -> dict:
    n_sources = len({s for e in evidence_events for s in e.sources})
    return {
        "key": f"{rule.rule_id}:{scope}", "rule_id": rule.rule_id, "level": level, "priority": 0,
        "priority_score": priority_score, "title": title, "why": why, "actions": list(rule.actions),
        "owner": rule.owner, "horizon": rule.horizon, "horizon_label": HORIZON_LABELS[rule.horizon],
        "confidence": confidence(n_sources) if evidence_events else "rendah", "source_count": n_sources,
        "flags": flags, "aspect": aspect, "provinces": provinces, "product_codes": product_codes,
        "evidence": [e.evidence() for e in evidence_events], "is_draft": True,
    }


def build_decisions(sig: S.Signals, matrix: list[dict]) -> list[dict]:
    decisions: list[dict] = []
    for a in S.ASPECTS:
        asp = sig.aspect(a)
        if S.level_rank(asp["level"]) < S.level_rank("pantau"):
            continue
        rule = RULES_BY_ASPECT[a]
        ranked = sig.now_scores[a].ranked
        provinces = _provinces(ranked)
        codes = P.related_products(matrix, a)
        spike = asp["delta"] >= SPIKE_DELTA
        if rule.scope == "province" and provinces:
            title, scope = rule.title.format(provinsi=provinces[0]), S.slug(provinces[0])
        else:
            title, scope = rule.title.format(provinsi=NO_PROVINCE_LABEL), "all"
        ps = (LEVEL_WEIGHT[asp["level"]] * PRIORITY_LEVEL_FACTOR + asp["score"] * PRIORITY_SCORE_FACTOR
              + (SPIKE_BONUS if spike else 0))
        decisions.append(_decision(
            rule, level=DECISION_LEVEL[asp["level"]], priority_score=ps, title=title,
            why=_why(asp, len(codes), provinces), scope=scope, provinces=provinces, product_codes=codes,
            evidence_events=[e for _, e in ranked[:MAX_EVIDENCE]], flags=["lonjakan"] if spike else [], aspect=a))

    hot = [a for a in S.ASPECTS if S.level_rank(sig.aspect(a)["level"]) >= S.level_rank("waspada")]
    if len(hot) >= CROSS_MIN_ASPECTS:
        ranked = sorted((x for a in hot for x in sig.now_scores[a].ranked), key=lambda x: (-x[0], x[1].id))
        provinces = _provinces(ranked)
        codes = sorted({c for a in hot for c in P.related_products(matrix, a)},
                       key=lambda c: next(i for i, r in enumerate(matrix) if r["product_code"] == c))
        labels = ", ".join(f"{sig.aspect(a)['label'].lower()} {sig.aspect(a)['score']}" for a in hot)
        comp = sig.composite
        why = (f"{len(hot)} aspek berlevel Waspada atau lebih ({labels}). Indeks komposit {comp['score']} "
               f"({S.LEVEL_LABELS[comp['level']]}), delta {comp['delta']:+d}. {len(codes)} produk terkait.")
        decisions.append(_decision(
            CROSS_RULE, level="perlu_keputusan",
            priority_score=CROSS_WEIGHT * PRIORITY_LEVEL_FACTOR + comp["score"] * PRIORITY_SCORE_FACTOR,
            title=CROSS_RULE.title, why=why, scope="all", provinces=provinces, product_codes=codes,
            evidence_events=[e for _, e in ranked[:MAX_EVIDENCE]], flags=[], aspect=None))

    decisions.sort(key=lambda d: (-d["priority_score"], d["key"]))
    decisions = decisions[:MAX_DECISIONS]
    for i, d in enumerate(decisions, start=1):
        d["priority"] = i
    return decisions


def headline(decisions: list[dict]) -> str:
    need = [d for d in decisions if d["level"] == "perlu_keputusan"]
    watch = [d for d in decisions if d["level"] == "pantau"]
    if need:
        return f"{len(need)} keputusan dibutuhkan: " + "; ".join(d["title"] for d in need)
    if watch:
        return f"Tidak ada keputusan mendesak. {len(watch)} aspek dipantau."
    return "Tidak ada keputusan mendesak. Semua aspek normal."
