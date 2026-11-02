"""Parser tiap sumber dari fixture nyata + aturan pengambilan CAP BMKG."""
import asyncio
import json
import re

import httpx
import pytest

from insight_testutil import fixture_bytes, insight_env, no_sleep  # noqa: F401

from insight import db as dbm
from insight.config import RssFeed, get_settings
from insight.models import SourceError
from insight.sources import bmkg_quake, bmkg_weather, gdelt, rss, who_don


def run(coro):
    return asyncio.run(coro)


def client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# ---------- BMKG gempa ----------

def test_bmkg_quake_parses_real_fixture_and_merges_lists():
    calls = []

    def handler(req):
        calls.append(str(req.url))
        name = "bmkg_gempaterkini.json" if "gempaterkini" in str(req.url) else "bmkg_gempadirasakan.json"
        return httpx.Response(200, content=fixture_bytes(name))

    async def go():
        async with client(handler) as c:
            return await bmkg_quake.BmkgQuakeAdapter().fetch(c)

    items = run(go())
    assert len(calls) == 2
    # 6 (terkini) + 4 (dirasakan) - 2 kejadian yang sama = 8
    assert len(items) == 8
    tomohon = [i for i in items if "TOMOHON" in i.title]
    assert len(tomohon) == 1
    t = tomohon[0]
    assert t.meta["magnitude"] == 5.3 and t.meta["depth_km"] == 148 and t.meta["tsunami"] is False
    assert t.province == "Sulawesi Utara"
    assert "Dirasakan" in t.snippet and "Tidak berpotensi tsunami" in t.snippet
    assert t.published_at.isoformat() == "2026-11-02T08:13:10+00:00"
    assert t.url.startswith("https://www.bmkg.go.id/gempabumi/")
    assert {i.attribution for i in items} == {"Sumber: BMKG"}
    provs = {i.title.split(" - ", 1)[1]: i.province for i in items}
    assert provs["153 km Tenggara OKSIBIL-PAPUAPGNGN"] == "Papua Pegunungan"
    assert provs["201 km BaratLaut TANIMBAR"] is None


def test_bmkg_quake_one_list_failing_still_returns_other():
    def handler(req):
        if "gempaterkini" in str(req.url):
            return httpx.Response(500)
        return httpx.Response(200, content=fixture_bytes("bmkg_gempadirasakan.json"))

    async def go():
        async with client(handler) as c:
            return await bmkg_quake.BmkgQuakeAdapter().fetch(c)

    assert len(run(go())) == 4


def test_bmkg_quake_both_failing_raises():
    async def go():
        async with client(lambda r: httpx.Response(503)) as c:
            return await bmkg_quake.BmkgQuakeAdapter().fetch(c)

    with pytest.raises(SourceError):
        run(go())


def test_tsunami_flag():
    assert bmkg_quake._tsunami("Berpotensi tsunami") is True
    assert bmkg_quake._tsunami("Tidak berpotensi tsunami") is False


# ---------- BMKG cuaca + CAP ----------

def _rss_with(n: int, link_fmt="https://www.bmkg.go.id/alerts/nowcast/id/CXX{i:03d}_alert.xml") -> bytes:
    real = fixture_bytes("bmkg_nowcast_rss.xml").decode("utf-8")
    first = re.search(r"<item>.*?</item>", real, re.S).group(0)
    items = []
    for i in range(n):
        it = re.sub(r"<guid([^>]*)>.*?</guid>", rf"<guid\1>guid-{i}</guid>", first, flags=re.S)
        it = re.sub(r"<link>.*?</link>", f"<link>{link_fmt.format(i=i)}</link>", it, flags=re.S)
        items.append(it)
    head = real[: real.find("<item>")]
    tail = real[real.rfind("</item>") + len("</item>"):]
    return (head + "\n".join(items) + tail).encode("utf-8")


def _cap(severity="Moderate") -> bytes:
    return fixture_bytes("bmkg_cap_moderate.xml").replace(b"<severity>Moderate</severity>",
                                                          f"<severity>{severity}</severity>".encode())


def _weather(handler, settings=None):
    s = settings or get_settings()
    a = bmkg_weather.BmkgWeatherAdapter(s, sleep=no_sleep)

    async def go():
        async with client(handler) as c:
            return await a.fetch(c)

    return a, run(go())


def test_bmkg_weather_real_fixture_with_cap(insight_env):
    cap_urls = []

    def handler(req):
        u = str(req.url)
        if u == bmkg_weather.RSS_URL:
            return httpx.Response(200, content=fixture_bytes("bmkg_nowcast_rss.xml"))
        cap_urls.append(u)
        return httpx.Response(200, content=fixture_bytes("bmkg_cap_moderate.xml"))

    a, items = _weather(handler)
    assert len(items) == 4 and len(cap_urls) == 4
    assert all(u.startswith(bmkg_weather.CAP_BASE) and u.endswith("_alert.xml") for u in cap_urls)
    first = items[0]
    assert first.title == "Hujan Lebat disertai Petir di Sulawesi Barat"
    assert first.province == "Sulawesi Barat"
    assert first.severity_verified is True and first.meta["cap_severity"] == "Moderate"
    assert first.published_at.isoformat() == "2026-11-02T17:46:00+00:00"   # +0800 → UTC
    assert first.attribution == "Sumber: BMKG"


def test_parse_cap_severity_from_real_fixture():
    assert bmkg_weather.parse_cap_severity(fixture_bytes("bmkg_cap_moderate.xml")) == ("Moderate", "Sulawesi Barat")


def test_cap_only_for_new_items_and_capped(insight_env, monkeypatch):
    monkeypatch.setenv("INSIGHT_CAP_MAX_PER_CYCLE", "20")
    with dbm.session(get_settings().db_path) as conn:
        for i in range(5):  # 5 guid sudah ada di cache
            conn.execute("INSERT INTO insight_cap_cache VALUES (?,?,?,?,?)", (f"guid-{i}", "2026-11-03T00:00:00Z", 1,
                                                                            "Severe", None))
    caps = []

    def handler(req):
        if str(req.url) == bmkg_weather.RSS_URL:
            return httpx.Response(200, content=_rss_with(30))
        caps.append(str(req.url))
        return httpx.Response(200, content=_cap())

    a, items = _weather(handler)
    assert len(items) == 30
    assert len(caps) == 20                       # maksimal 20 per siklus
    assert not any("CXX000" in u or "CXX004" in u for u in caps)   # item lama tidak diambil ulang
    by_guid = {i.meta["guid"]: i for i in items}
    assert by_guid["guid-0"].meta["cap_severity"] == "Severe"       # dari cache
    assert by_guid["guid-29"].severity_verified is False            # belum kebagian kuota
    assert by_guid["guid-29"].meta["cap_status"] == "pending"

    # siklus berikutnya: hanya 5 sisanya
    caps.clear()
    _weather(handler)
    assert len(caps) == 5


def test_cap_stops_on_429_and_does_not_cache_it(insight_env):
    caps = []

    def handler(req):
        if str(req.url) == bmkg_weather.RSS_URL:
            return httpx.Response(200, content=_rss_with(6))
        caps.append(str(req.url))
        return httpx.Response(429) if len(caps) == 3 else httpx.Response(200, content=_cap("Extreme"))

    a, items = _weather(handler)
    assert len(caps) == 3 and a.cap_stop_reason == "429"
    with dbm.session(get_settings().db_path) as conn:
        cached = {r["guid"] for r in conn.execute("SELECT guid FROM insight_cap_cache")}
    assert cached == {"guid-0", "guid-1"}
    assert sum(i.severity_verified for i in items) == 2
    assert all(i.title for i in items)   # item tanpa CAP tetap dipakai


def test_cap_error_is_cached_and_not_retried(insight_env):
    caps = []

    def handler(req):
        if str(req.url) == bmkg_weather.RSS_URL:
            return httpx.Response(200, content=_rss_with(3))
        caps.append(str(req.url))
        return httpx.Response(500) if "CXX000" in str(req.url) else httpx.Response(200, content=_cap())

    a, _ = _weather(handler)
    assert len(caps) == 1 and a.cap_stop_reason == "http_500"   # berhenti untuk siklus ini
    with dbm.session(get_settings().db_path) as conn:
        row = conn.execute("SELECT * FROM insight_cap_cache WHERE guid='guid-0'").fetchone()
    assert row["ok"] == 0 and "500" in row["error"]
    caps.clear()
    _, items = _weather(handler)
    assert not any("CXX000" in u for u in caps) and len(caps) == 2
    assert {i.meta["guid"]: i.meta["cap_status"] for i in items}["guid-0"] == "failed"


def test_cap_url_from_foreign_host_is_never_fetched(insight_env):
    seen = []

    def handler(req):
        seen.append(str(req.url))
        if str(req.url) == bmkg_weather.RSS_URL:
            return httpx.Response(200, content=_rss_with(2, link_fmt="https://evil.example/{i}_alert.xml"))
        return httpx.Response(200, content=_cap())

    _, items = _weather(handler)
    assert seen == [bmkg_weather.RSS_URL]
    assert all(not i.severity_verified for i in items)
    assert bmkg_weather.safe_cap_url("https://www.bmkg.go.id/alerts/nowcast/id/../../x_alert.xml") is None


def test_cap_requests_are_sequential_with_delay(insight_env):
    delays = []

    async def rec_sleep(s):
        delays.append(s)

    def handler(req):
        if str(req.url) == bmkg_weather.RSS_URL:
            return httpx.Response(200, content=_rss_with(4))
        return httpx.Response(200, content=_cap())

    a = bmkg_weather.BmkgWeatherAdapter(get_settings(), sleep=rec_sleep)

    async def go():
        async with client(handler) as c:
            return await a.fetch(c)

    run(go())
    assert delays == [bmkg_weather.CAP_DELAY_SECONDS] * 3


# ---------- WHO DON ----------

def test_who_don_parses_real_fixture():
    items = who_don.parse_don(fixture_bytes("who_don.json"))
    assert len(items) == 3
    assert items[0].title == "Shamonda virus in human - France"
    assert items[0].url == "https://www.who.int/emergencies/disease-outbreak-news/item/2026-DON623"
    assert items[1].title.startswith("Ebola disease caused by Bundibugyo virus - ")   # OverrideTitle dipakai
    assert items[0].attribution == "Sumber: WHO" and items[0].category == "kesehatan_wabah"
    assert items[0].published_at.isoformat() == "2026-11-02T14:26:51+00:00"


def test_who_don_rejects_bad_urlname():
    doc = {"value": [{"Title": "x", "UrlName": "../../evil", "PublicationDate": "2026-11-01T00:00:00Z"}]}
    assert who_don.parse_don(json.dumps(doc).encode()) == []


# ---------- GDELT ----------

# Contoh dari DOKUMENTASI GDELT DOC 2.0 (bukan tangkapan langsung; API mengembalikan {} saat diverifikasi).
GDELT_DOC_SAMPLE = {"articles": [
    {"url": "https://example.co.id/banjir-bekasi", "url_mobile": "", "title": "Banjir rendam ribuan rumah di Bekasi",
     "seendate": "20261102T101500Z", "socialimage": "", "domain": "example.co.id", "language": "Indonesian",
     "sourcecountry": "Indonesia"},
    {"url": "https://example.co.id/ojk", "url_mobile": "", "title": "OJK terbitkan POJK baru asuransi",
     "seendate": "20261101T080000Z", "socialimage": "", "domain": "example.co.id", "language": "Indonesian",
     "sourcecountry": "Indonesia"},
]}


def test_gdelt_parses_documented_format_and_empty_object():
    items = gdelt.parse_artlist(json.dumps(GDELT_DOC_SAMPLE).encode())
    assert [i.title for i in items] == ["Banjir rendam ribuan rumah di Bekasi", "OJK terbitkan POJK baru asuransi"]
    assert items[0].published_at.isoformat() == "2026-11-02T10:15:00+00:00"
    assert items[0].attribution == "Sumber: GDELT Project"
    assert gdelt.parse_artlist(b"{}") == []          # respons nyata saat verifikasi


def test_gdelt_queries_sequential_spaced_and_stop_on_429():
    delays, calls = [], []

    async def rec_sleep(s):
        delays.append(s)

    def handler(req):
        calls.append(req.url.params["query"])
        if len(calls) == 3:
            return httpx.Response(429, text="Please limit requests to one every 5 seconds")
        return httpx.Response(200, json=GDELT_DOC_SAMPLE)

    a = gdelt.GdeltAdapter(sleep=rec_sleep, clock=lambda: 0.0)

    async def go():
        async with client(handler) as c:
            return await a.fetch(c)

    items = run(go())
    assert len(calls) == 3 and a.stop_reason == "429"
    assert delays == [gdelt.QUERY_SPACING_SECONDS] * 2
    assert len(items) == 2                       # dedupe per URL antar-query, hasil parsial dipakai
    assert all(q.endswith("sourcecountry:indonesia") for q in calls)


def test_gdelt_429_on_first_query_is_error():
    a = gdelt.GdeltAdapter(sleep=no_sleep)

    async def go():
        async with client(lambda r: httpx.Response(429)) as c:
            return await a.fetch(c)

    with pytest.raises(SourceError):
        run(go())


# ---------- RSS generik ----------

def test_rss_parses_real_rss2_fixture_and_cleans_html():
    feed = RssFeed(key="rss.who-news", label="WHO News", url="https://www.who.int/rss-feeds/news-english.xml")
    items = rss.parse_feed(fixture_bytes("rss_who_news.xml"), feed)
    assert len(items) == 2
    assert items[0].title.startswith("New WHO technical package")
    assert items[0].url.startswith("https://www.who.int/news/item/")
    assert items[0].source == "rss.who-news" and items[0].attribution == "Sumber: WHO News"
    assert items[0].published_at is not None
    from insight.classify import clean_text
    assert "<" not in clean_text(items[0].snippet, 300)


def test_rss_parses_atom():
    atom = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>t</title>
<entry><title>Banjir di Semarang</title><link rel="alternate" href="https://example.org/a"/>
<updated>2026-11-02T01:00:00Z</updated><summary>&lt;b&gt;Ringkas&lt;/b&gt;</summary></entry></feed>"""
    feed = RssFeed(key="rss.contoh", label="Contoh", url="https://example.org/feed")
    items = rss.parse_feed(atom, feed)
    assert len(items) == 1 and items[0].url == "https://example.org/a"


def test_rss_with_entity_is_rejected():
    bomb = b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa">]><rss><channel></channel></rss>'
    with pytest.raises(SourceError):
        rss.parse_feed(bomb, RssFeed(key="rss.x", label="x", url="https://example.org/x"))


def test_rss_feeds_config_only_accepts_http(monkeypatch):
    monkeypatch.setenv("INSIGHT_RSS_FEEDS", "Antara=https://example.org/rss; Bad=file:///etc/passwd;Ftp=ftp://x/y")
    feeds = get_settings().rss_feeds
    assert [(f.key, f.url) for f in feeds] == [("rss.antara", "https://example.org/rss")]
    assert "rss.antara" in get_settings().enabled_keys
