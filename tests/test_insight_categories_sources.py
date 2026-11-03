"""Ronde 2: kategori pasar_keuangan & perbankan_bri, aturan skor baru, sumber baru terverifikasi, allowlist SSRF,
format INSIGHT_RSS_FEEDS baru, timeout per sumber, degraded, dan kuota per kategori."""
import asyncio

import httpx
import pytest

from insight_testutil import Clock, fixture_bytes, insert_item, insight_env, utc  # noqa: F401

from insight import classify, pipeline
from insight import db as dbm
from insight import digest as D
from insight import scoring_rules as R
from insight.config import get_settings, parse_rss_feeds
from insight.models import CATEGORIES, RawItem, SourceError
from insight.sources import BUILTIN, build_adapters, rss, usgs, worldbank
from insight.sources.base import check_host_allowed, get_bytes, stream_xml_entries


def run(coro):
    return asyncio.run(coro)


def client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.fixture
def clock(monkeypatch):
    c = Clock(utc(2026, 11, 3, 3, 0, 0))
    monkeypatch.setattr(dbm, "utcnow", c)
    return c


# ---------- kategori & klasifikasi ----------

def test_new_categories_registered():
    assert "pasar_keuangan" in CATEGORIES and "perbankan_bri" in CATEGORIES
    assert set(R.CATEGORY_KEYWORDS) == set(CATEGORIES) - {"lainnya"}
    assert set(R.CATEGORY_PRIORITY) == set(CATEGORIES) - {"lainnya"}
    assert set(R.NEWS_CATEGORY_BONUS) == set(CATEGORIES) - {"lainnya"}
    # urutan spesifisitas untuk seri: perbankan_bri → pasar_keuangan → ekonomi_makro
    p = R.CATEGORY_PRIORITY
    assert p.index("perbankan_bri") < p.index("pasar_keuangan") < p.index("ekonomi_makro")


@pytest.mark.parametrize("text,cat", [
    # ekonomi_makro: inflasi, BI-Rate, PDB, neraca perdagangan, kurs rupiah, fiskal
    ("BPS: inflasi Oktober 2,1 persen, PDB tumbuh 5 persen", "ekonomi_makro"),
    ("Bank Indonesia pertahankan BI-Rate di 5,75 persen", "ekonomi_makro"),
    ("Neraca perdagangan surplus, kurs rupiah menguat", "ekonomi_makro"),
    ("Pemerintah perlebar defisit anggaran APBN lewat kebijakan fiskal", "ekonomi_makro"),
    # pasar_keuangan: IHSG, saham, obligasi/SBN, reksa dana, volatilitas, modal asing, trading halt
    ("IHSG ditutup melemah, investor asing catat jual bersih", "pasar_keuangan"),
    ("BEI berlakukan trading halt setelah indeks anjlok", "pasar_keuangan"),
    ("Yield obligasi SBN naik, reksa dana pendapatan tetap tertekan", "pasar_keuangan"),
    ("Aliran modal asing keluar, volatilitas pasar meningkat", "pasar_keuangan"),
    # perbankan_bri: Grup BRI + perbankan nasional
    ("Laba BRI kuartal III naik", "perbankan_bri"),
    ("Saham BBRI menguat", "perbankan_bri"),                          # entitas BRI (3) > saham (1)
    ("Penyaluran KUR Bank Rakyat Indonesia capai target", "perbankan_bri"),
    ("BRI Life luncurkan produk asuransi jiwa baru", "perbankan_bri"),
    ("NPL perbankan naik, likuiditas bank mengetat", "perbankan_bri"),
    ("Suku bunga kredit perbankan turun", "perbankan_bri"),
])
def test_new_category_keywords(text, cat):
    assert classify.classify_category("gdelt", text) == cat


@pytest.mark.parametrize("text,cat", [
    ("saham bank", "perbankan_bri"),          # 1 vs 1 → perbankan_bri lebih spesifik
    ("saham dan inflasi", "pasar_keuangan"),  # 1 vs 1 → pasar_keuangan lebih spesifik dari ekonomi_makro
    ("kredit dan inflasi", "perbankan_bri"),  # 1 vs 1 → perbankan_bri
    ("inflasi asuransi", "industri_asuransi"),  # urutan lama dipertahankan untuk kategori lain
])
def test_tie_breaks_by_specificity(text, cat):
    hits = classify.matched_categories(text)
    assert len(set(hits.values())) == 1          # benar-benar seri
    assert classify.classify_category("gdelt", text) == cat


def test_highest_total_weight_wins_over_specificity():
    # ekonomi_makro: inflasi(1) + bi rate(2) + rupiah(1) = 4 > perbankan_bri: kredit(1)
    text = "Inflasi naik, BI rate dan rupiah jadi sorotan, kredit melambat"
    hits = classify.matched_categories(text)
    assert hits["ekonomi_makro"] == 4 and hits["perbankan_bri"] == 1
    assert classify.classify_category("gdelt", text) == "ekonomi_makro"


def test_longest_phrase_counted_once():
    assert classify.matched_categories("suku bunga kredit")["perbankan_bri"] == 2
    assert classify.weighted_hits("BRI Life", R.CATEGORY_KEYWORDS["perbankan_bri"]) == 3


def test_source_fixed_and_default_categories():
    assert classify.classify_category("usgs_quake", "OJK inflasi") == "bencana_alam"
    # kategori bawaan hanya dipakai bila kata kunci tidak cocok
    assert classify.classify_category("kemkes_rilis", "Kemenkes perkuat SDM kesehatan") == "kesehatan_wabah"
    assert classify.classify_category("kemkes_rilis", "Inflasi naik, BI rate turun") == "ekonomi_makro"
    # satu kata umum berbobot 1 tidak cukup untuk mengalahkan kategori bawaan sumber (DEFAULT_OVERRIDE_MIN_WEIGHT)
    assert classify.classify_category("kemkes_rilis", "Inflasi naik") == "kesehatan_wabah"
    assert classify.classify_category("kemkes_rilis", "Syarat kredit SKP dokter jadi 160") == "kesehatan_wabah"
    assert classify.classify_category("gdelt", "Syarat kredit SKP dokter jadi 160") == "perbankan_bri"
    assert classify.classify_category("worldbank_id", "Social forestry program") == "ekonomi_makro"
    assert classify.classify_category("rss.kontan", "Berita umum", "pasar_keuangan") == "pasar_keuangan"
    assert classify.classify_category("rss.kontan", "Berita umum") == "lainnya"


# ---------- aturan skor baru ----------

@pytest.mark.parametrize("text,rule,score", [
    ("BI Rate naik 25 bps", "keputusan_bi_rate", 25 + 15 + 15),
    ("Bank Indonesia pertahankan BI-Rate", "keputusan_bi_rate", 25 + 15 + 15),
    ("IHSG anjlok 4 persen", "ihsg_turun_tajam", 25 + 15 + 25),
    ("BEI lakukan trading halt", "trading_halt", 25 + 15 + 30),
    ("OJK jatuhkan sanksi denda kepada perusahaan pembiayaan", "sanksi_ojk", 25 + 20 + 20),
    ("Laba BRI turun 5 persen", "material_grup_bri", 25 + 15 + 15),
    ("Layanan BRImo gangguan sejak pagi", "material_grup_bri", 25 + 15 + 15),
    ("BPR di Bali dilikuidasi LPS", "gangguan_penutupan_bank", 25 + 15 + 25 + 5),
])
def test_news_event_rules(text, rule, score):
    assert rule in [r.name for r in classify.matched_event_rules(text)]
    province = classify.detect_province(text)
    assert classify.score_news(text, province) == score


def test_event_rules_take_single_highest_bonus_and_cap():
    t = "IHSG anjlok, BEI berlakukan trading halt"          # ihsg_turun_tajam (25) & trading_halt (30)
    assert {r.name for r in classify.matched_event_rules(t)} == {"ihsg_turun_tajam", "trading_halt"}
    assert classify.score_news(t, None) == 25 + 15 + 30
    assert classify.score_news("Pertandingan sepak bola", None) == 25     # tanpa aturan
    assert classify.score_news("BI rate dibahas", None) == 25 + 15        # grup kedua tidak cocok


def test_event_rules_are_data():
    assert all(isinstance(r, R.NewsEventRule) and r.groups and r.bonus > 0 for r in R.NEWS_EVENT_RULES)
    assert len({r.name for r in R.NEWS_EVENT_RULES}) == len(R.NEWS_EVENT_RULES)


def test_prepare_uses_default_category_and_new_scores(clock):
    now = utc(2026, 11, 3)
    row = pipeline.prepare(RawItem(source="worldbank_id", source_label="WB", attribution="Sumber: World Bank",
                                   title="Jobs program", url="https://www.worldbank.org/x", published_at=now,
                                   default_category="ekonomi_makro"), now)
    assert row["category"] == "ekonomi_makro" and row["score"] == 25
    row = pipeline.prepare(RawItem(source="rss.kontan", source_label="Kontan", attribution="Sumber: Kontan",
                                   title="IHSG anjlok tajam", url="https://kontan.example/x", published_at=now,
                                   default_category="ekonomi_makro"), now)
    assert row["category"] == "pasar_keuangan" and row["score"] == 65


def test_feed_filter_accepts_new_categories(insight_env):
    from insight.router import feed
    with dbm.session(get_settings().db_path) as conn:
        insert_item(conn, id="p1", category="pasar_keuangan", published_at="2026-11-03T00:00:00Z")
        insert_item(conn, id="b1", category="perbankan_bri", published_at="2026-11-03T00:00:00Z")
    assert [i["id"] for i in feed("pasar_keuangan", None, None, None, 50, 0)["items"]] == ["p1"]
    assert [i["id"] for i in feed("perbankan_bri", None, None, None, 50, 0)["items"]] == ["b1"]


# ---------- sumber baru (fixture nyata) ----------

def test_usgs_parses_real_fixture_and_filters_indonesia():
    items = usgs.parse_geojson(fixture_bytes("usgs_4.5_week.geojson"))
    assert len(items) == 3                                   # 2 gempa di luar Indonesia dibuang
    first = items[0]
    assert first.title == "M 5.1 - 19 km WNW of Tomohon, Indonesia"
    assert first.url == "https://earthquake.usgs.gov/earthquakes/eventpage/us7000tuuy"
    assert first.meta["magnitude"] == 5.1 and round(first.meta["depth_km"]) == 197 and first.meta["tsunami"] is False
    assert first.published_at.isoformat().startswith("2026-")
    assert first.category == "bencana_alam" and first.attribution == "Sumber: USGS"
    row = pipeline.prepare(items[1], utc(2026, 11, 3))       # M5.0, kedalaman 10 km → 60 + 5
    assert row["category"] == "bencana_alam" and row["score"] == 65 and row["dedupe_key"] is None


def test_usgs_rejects_non_json():
    with pytest.raises(SourceError):
        usgs.parse_geojson(b"<html>")


def test_kemkes_stream_parses_real_fixture(insight_env):
    data = fixture_bytes("kemkes_rilis_berita.xml")
    seen = []

    def handler(req):
        seen.append(str(req.url))
        return httpx.Response(200, content=data, headers={"content-type": "application/xml"})

    async def go():
        async with client(handler) as c:
            return await rss.KemkesRilisAdapter().fetch(c)

    items = run(go())
    assert seen == [rss.KEMKES_RSS_URL]
    assert [i.title for i in items][:1] == ["Pemberian Obat Pencegahan TBC di DKI Jakarta Meningkat Lima Kali Lipat"]
    assert len(items) == 3 and all(i.url.startswith("https://kemkes.go.id/id/") for i in items)
    assert items[0].attribution == "Sumber: Kementerian Kesehatan RI"
    row = pipeline.prepare(items[0], utc(2026, 11, 3))
    assert row["category"] == "kesehatan_wabah" and row["province"] == "DKI Jakarta"
    assert "<" not in row["snippet"]
    assert rss.KemkesRilisAdapter.slow is True


def test_stream_stops_after_max_items_and_rejects_entity():
    body = (b'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>'
            + b"".join(b"<item><title>Banjir %d</title><link>https://kemkes.go.id/id/a%d</link></item>" % (n, n)
                       for n in range(500)) + b"</channel></rss>")

    async def go(content, **kw):
        async with client(lambda r: httpx.Response(200, content=content)) as c:
            return await stream_xml_entries(c, "https://kemkes.go.id/id/rss/x", **kw)

    assert len(run(go(body, max_items=40))) == 40
    bomb = b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa">]><rss><channel></channel></rss>'
    with pytest.raises(SourceError):
        run(go(bomb))


def test_worldbank_parses_real_fixture():
    items = worldbank.parse_news(fixture_bytes("worldbank_news_id.json"))
    assert len(items) == 3                                   # "facets" diabaikan
    assert items[0].title.startswith("Social Forestry in Indonesia")
    assert all(i.url.startswith("https://www.worldbank.org/") for i in items)   # http → https
    assert items[0].published_at.isoformat() == "2026-06-04T20:14:09+00:00"
    assert items[0].default_category == "ekonomi_makro" and items[0].attribution == "Sumber: World Bank"


def test_worldbank_rejects_unknown_format():
    with pytest.raises(SourceError):
        worldbank.parse_news(b'{"rows": 0}')


def test_new_builtin_sources_enabled_by_default(insight_env):
    s = get_settings()
    assert {"usgs_quake", "kemkes_rilis", "worldbank_id"} <= set(s.sources)
    assert set(BUILTIN) == set(s.sources)
    assert s.rss_feeds == ()                                 # media komersial: bawaan kosong
    names = [a.name for a in build_adapters(s)]
    assert names == list(s.sources)


# ---------- INSIGHT_RSS_FEEDS ----------

def test_rss_feeds_new_and_old_formats():
    feeds = parse_rss_feeds(
        "https://www.kontan.co.id/rss; https://www.cnbcindonesia.com/market/rss|pasar_keuangan;"
        " Antara=https://www.antaranews.com/rss/ekonomi.xml|ekonomi_makro; Lama=https://example.org/rss?a=b;"
        " https://bisnis.example/rss|bukan_kategori; https://127.0.0.1/rss; http://localhost/rss;"
        " https://10.0.0.5/feed; Bad=file:///etc/passwd")
    got = [(f.key, f.label, f.url, f.category) for f in feeds]
    assert got == [
        ("rss.kontan-co-id", "kontan.co.id", "https://www.kontan.co.id/rss", None),
        ("rss.cnbcindonesia-com", "cnbcindonesia.com", "https://www.cnbcindonesia.com/market/rss", "pasar_keuangan"),
        ("rss.antara", "Antara", "https://www.antaranews.com/rss/ekonomi.xml", "ekonomi_makro"),
        ("rss.lama", "Lama", "https://example.org/rss?a=b", None),
    ]


def test_rss_feed_category_used_as_default(insight_env):
    feed = parse_rss_feeds("https://feeds.example/rss|perbankan_bri")[0]
    xml = (b'<?xml version="1.0"?><rss><channel><item><title>Berita umum</title><link>https://feeds.example/1</link>'
           b"</item><item><title>IHSG anjlok</title><link>https://feeds.example/2</link></item></channel></rss>")

    async def go():
        async with client(lambda r: httpx.Response(200, content=xml)) as c:
            return await rss.RssAdapter(feed).fetch(c)

    rows = [pipeline.prepare(i, utc(2026, 11, 3)) for i in run(go())]
    assert [r["category"] for r in rows] == ["perbankan_bri", "pasar_keuangan"]


# ---------- SSRF: daftar domain ----------

def test_allowlist_blocks_unknown_hosts_and_ips():
    check_host_allowed("https://earthquake.usgs.gov/x")
    check_host_allowed("https://feeds.example/rss", allow_hosts=("feeds.example",))
    for bad in ("https://evil.example/x", "https://169.254.169.254/latest", "http://localhost/x",
                "https://127.0.0.1/x", "file:///etc/passwd", "https://kemkes.go.id.evil.example/x"):
        with pytest.raises(SourceError):
            check_host_allowed(bad)
    with pytest.raises(SourceError):   # IP tetap ditolak walau "diizinkan" eksplisit
        check_host_allowed("https://10.0.0.1/x", allow_hosts=("10.0.0.1",))


def test_redirect_to_foreign_host_is_not_followed():
    hits = []

    def handler(req):
        hits.append(req.url.host)
        if req.url.host == "earthquake.usgs.gov":
            return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data"})
        return httpx.Response(200, content=b"secret")

    async def go():
        async with client(handler) as c:
            return await get_bytes(c, usgs.FEED_URL, label="USGS")

    with pytest.raises(SourceError):
        run(go())
    assert hits == ["earthquake.usgs.gov"]


def test_redirect_within_allowlist_is_followed():
    def handler(req):
        if req.url.path == "/old":
            return httpx.Response(301, headers={"location": "/earthquakes/feed/v1.0/summary/4.5_week.geojson"})
        return httpx.Response(200, content=b"ok")

    async def go():
        async with client(handler) as c:
            return await get_bytes(c, "https://earthquake.usgs.gov/old")

    assert run(go()) == b"ok"


# ---------- timeout per sumber & degraded ----------

class FakeAdapter:
    def __init__(self, name, items=(), delay=0.0, timeout=None, degraded=None, slow=False):
        self.name, self.label, self.attribution = name, name, f"Sumber: {name}"
        self._items, self._delay, self.degraded_reason, self.slow = list(items), delay, degraded, slow
        if timeout is not None:
            self.timeout_seconds = timeout

    async def fetch(self, client):
        if self._delay:
            await asyncio.sleep(self._delay)
        return list(self._items)


def raw(source, title, url):
    return RawItem(source=source, source_label=source, attribution=f"Sumber: {source}", title=title, url=url,
                   published_at=utc(2026, 11, 3, 2))


def test_per_source_timeout_isolated(insight_env, clock):
    fast = FakeAdapter("gdelt", [raw("gdelt", "Banjir di Riau", "https://n.example/1")])
    slow = FakeAdapter("usgs_quake", delay=1.0, timeout=0.05)
    res = run(pipeline.refresh(get_settings(), adapters=[fast, slow]))
    by = {r["source"]: r for r in res["results"]}
    assert by["gdelt"]["ok"] and by["gdelt"]["new_items"] == 1
    assert not by["usgs_quake"]["ok"] and "batas waktu sumber" in by["usgs_quake"]["error"]


def test_degraded_recorded_and_exposed_in_sources(insight_env, clock):
    a = FakeAdapter("gdelt", degraded="GDELT membatasi laju (HTTP 429)")
    res = run(pipeline.refresh(get_settings(), adapters=[a]))
    r = res["results"][0]
    assert r["ok"] is True and r["error"] is None and r["degraded"] is True
    from insight.router import sources
    by = {x["source"]: x for x in sources()}
    assert by["gdelt"]["degraded"] is True and "429" in by["gdelt"]["degraded_reason"]
    assert by["gdelt"]["status"] != "error"
    # siklus berikutnya normal → penanda hilang
    run(pipeline.refresh(get_settings(), adapters=[FakeAdapter("gdelt")]))
    by = {x["source"]: x for x in sources()}
    assert by["gdelt"]["degraded"] is False and by["gdelt"]["degraded_reason"] is None


# ---------- kuota per kategori di brief ----------

def test_digest_quota_represents_all_aspects(insight_env, clock):
    with dbm.session(get_settings().db_path) as conn:
        for n in range(10):   # bencana mendominasi skor
            insert_item(conn, id=f"q{n}", score=90 - n, category="bencana_alam", published_at="2026-11-03T01:00:00Z")
        insert_item(conn, id="pk", score=45, category="pasar_keuangan", published_at="2026-11-03T01:00:00Z")
        insert_item(conn, id="bri", score=40, category="perbankan_bri", published_at="2026-11-03T01:00:00Z")
        s, e = D.window("daily", utc(2026, 11, 3, 3))
        items = D.select_items(conn, s, e)
    ids = [i["id"] for i in items]
    assert ids == ["q0", "q1", "q2", "q3", "pk", "bri"]
    content = D.annotate_content({"executive_summary": "x", "key_events": [{"text": "t", "item_ids": ["pk"]}],
                                  "impact_note": "", "watchlist": []}, items)
    assert content["key_events"][0]["category"] == "pasar_keuangan"
    assert content["aspects"] == [{"category": "bencana_alam", "items": 4, "max_score": 90},
                                  {"category": "pasar_keuangan", "items": 1, "max_score": 45},
                                  {"category": "perbankan_bri", "items": 1, "max_score": 40}]
