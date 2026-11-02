"""Daftar kanonik 38 provinsi Indonesia + alias umum, dan deteksi provinsi dari teks."""
from __future__ import annotations

import re

PROVINCES: tuple[str, ...] = (
    "Aceh", "Sumatera Utara", "Sumatera Barat", "Riau", "Kepulauan Riau", "Jambi", "Sumatera Selatan",
    "Kepulauan Bangka Belitung", "Bengkulu", "Lampung", "DKI Jakarta", "Jawa Barat", "Banten", "Jawa Tengah",
    "DI Yogyakarta", "Jawa Timur", "Bali", "Nusa Tenggara Barat", "Nusa Tenggara Timur", "Kalimantan Barat",
    "Kalimantan Tengah", "Kalimantan Selatan", "Kalimantan Timur", "Kalimantan Utara", "Sulawesi Utara",
    "Gorontalo", "Sulawesi Tengah", "Sulawesi Barat", "Sulawesi Selatan", "Sulawesi Tenggara", "Maluku",
    "Maluku Utara", "Papua", "Papua Barat", "Papua Barat Daya", "Papua Selatan", "Papua Tengah",
    "Papua Pegunungan",
)

JAVA = frozenset({"DKI Jakarta", "Jawa Barat", "Banten", "Jawa Tengah", "DI Yogyakarta", "Jawa Timur"})

# Alias umum (Indonesia + Inggris + beberapa kota besar). Nama kanonik otomatis ikut.
ALIASES: dict[str, str] = {
    "nanggroe aceh darussalam": "Aceh", "banda aceh": "Aceh",
    "sumut": "Sumatera Utara", "north sumatra": "Sumatera Utara", "medan": "Sumatera Utara",
    "sumbar": "Sumatera Barat", "west sumatra": "Sumatera Barat",
    "pekanbaru": "Riau",
    "kepri": "Kepulauan Riau", "riau islands": "Kepulauan Riau", "batam": "Kepulauan Riau",
    "sumsel": "Sumatera Selatan", "south sumatra": "Sumatera Selatan", "palembang": "Sumatera Selatan",
    "babel": "Kepulauan Bangka Belitung", "bangka belitung": "Kepulauan Bangka Belitung",
    "bandar lampung": "Lampung",
    "jakarta": "DKI Jakarta", "dki": "DKI Jakarta",
    "jabar": "Jawa Barat", "west java": "Jawa Barat", "bandung": "Jawa Barat", "bogor": "Jawa Barat",
    "bekasi": "Jawa Barat", "depok": "Jawa Barat", "sukabumi": "Jawa Barat",
    "tangerang": "Banten",
    "jateng": "Jawa Tengah", "central java": "Jawa Tengah", "semarang": "Jawa Tengah",
    "diy": "DI Yogyakarta", "yogyakarta": "DI Yogyakarta", "daerah istimewa yogyakarta": "DI Yogyakarta",
    "jogja": "DI Yogyakarta", "jogjakarta": "DI Yogyakarta", "yogya": "DI Yogyakarta",
    "jatim": "Jawa Timur", "east java": "Jawa Timur", "surabaya": "Jawa Timur",
    "denpasar": "Bali",
    "ntb": "Nusa Tenggara Barat", "west nusa tenggara": "Nusa Tenggara Barat", "mataram": "Nusa Tenggara Barat",
    "lombok": "Nusa Tenggara Barat",
    "ntt": "Nusa Tenggara Timur", "east nusa tenggara": "Nusa Tenggara Timur", "kupang": "Nusa Tenggara Timur",
    "kalbar": "Kalimantan Barat", "west kalimantan": "Kalimantan Barat", "pontianak": "Kalimantan Barat",
    "kalteng": "Kalimantan Tengah", "central kalimantan": "Kalimantan Tengah", "palangkaraya": "Kalimantan Tengah",
    "palangka raya": "Kalimantan Tengah",
    "kalsel": "Kalimantan Selatan", "south kalimantan": "Kalimantan Selatan", "banjarmasin": "Kalimantan Selatan",
    "kaltim": "Kalimantan Timur", "east kalimantan": "Kalimantan Timur", "samarinda": "Kalimantan Timur",
    "balikpapan": "Kalimantan Timur",
    "kaltara": "Kalimantan Utara", "north kalimantan": "Kalimantan Utara",
    "sulut": "Sulawesi Utara", "north sulawesi": "Sulawesi Utara", "manado": "Sulawesi Utara",
    "sulteng": "Sulawesi Tengah", "central sulawesi": "Sulawesi Tengah", "palu": "Sulawesi Tengah",
    "sulbar": "Sulawesi Barat", "west sulawesi": "Sulawesi Barat",
    "sulsel": "Sulawesi Selatan", "south sulawesi": "Sulawesi Selatan", "makassar": "Sulawesi Selatan",
    "sultra": "Sulawesi Tenggara", "southeast sulawesi": "Sulawesi Tenggara", "kendari": "Sulawesi Tenggara",
    "ambon": "Maluku",
    "malut": "Maluku Utara", "north maluku": "Maluku Utara", "ternate": "Maluku Utara",
    "jayapura": "Papua",
    "pabar": "Papua Barat", "west papua": "Papua Barat", "manokwari": "Papua Barat",
    "southwest papua": "Papua Barat Daya", "sorong": "Papua Barat Daya",
    "south papua": "Papua Selatan", "merauke": "Papua Selatan",
    "central papua": "Papua Tengah", "nabire": "Papua Tengah",
    "highland papua": "Papua Pegunungan", "papua highlands": "Papua Pegunungan", "wamena": "Papua Pegunungan",
}

# Kode wilayah di akhir field "Wilayah" BMKG (mis. "1 km BaratDaya TOMOHON-SULUT").
BMKG_REGION_CODES: dict[str, str] = {
    "ACEH": "Aceh", "SUMUT": "Sumatera Utara", "SUMBAR": "Sumatera Barat", "RIAU": "Riau",
    "KEPRI": "Kepulauan Riau", "JAMBI": "Jambi", "SUMSEL": "Sumatera Selatan", "BABEL": "Kepulauan Bangka Belitung",
    "BENGKULU": "Bengkulu", "LAMPUNG": "Lampung", "DKI": "DKI Jakarta", "JAKARTA": "DKI Jakarta",
    "JABAR": "Jawa Barat", "BANTEN": "Banten", "JATENG": "Jawa Tengah", "DIY": "DI Yogyakarta",
    "JATIM": "Jawa Timur", "BALI": "Bali", "NTB": "Nusa Tenggara Barat", "NTT": "Nusa Tenggara Timur",
    "KALBAR": "Kalimantan Barat", "KALTENG": "Kalimantan Tengah", "KALSEL": "Kalimantan Selatan",
    "KALTIM": "Kalimantan Timur", "KALTARA": "Kalimantan Utara", "SULUT": "Sulawesi Utara",
    "GORONTALO": "Gorontalo", "SULTENG": "Sulawesi Tengah", "SULBAR": "Sulawesi Barat",
    "SULSEL": "Sulawesi Selatan", "SULTRA": "Sulawesi Tenggara", "MALUKU": "Maluku", "MALUT": "Maluku Utara",
    "PAPUA": "Papua", "PAPUABRT": "Papua Barat", "PABAR": "Papua Barat", "PAPUABRTDAYA": "Papua Barat Daya",
    "PAPUASLTN": "Papua Selatan", "PAPUASELATAN": "Papua Selatan", "PAPUATGH": "Papua Tengah",
    "PAPUATENGAH": "Papua Tengah", "PAPUAPGNGN": "Papua Pegunungan", "PAPUAPEGUNUNGAN": "Papua Pegunungan",
}

_LOOKUP: dict[str, str] = {p.lower(): p for p in PROVINCES}
_LOOKUP.update(ALIASES)
# Urut terpanjang dulu supaya "Papua Barat Daya" menang atas "Papua Barat" dan "Papua".
_PATTERN = re.compile(
    r"(?<![\w])(" + "|".join(re.escape(k) for k in sorted(_LOOKUP, key=len, reverse=True)) + r")(?![\w])",
    re.IGNORECASE,
)


def canonical(name: str | None) -> str | None:
    """Nama/alias → nama kanonik, atau None bila tidak dikenal."""
    if not name:
        return None
    key = re.sub(r"\s+", " ", name.strip().lower())
    return _LOOKUP.get(key)


def detect_province(text: str | None) -> str | None:
    """Provinsi pertama yang disebut di teks, atau None."""
    if not text:
        return None
    m = _PATTERN.search(text)
    return _LOOKUP[m.group(1).lower()] if m else None


def province_from_bmkg_region(wilayah: str | None) -> str | None:
    """Ambil provinsi dari kode di akhir 'Wilayah' BMKG, fallback ke deteksi teks."""
    if not wilayah:
        return None
    w = wilayah.strip()
    # kode ada setelah "-" terakhir ("TOMOHON-SULUT"); tanpa "-", coba token terakhir ("MALUKUBRTDAYA")
    tail = (w.rsplit("-", 1)[-1] if "-" in w else w.rsplit(" ", 1)[-1]).strip().upper().replace(" ", "")
    if tail:
        if tail in BMKG_REGION_CODES:
            return BMKG_REGION_CODES[tail]
        # mis. "ACEHBARAT" → Aceh, "MALUKUBRTDAYA" → Maluku (prefiks terpanjang yang cocok)
        for code in sorted(BMKG_REGION_CODES, key=len, reverse=True):
            if len(code) >= 4 and tail.startswith(code):
                return BMKG_REGION_CODES[code]
    return detect_province(wilayah)
