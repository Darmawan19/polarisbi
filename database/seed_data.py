import numpy as np
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)

COMPANIES = [
    "Prudential Life Assurance",
    "Allianz Life Indonesia",
    "AIA Financial",
    "Manulife Indonesia",
    "BRI Life",
    "AXA Mandiri Financial Services",
    "Sequis Life",
    "Asuransi Jiwa Sinarmas MSIG",
    "Cigna Indonesia",
    "Avrist Assurance",
    "FWD Insurance Indonesia",
    "Sun Life Financial Indonesia",
    "Indolife Pensiontama",
    "Astra Aviva Life",
    "Generali Indonesia",
]

PERIODS = ["2024Q1", "2024Q2", "2024Q3", "2024Q4"]
TOP5 = ["BRI Life", "Prudential Life Assurance", "Allianz Life Indonesia", "Manulife Indonesia", "AIA Financial"]


def seed_industry_aggregate():
    rng = np.random.default_rng(42)
    rows = []
    size_factors = {c: rng.uniform(0.5, 3.0) for c in COMPANIES}

    for periode in PERIODS:
        for company in COMPANIES:
            sf = size_factors[company]
            premi = rng.uniform(800e9, 2500e9) * sf
            klaim = premi * rng.uniform(0.55, 0.85)
            aset = premi * rng.uniform(2.5, 4.5)
            investasi = aset * rng.uniform(0.80, 0.92)
            rbc = rng.uniform(180, 480)
            rows.append({
                "PERIODE": periode,
                "NAMA_PERUSAHAAN": company,
                "KATEGORI": "Jiwa",
                "PREMI_BRUTO_IDR": round(premi),
                "KLAIM_BRUTO_IDR": round(klaim),
                "ASET_IDR": round(aset),
                "INVESTASI_IDR": round(investasi),
                "RBC_PCT": round(rbc, 2),
            })

    df = pd.DataFrame(rows)
    out = DATA_DIR / "ojk_industry_aggregate.csv"
    df.to_csv(out, index=False)
    print(f"ojk_industry_aggregate.csv: {len(df)} rows")
    return df


def seed_channel_distribusi():
    rng = np.random.default_rng(43)
    channels = ["Bancassurance", "Agency", "Telemarketing", "Digital", "Worksite Marketing"]
    rows = []

    for periode in PERIODS:
        for company in TOP5:
            for kanal in channels:
                ape = rng.uniform(50e9, 800e9)
                polis = int(rng.uniform(5000, 80000))
                rows.append({
                    "PERIODE": periode,
                    "NAMA_PERUSAHAAN": company,
                    "KANAL_DISTRIBUSI": kanal,
                    "APE_IDR": round(ape),
                    "JUMLAH_POLIS_BARU": polis,
                })

    df = pd.DataFrame(rows)
    out = DATA_DIR / "ojk_channel_distribusi.csv"
    df.to_csv(out, index=False)
    print(f"ojk_channel_distribusi.csv: {len(df)} rows")
    return df


def seed_klaim_kategori():
    rng = np.random.default_rng(44)
    kategori_list = [
        "Klaim Meninggal",
        "Klaim Kesehatan",
        "Klaim Surrender",
        "Klaim Akhir Kontrak",
        "Klaim Kecelakaan",
        "Klaim Penyakit Kritis",
    ]
    rows = []

    for periode in PERIODS:
        for company in TOP5:
            for kat in kategori_list:
                jumlah = int(rng.uniform(500, 15000))
                nilai_per_klaim = rng.uniform(5e6, 50e6)
                nilai_total = round(jumlah * nilai_per_klaim)
                rasio = round(rng.uniform(5, 65), 2)
                rows.append({
                    "PERIODE": periode,
                    "NAMA_PERUSAHAAN": company,
                    "KATEGORI_KLAIM": kat,
                    "JUMLAH_KLAIM": jumlah,
                    "NILAI_KLAIM_IDR": nilai_total,
                    "RASIO_TERHADAP_PREMI": rasio,
                })

    df = pd.DataFrame(rows)
    out = DATA_DIR / "ojk_klaim_kategori.csv"
    df.to_csv(out, index=False)
    print(f"ojk_klaim_kategori.csv: {len(df)} rows")
    return df


if __name__ == "__main__":
    seed_industry_aggregate()
    seed_channel_distribusi()
    seed_klaim_kategori()
