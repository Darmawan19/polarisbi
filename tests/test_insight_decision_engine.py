"""Mesin keputusan: sinyal per aspek, penggabungan duplikat, peta panas produk, aturan, endpoint overview."""
import ast
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from insight_testutil import Clock, insert_item, insight_env, utc  # noqa: F401

from insight import db as dbm
from insight import overview as O
from insight import playbook as PB
from insight import products as P
from insight import signals as S
from insight.config import get_settings

NOW = utc(2026, 11, 3, 3, 0, 0)
H = {"X-Requested-With": "polarisbi"}
PW = "Sangat-Kuat-2026"

ROOT = Path(__file__).resolve().parent.parent


def iso(dt):
    return dbm.to_iso(dt)


def add(conn, id, *, category="ekonomi_makro", score=50, hours_ago=1.0, source=None, province=None, title=None,
        minutes_ago=None, meta_json="{}"):
    pub = NOW - (timedelta(minutes=minutes_ago) if minutes_ago is not None else timedelta(hours=hours_ago))
    insert_item(conn, id=id, title=title or f"Kejadian unik {id} kata{id}x", source=source or f"rss.src-{id}",
                score=score, published_at=iso(pub), province=province, category=category, meta_json=meta_json,
                attribution=f"Sumber: {source or id}")


def engine(now=NOW):
    O.invalidate()
    return O.compute(get_settings(), now, use_cache=False)


def conn():
    return dbm.session(get_settings().db_path)


@pytest.fixture(autouse=True)
def _clear_cache():
    O.invalidate()
    yield
    O.invalidate()


# ---------- database kosong ----------

def test_empty_database_all_normal(insight_env):
    e = engine()
    assert all(a["score"] == 0 and a["level"] == "normal" and a["item_count"] == 0 for a in e.signals.aspects)
    assert e.signals.composite == {"score": 0, "level": "normal", "delta": 0, "trend": "stabil"}
    assert e.decisions == [] and O.counts(e) == {"perlu_keputusan": 0, "dipantau": 0, "normal": 7}
    assert e.headline == "Tidak ada keputusan mendesak. Semua aspek normal."
    assert e.signals.provinces == [] and e.signals.baseline_ready is False
    assert [a["aspect"] for a in e.signals.aspects] == list(S.ASPECTS)
    assert all(len(a["sparkline"]) == S.SPARK_DAYS and a["vs_baseline"] is None for a in e.signals.aspects)


# ---------- satu gempa: skor, level, peluruhan ----------

def test_single_quake_score_level_and_decay(insight_env):
    with conn() as c:
        add(c, "q", category="bencana_alam", source="bmkg_quake", score=90, hours_ago=0, province="Sulawesi Tengah")
    e = engine()
    a = e.signals.aspect("bencana_alam")
    assert a["score"] == 90 and a["level"] == "kritis" and a["item_count"] == 1 and a["max_severity"] == "sangat_tinggi"
    assert a["top_event_ids"] == ["q"] and a["delta"] == 90 and a["trend"] == "naik"
    assert e.signals.provinces == [{"province": "Sulawesi Tengah", "score": 90, "level": "kritis", "event_count": 1,
                                    "categories": ["bencana_alam"]}]
    # 12 jam kemudian: 90 x 0.5^(12/24) = 63.6 → 64 (Waspada); 24 jam: jendela berakhir (published == batas bawah)
    assert engine(NOW + timedelta(hours=12)).signals.aspect("bencana_alam")["score"] == 64
    assert engine(NOW + timedelta(hours=23)).signals.aspect("bencana_alam")["level"] == "pantau"   # 46
    assert engine(NOW + timedelta(hours=24)).signals.aspect("bencana_alam")["score"] == 0


def test_levels_and_legend():
    assert [S.level_for(x) for x in (0, 29, 30, 54, 55, 74, 75, 100)] == [
        "normal", "normal", "pantau", "pantau", "waspada", "waspada", "kritis", "kritis"]
    assert S.levels_legend() == [
        {"level": "normal", "label": "Normal", "min": 0, "max": 29},
        {"level": "pantau", "label": "Pantau", "min": 30, "max": 54},
        {"level": "waspada", "label": "Waspada", "min": 55, "max": 74},
        {"level": "kritis", "label": "Kritis", "min": 75, "max": 100}]
    assert S.recency_decay(24) == 0.5 and S.recency_decay(0) == 1.0


# ---------- penggabungan gempa ----------

def _quakes(c, specs):
    for id, src, mag, minutes, score in specs:
        add(c, id, category="bencana_alam", source=src, score=score, minutes_ago=minutes,
            province="Sulawesi Tengah", meta_json=f'{{"magnitude": {mag}}}')


def test_quake_merge_bmkg_usgs(insight_env):
    with conn() as c:
        _quakes(c, [("b1", "bmkg_quake", 6.2, 60, 85), ("u1", "usgs_quake", 6.0, 40, 80)])   # selisih 0.2, 20 mnt
    a = engine().signals
    assert a.aspect("bencana_alam")["item_count"] == 1
    ev = a.current["bencana_alam"][0]
    assert ev.id == "b1" and ev.sources == frozenset({"bmkg_quake", "usgs_quake"})


@pytest.mark.parametrize("specs", [
    [("b1", "bmkg_quake", 6.2, 60, 85), ("u1", "usgs_quake", 5.8, 50, 60)],     # selisih magnitudo 0.4
    [("b1", "bmkg_quake", 6.2, 90, 85), ("u1", "usgs_quake", 6.2, 59, 80)],     # selisih waktu 31 menit
    [("b1", "bmkg_quake", 6.2, 60, 85), ("b2", "bmkg_quake", 6.2, 50, 85)],     # sumber sama → tidak digabung
])
def test_quake_not_merged(insight_env, specs):
    with conn() as c:
        _quakes(c, specs)
    assert engine().signals.aspect("bencana_alam")["item_count"] == 2


# ---------- penggabungan berita mirip (kalibrasi: judul nyata hasil parafrase) ----------

SAME_STORY = [  # tiga media, berita cadangan devisa yang sama (Jaccard 0.78-0.80)
    ("cnbc", "Cadangan Devisa RI Naik Tipis Jadi US$146,8 Miliar pada Oktober 2026"),
    ("cnn", "Cadangan Devisa RI Naik Jadi US$146,8 M pada Oktober 2026"),
    ("lip6", "Cadangan Devisa RI Naik Jadi US$ 146,8 Miliar per Oktober"),
]
DIFFERENT_STORIES = [  # Jaccard 0.56: mirip pola tetapi berita berbeda → tidak boleh digabung pada ambang 0.6
    ("cnbc", "Daftar Terbaru Bunga Deposito Bank Digital per 6 November 2026"),
    ("cnn", "Daftar Terbaru Bank Tutup per 4 November 2026"),
]


def test_similar_news_grouped_across_media_and_sources_counted(insight_env):
    with conn() as c:
        for i, (src, title) in enumerate(SAME_STORY):
            add(c, f"n{i}", category="ekonomi_makro", source=f"rss.{src}", score=40 + i, hours_ago=1 + i, title=title)
        for i, (src, title) in enumerate(DIFFERENT_STORIES):
            add(c, f"d{i}", category="perbankan_bri", source=f"rss.{src}", score=40, hours_ago=1, title=title)
    sig = engine().signals
    makro = sig.current["ekonomi_makro"]
    assert len(makro) == 1 and sig.aspect("ekonomi_makro")["item_count"] == 1
    assert makro[0].id == "n2" and makro[0].score == 42 and len(makro[0].sources) == 3
    assert sig.aspect("perbankan_bri")["item_count"] == 2


def test_grouping_requires_same_category_and_48h_window(insight_env):
    title = SAME_STORY[0][1]
    with conn() as c:
        add(c, "x1", category="ekonomi_makro", source="rss.a", hours_ago=1, title=title)
        add(c, "x2", category="pasar_keuangan", source="rss.b", hours_ago=1, title=title)
    assert engine().signals.aspect("ekonomi_makro")["item_count"] == 1
    t0 = NOW - timedelta(hours=60)
    items = [S.Item(id=str(i), source=f"rss.{i}", base="rss", title=title, url="u", attribution="a",
                    published=t0 + timedelta(hours=h), category="ekonomi_makro", province=None, score=40,
                    magnitude=None, tokens=S.title_tokens(title)) for i, h in enumerate((0, 49))]
    assert len(S.build_groups(items)) == 2          # di luar 48 jam dari anggota pertama
    assert S.jaccard(S.title_tokens(DIFFERENT_STORIES[0][1]), S.title_tokens(DIFFERENT_STORIES[1][1])) < 0.6


# ---------- bonus volume ----------

@pytest.mark.parametrize("n,expected", [(1, 50), (2, 53), (3, 56), (10, 65)])
def test_volume_bonus(insight_env, n, expected):
    with conn() as c:
        for i in range(n):
            add(c, f"v{i}", category="regulasi", score=50, hours_ago=0)
    a = engine().signals.aspect("regulasi")
    assert a["score"] == expected and a["item_count"] == n and a["volume_bonus"] == min(15, 3 * (n - 1))


def test_volume_bonus_ignores_low_effective_scores(insight_env):
    with conn() as c:
        add(c, "hi", category="regulasi", score=60, hours_ago=0)
        add(c, "lo", category="regulasi", score=50, hours_ago=23)    # 50 x 0.5^(23/24) = 25.8 < 30
    assert engine().signals.aspect("regulasi")["score"] == 60


# ---------- delta, tren, komposit ----------

def test_delta_trend_and_composite(insight_env):
    with conn() as c:
        add(c, "old", category="pasar_keuangan", score=60, hours_ago=30)   # jendela pembanding (umur 6 jam di sana)
        add(c, "new", category="pasar_keuangan", score=40, hours_ago=0)
        add(c, "mk", category="ekonomi_makro", score=35, hours_ago=0)
    sig = engine().signals
    pk = sig.aspect("pasar_keuangan")
    prev = S.round_half_up(60 * 0.5 ** (6 / 24))                           # 50
    assert pk["score"] == 40 and pk["delta"] == 40 - prev and pk["trend"] == "turun"
    assert sig.aspect("ekonomi_makro")["trend"] == "naik"
    expected = S.round_half_up(0.6 * 40 + 0.4 * (40 + 35) / 7)             # 28
    assert sig.composite["score"] == expected and sig.composite["level"] == "normal"
    prev_c = S.round_half_up(0.6 * prev + 0.4 * prev / 7)
    assert sig.composite["delta"] == expected - prev_c
    assert [S.trend_for(d) for d in (10, 9, -9, -10)] == ["naik", "stabil", "stabil", "turun"]


def test_baseline_ready_after_seven_days(insight_env):
    with conn() as c:
        add(c, "past", category="regulasi", score=60, hours_ago=24 * 8)
        add(c, "now", category="regulasi", score=60, hours_ago=0)
    a = engine().signals.aspect("regulasi")
    assert a["baseline_ready"] is True and a["vs_baseline"] is not None and a["vs_baseline"] > 0
    assert a["sparkline"][-1] == {"date": "2026-11-03", "score": 60}


# ---------- peta panas produk ----------

def _custom_products(tmp_path, monkeypatch, shares):
    pcsv = tmp_path / "p.csv"
    pcsv.write_text("# uji\nproduct_code,product_name,product_line,channel,active_policies," +
                    ",".join(f"s_{a}" for a in S.ASPECTS) + "\n" +
                    "".join(f"{code},Produk {code},x,y,1000,1,1,1,1,1,1,1\n" for code in shares), encoding="utf-8")
    vcsv = tmp_path / "v.csv"
    lines = ["product_code,province,policies"]
    for code, share in shares.items():
        lines += [f"{code},Aceh,{int(1000 * share)}", f"{code},Jawa Barat,{1000 - int(1000 * share)}"]
    vcsv.write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setenv("INSIGHT_PRODUCT_CSV", str(pcsv))
    monkeypatch.setenv("INSIGHT_PRODUCT_PROVINCE_CSV", str(vcsv))


def test_geo_weighting(insight_env, tmp_path, monkeypatch):
    _custom_products(tmp_path, monkeypatch, {"NOL": 0.0, "SEDIKIT": 0.02, "PENUH": 0.10})
    with conn() as c:
        add(c, "q", category="bencana_alam", source="bmkg_quake", score=80, hours_ago=0, province="Aceh")
        add(c, "w", category="kesehatan_wabah", score=60, hours_ago=0)            # nasional → bobot 1
    cells = {r["product_code"]: r["cells"] for r in engine().matrix}
    assert cells["NOL"]["bencana_alam"] == 0
    assert cells["SEDIKIT"]["bencana_alam"] == S.round_half_up(80 * 0.02 / 0.05)   # 32
    assert cells["PENUH"]["bencana_alam"] == 80
    assert all(cells[k]["kesehatan_wabah"] == 60 for k in cells)


def test_matrix_shape_order_and_demo_catalog(insight_env):
    with conn() as c:
        add(c, "pk", category="pasar_keuangan", score=70, hours_ago=0)
    e = engine()
    assert [r["product_code"] for r in e.matrix][0] == "DEMO-UL"                  # s_pasar_keuangan = 1.0
    assert [r["score"] for r in e.matrix] == sorted((r["score"] for r in e.matrix), reverse=True)
    row = e.matrix[0]
    assert set(row) == {"product_code", "product_name", "product_line", "channel", "active_policies", "score", "level",
                        "delta", "trend", "drivers", "cells", "top_province"}
    assert list(row["cells"]) == list(S.ASPECTS) and row["cells"]["pasar_keuangan"] == 70
    assert row["drivers"][0] == {"aspect": "pasar_keuangan", "value": 70} and len(row["drivers"]) == 2
    assert e.product_data_is_demo is True and len(e.matrix) == 6


def test_demo_csv_totals_match_and_cover_38_provinces():
    prov = P.DemoProductProvider()
    pol = prov.product_province_policies()
    for p in prov.list_products():
        assert sum(pol[p.code].values()) == p.active_policies and len(pol[p.code]) == 38


# ---------- aturan ----------

@pytest.mark.parametrize("aspect", S.ASPECTS)
def test_each_aspect_rule(insight_env, aspect):
    with conn() as c:
        add(c, "e", category=aspect, score=60, hours_ago=0, province="Jawa Barat")
    e = engine()
    assert len(e.decisions) == 1
    d = e.decisions[0]
    rule = PB.RULES_BY_ASPECT[aspect]
    assert d["rule_id"] == rule.rule_id and d["aspect"] == aspect and d["level"] == "perlu_keputusan"
    assert d["is_draft"] is True and d["priority"] == 1 and d["actions"] == list(rule.actions)
    assert d["owner"] == rule.owner and d["evidence"][0]["id"] == "e" and d["provinces"] == ["Jawa Barat"]
    expected_key = f"{rule.rule_id}:jawa-barat" if rule.scope == "province" else f"{rule.rule_id}:all"
    assert d["key"] == expected_key
    if aspect == "bencana_alam":
        assert d["title"] == "Siapkan kesiagaan klaim di Jawa Barat"
    assert "60" in d["why"] and "1 kejadian" in d["why"]
    assert set(d["evidence"][0]) == {"id", "title", "url", "source", "published_at", "score", "severity", "category"}


def test_pantau_level_and_counts(insight_env):
    with conn() as c:
        add(c, "a", category="regulasi", score=40, hours_ago=0)
        add(c, "b", category="ekonomi_makro", score=70, hours_ago=0)
    e = engine()
    assert [(d["aspect"], d["level"]) for d in e.decisions] == [("ekonomi_makro", "perlu_keputusan"),
                                                               ("regulasi", "pantau")]
    assert O.counts(e) == {"perlu_keputusan": 1, "dipantau": 1, "normal": 5}
    assert e.headline.startswith("1 keputusan dibutuhkan: Tinjau dampak kondisi makro")


def test_cross_aspect_rule_priority_ranks_and_stable_keys(insight_env):
    with conn() as c:
        for i, a in enumerate(("regulasi", "pasar_keuangan", "ekonomi_makro")):
            add(c, f"h{i}", category=a, score=60 + 5 * i, hours_ago=0)
        add(c, "p", category="industri_asuransi", score=35, hours_ago=0)
    e1, e2 = engine(), engine()
    d = e1.decisions
    assert d[0]["rule_id"] == "lintas_aspek.eskalasi" and d[0]["title"] == "Eskalasi ke rapat risiko terpadu"
    assert d[0]["level"] == "perlu_keputusan" and d[0]["key"] == "lintas_aspek.eskalasi:all"
    assert [x["priority"] for x in d] == list(range(1, len(d) + 1)) == [1, 2, 3, 4, 5]
    assert [x["aspect"] for x in d[1:]] == ["ekonomi_makro", "pasar_keuangan", "regulasi", "industri_asuransi"]
    assert [x["priority_score"] for x in d] == sorted((x["priority_score"] for x in d), reverse=True)
    assert [x["key"] for x in d] == [x["key"] for x in e2.decisions]
    assert e1.headline.startswith("4 keputusan dibutuhkan: Eskalasi ke rapat risiko terpadu; ")


def test_two_waspada_aspects_no_cross_rule(insight_env):
    with conn() as c:
        add(c, "a", category="regulasi", score=60, hours_ago=0)
        add(c, "b", category="pasar_keuangan", score=60, hours_ago=0)
    assert all(d["rule_id"] != "lintas_aspek.eskalasi" for d in engine().decisions)


def test_spike_flag_raises_order(insight_env):
    with conn() as c:
        add(c, "a", category="regulasi", score=70, hours_ago=0)            # delta +70 → lonjakan
        add(c, "old", category="pasar_keuangan", score=90, hours_ago=25)   # pembanding pasar ~87
        add(c, "b", category="pasar_keuangan", score=72, hours_ago=0)      # skor lebih tinggi, delta negatif
    d = engine().decisions
    assert d[0]["aspect"] == "regulasi" and d[0]["flags"] == ["lonjakan"] and d[1]["flags"] == []


@pytest.mark.parametrize("n_sources,expected", [(1, "rendah"), (2, "sedang"), (3, "tinggi")])
def test_confidence_from_distinct_sources(insight_env, n_sources, expected):
    with conn() as c:
        for i in range(n_sources):     # judul sama → satu kelompok dengan n sumber
            add(c, f"c{i}", category="regulasi", score=60, hours_ago=0, source=f"rss.media{i}",
                title="OJK terbitkan aturan baru pialang asuransi digital")
    d = engine().decisions[0]
    assert d["confidence"] == expected and d["source_count"] == n_sources and len(d["evidence"]) == 1


def test_max_eight_decisions():
    assert PB.MAX_DECISIONS == 8 and len(PB.ASPECT_RULES) == 7


# ---------- tanpa LLM ----------

FORBIDDEN = {"llm", "digest", "auto_digest", "anthropic"}


def _imports(path: Path) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[-1] for a in node.names} | {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            names |= {mod.split(".")[-1], mod.split(".")[0]} | {a.name for a in node.names}
    return names - {""}


def test_signal_product_rule_modules_never_import_llm():
    seen, todo = set(), ["signals", "products", "playbook"]
    while todo:
        mod = todo.pop()
        if mod in seen:
            continue
        seen.add(mod)
        names = _imports(ROOT / "insight" / f"{mod}.py")
        assert not (names & FORBIDDEN), (mod, names & FORBIDDEN)
        todo += [n for n in names if (ROOT / "insight" / f"{n}.py").exists()]


# ---------- endpoint ----------

@pytest.fixture
def app_client(insight_env, tmp_path, monkeypatch):
    from insight import setup_insight
    from polaris_auth import service, setup_auth

    monkeypatch.setenv("POLARIS_AUTH_DB", str(tmp_path / "auth.db"))
    for k in ("POLARIS_BOOTSTRAP_ADMIN_USER", "POLARIS_BOOTSTRAP_ADMIN_PASSWORD", "POLARIS_COOKIE_SECURE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(dbm, "utcnow", Clock(NOW))
    app = FastAPI()
    setup_auth(app)
    setup_insight(app)
    for name, role in (("admin1", "admin"), ("analyst1", "analyst"), ("viewer1", "viewer")):
        service.create_user(name, PW, role)   # pengguna KHUSUS TES di DB sementara
    with TestClient(app, base_url="http://testserver") as c:
        yield c


def login(c, name):
    c.cookies.clear()
    assert c.post("/auth/login", json={"username": name, "password": PW}, headers=H).status_code == 200


OVERVIEW_KEYS = {"generated_at", "window_hours", "composite", "counts", "headline", "aspects", "provinces", "products",
                 "decisions", "baseline_ready", "exposure_is_demo", "product_data_is_demo", "attributions",
                 "degraded_sources", "levels"}


def test_overview_requires_login(app_client):
    assert app_client.get("/api/insight/overview", headers=H).status_code == 401


def test_overview_empty_and_seeded(app_client):
    login(app_client, "viewer1")
    r = app_client.get("/api/insight/overview", headers=H)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == OVERVIEW_KEYS and body["window_hours"] == 24 and body["decisions"] == []
    assert body["counts"] == {"perlu_keputusan": 0, "dipantau": 0, "normal": 7}
    assert body["exposure_is_demo"] is True and body["product_data_is_demo"] is True and len(body["levels"]) == 4
    with conn() as c:
        add(c, "q", category="bencana_alam", source="bmkg_quake", score=90, hours_ago=0, province="Jawa Barat")
    body = app_client.get("/api/insight/overview", headers=H).json()
    assert body["decisions"][0]["key"] == "bencana_alam.kesiagaan_klaim:jawa-barat"
    assert body["attributions"] == ["Sumber: bmkg_quake"] and body["generated_at"] == "2026-11-03T03:00:00Z"


def test_product_detail_and_404(app_client):
    login(app_client, "viewer1")
    with conn() as c:
        add(c, "pk", category="pasar_keuangan", score=70, hours_ago=0)
    r = app_client.get("/api/insight/products/DEMO-UL", headers=H)
    assert r.status_code == 200
    body = r.json()
    assert body["product_code"] == "DEMO-UL" and body["sensitivity"]["pasar_keuangan"] == 1.0
    assert body["product_data_is_demo"] is True and len(body["province_distribution"]) == 38
    assert [d["rule_id"] for d in body["decisions"]] == ["pasar_keuangan.unit_link"]
    nf = app_client.get("/api/insight/products/TIDAK-ADA", headers=H)
    assert nf.status_code == 404 and nf.json()["detail"]["code"] == "product_not_found"


def test_old_endpoints_unchanged(app_client):
    login(app_client, "viewer1")
    feed = app_client.get("/api/insight/feed", headers=H).json()
    assert set(feed) == {"items", "total", "limit", "offset"}
    assert set(app_client.get("/api/insight/exposure", headers=H).json()) == {"is_demo", "rows"}


# ---------- cache: hitung tunggal dan batas baris ----------

def test_concurrent_requests_compute_once(insight_env, monkeypatch):
    import threading

    calls = []
    real = S.compute_signals

    def slow(conn, now):
        calls.append(1)
        import time
        time.sleep(0.2)
        return real(conn, now)

    monkeypatch.setattr(S, "compute_signals", slow)
    s = get_settings()
    threads = [threading.Thread(target=O.compute, args=(s, NOW)) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(calls) == 1


def test_load_items_row_cap_keeps_newest(insight_env, monkeypatch):
    monkeypatch.setattr(S, "MAX_LOAD_ITEMS", 2)
    with conn() as c:
        for i, h in enumerate((5, 3, 1)):
            add(c, f"i{i}", category="regulasi", score=40, hours_ago=h)
        items = S.load_items(c, NOW - timedelta(days=1), NOW)
    assert [i.id for i in items] == ["i1", "i2"]
