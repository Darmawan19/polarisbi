"""Katalog produk BRI Life x risiko: provider produk (DEMO) dan peta panas produk x aspek.

Data produk dan sebaran polis adalah DEMO (fiktif) sampai ada sumber asli. Titik penggantian mengikuti pola
exposure.py: implementasikan ProductExposureProvider, daftarkan di PROVIDERS, lalu pilih lewat
INSIGHT_PRODUCT_PROVIDER. Selama provider adalah Demo, respons wajib memuat product_data_is_demo=true.

Rumus (deterministik, tanpa LLM):
- cell(p, a) = round(sensitivitas(p, a) x skor aspek untuk produk p)
- Aspek geografis (GEO_ASPECTS): skor aspek dihitung ulang dari kejadian (setelah penggabungan) dengan bobot
  per kejadian min(1, share_p / GEO_FULL_SHARE); share_p = porsi polis produk p di provinsi kejadian.
  Kejadian tanpa provinsi (nasional) berbobot 1. Aspek lain memakai skor aspek global.
- score produk = sel tertinggi; level dengan skala sinyal; delta = score sekarang - score 24 jam lalu.
"""
from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Callable, Protocol, runtime_checkable

from . import signals as S
from .config import InsightSettings, get_settings

log = logging.getLogger("insight")

DATA_DIR = Path(__file__).resolve().parent / "data"
DEMO_PRODUCTS_CSV = DATA_DIR / "demo_products.csv"
DEMO_PRODUCT_PROVINCE_CSV = DATA_DIR / "demo_product_province.csv"

GEO_ASPECTS = ("bencana_alam", "kesehatan_wabah")
# Porsi polis produk di provinsi kejadian yang dianggap terdampak penuh (bobot 1). Dikalibrasi dari CSV demo:
# 0,02 adalah nilai terbesar yang membuat gempa berskor efektif 80 menautkan produk berkepekaan tinggi
# (Credit Life 0,7, PA 0,9) di setiap provinsi dengan porsi >= 1,5%, dan tetap tidak menautkan produk di
# provinsi dengan porsi < 0,5%. Nilai lama 0,05 membuat 30 dari 38 provinsi tidak menautkan produk apa pun.
GEO_FULL_SHARE = 0.02
RELATED_CELL_MIN = 40        # produk "terkait" sebuah aspek bila sel >= ini
DRIVERS = 2                  # jumlah aspek pendorong per produk


@dataclass(frozen=True)
class Product:
    code: str
    name: str
    line: str
    channel: str
    active_policies: int
    sensitivity: dict          # {aspek: 0..1}


@runtime_checkable
class ProductExposureProvider(Protocol):
    is_demo: bool

    def list_products(self) -> list[Product]:
        ...

    def product_province_policies(self) -> dict[str, dict[str, int]]:
        """{product_code: {provinsi: jumlah polis}}."""
        ...


def _rows(path: str) -> list[dict]:
    """CSV dengan baris komentar berawalan '#' (diabaikan)."""
    with open(path, encoding="utf-8", newline="") as fh:
        text = "".join(line for line in fh if not line.lstrip().startswith("#"))
    return list(csv.DictReader(io.StringIO(text)))


@lru_cache(maxsize=8)
def _read_products(path: str, mtime: float) -> tuple[Product, ...]:
    out = []
    for r in _rows(path):
        sens = {a: max(0.0, min(1.0, float(r[f"s_{a}"]))) for a in S.ASPECTS}
        out.append(Product(code=r["product_code"].strip(), name=r["product_name"].strip(),
                           line=r["product_line"].strip(), channel=r["channel"].strip(),
                           active_policies=int(r["active_policies"]), sensitivity=sens))
    return tuple(out)


@lru_cache(maxsize=8)
def _read_policies(path: str, mtime: float) -> tuple[tuple[str, str, int], ...]:
    return tuple((r["product_code"].strip(), r["province"].strip(), int(r["policies"])) for r in _rows(path))


class DemoProductProvider:
    """Data fiktif dari insight/data/*.csv (lokasi katalog bisa diganti lewat INSIGHT_PRODUCT_CSV)."""
    is_demo = True

    def __init__(self, products_csv: Path | None = None, province_csv: Path | None = None):
        self.products_csv = Path(products_csv or DEMO_PRODUCTS_CSV)
        self.province_csv = Path(province_csv or DEMO_PRODUCT_PROVINCE_CSV)

    def list_products(self) -> list[Product]:
        return list(_read_products(str(self.products_csv), self.products_csv.stat().st_mtime))

    def product_province_policies(self) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        for code, prov, n in _read_policies(str(self.province_csv), self.province_csv.stat().st_mtime):
            out.setdefault(code, {})[prov] = out.get(code, {}).get(prov, 0) + n
        return out


PROVIDERS: dict[str, Callable[[InsightSettings], ProductExposureProvider]] = {
    "demo": lambda s: DemoProductProvider(s.product_csv, s.product_province_csv),
    # "warehouse": lambda s: WarehouseProductProvider(...),  # nanti: katalog & polis aktif dari data warehouse
}


def get_product_provider(settings: InsightSettings | None = None) -> ProductExposureProvider:
    s = settings or get_settings()
    factory = PROVIDERS.get(s.product_provider)
    if factory is None:
        log.warning("INSIGHT_PRODUCT_PROVIDER=%r tidak dikenal; memakai 'demo'.", s.product_provider)
        factory = PROVIDERS["demo"]
    return factory(s)


def shares(policies: dict[str, int]) -> dict[str, float]:
    total = sum(policies.values())
    return {p: n / total for p, n in policies.items()} if total > 0 else {}


def geo_weight(share: float) -> float:
    return min(1.0, share / GEO_FULL_SHARE)


def _event_weight(share_map: dict[str, float]) -> Callable[[S.Event], float]:
    def w(e: S.Event) -> float:
        return 1.0 if not e.province else geo_weight(share_map.get(e.province, 0.0))
    return w


def product_cells(product: Product, share_map: dict[str, float], events: dict[str, list[S.Event]],
                  global_scores: dict[str, S.AspectScore], ref) -> tuple[dict[str, int], dict[str, S.AspectScore]]:
    """({aspek: sel}, {aspek: AspectScore yang dipakai})."""
    cells, used = {}, {}
    for a in S.ASPECTS:
        sc = S.aspect_score(events[a], ref, _event_weight(share_map)) if a in GEO_ASPECTS else global_scores[a]
        used[a] = sc
        cells[a] = S.round_half_up(product.sensitivity[a] * sc.score)
    return cells, used


def _top_province(product: Product, share_map: dict[str, float], events: dict[str, list[S.Event]], ref) -> str | None:
    best, best_v = None, 0.0
    w = _event_weight(share_map)
    for a in GEO_ASPECTS:
        for e in events[a]:
            if not e.province:
                continue
            v = product.sensitivity[a] * e.effective(ref, w(e))
            if v > best_v or (v == best_v and best is not None and e.province < best):
                best, best_v = e.province, v
    return best if best_v > 0 else None


def heat_matrix(sig: S.Signals, provider: ProductExposureProvider) -> list[dict]:
    """Baris per produk, urut score menurun (seri: urutan katalog). cells urut S.ASPECTS."""
    products = provider.list_products()
    policies = provider.product_province_policies()
    prev_ref = sig.now - timedelta(hours=S.WINDOW_HOURS)
    rows = []
    for idx, p in enumerate(products):
        sm = shares(policies.get(p.code, {}))
        cells, _ = product_cells(p, sm, sig.current, sig.now_scores, sig.now)
        prev_cells, _ = product_cells(p, sm, sig.previous, sig.prev_scores, prev_ref)
        score, prev_score = max(cells.values()), max(prev_cells.values())
        drivers = sorted(S.ASPECTS, key=lambda a: (-cells[a], S.ASPECTS.index(a)))[:DRIVERS]
        delta = score - prev_score
        rows.append({
            "product_code": p.code, "product_name": p.name, "product_line": p.line, "channel": p.channel,
            "active_policies": p.active_policies, "score": score, "level": S.level_for(score), "delta": delta,
            "trend": S.trend_for(delta),
            "drivers": [{"aspect": a, "value": cells[a]} for a in drivers],
            "cells": {a: cells[a] for a in S.ASPECTS},
            "top_province": _top_province(p, sm, sig.current, sig.now),
            "_order": idx,
        })
    rows.sort(key=lambda r: (-r["score"], r["_order"]))
    for r in rows:
        del r["_order"]
    return rows


def related_products(matrix: list[dict], aspect: str) -> list[str]:
    """Kode produk dengan sel aspek >= RELATED_CELL_MIN, urut sel menurun (seri: kode)."""
    hits = [(r["cells"][aspect], r["product_code"]) for r in matrix if r["cells"][aspect] >= RELATED_CELL_MIN]
    return [code for _, code in sorted(hits, key=lambda x: (-x[0], x[1]))]


def product_detail(code: str, sig: S.Signals, provider: ProductExposureProvider, matrix: list[dict]) -> dict | None:
    product = next((p for p in provider.list_products() if p.code == code), None)
    if product is None:
        return None
    row = next(r for r in matrix if r["product_code"] == code)
    policies = provider.product_province_policies().get(code, {})
    total = sum(policies.values())
    dist = sorted(({"province": prov, "policies": n, "share": round(n / total, 4) if total else 0.0}
                   for prov, n in policies.items()), key=lambda d: (-d["policies"], d["province"]))
    return {**row, "sensitivity": dict(product.sensitivity), "province_distribution": dist,
            "product_data_is_demo": bool(provider.is_demo)}
