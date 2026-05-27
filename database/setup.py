import duckdb
from pathlib import Path

DEFAULT_DB_PATH = str(Path(__file__).parent.parent / "polaris.duckdb")
DEFAULT_DATA_DIR = str(Path(__file__).parent.parent / "data" / "raw")


def initialize_database(db_path: str = DEFAULT_DB_PATH, data_dir: str = DEFAULT_DATA_DIR):
    data_dir = Path(data_dir)
    con = duckdb.connect(db_path)

    tables = {
        "industry_aggregate": data_dir / "ojk_industry_aggregate.csv",
        "channel_distribusi": data_dir / "ojk_channel_distribusi.csv",
        "klaim_kategori": data_dir / "ojk_klaim_kategori.csv",
    }

    for table, csv_path in tables.items():
        con.execute(f"DROP TABLE IF EXISTS {table}")
        con.execute(f"CREATE TABLE {table} AS SELECT * FROM read_csv_auto('{csv_path.as_posix()}')")
        count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"Table '{table}': {count} rows loaded")

    con.close()


def get_schema_description() -> str:
    return """
## Skema Database PolarisBI

### Tabel: industry_aggregate
Data agregat industri asuransi jiwa per perusahaan dan kuartal.
| Kolom              | Tipe    | Deskripsi                                      |
|--------------------|---------|------------------------------------------------|
| PERIODE            | VARCHAR | Kuartal pelaporan, format '2024Q1' s/d '2024Q4' |
| NAMA_PERUSAHAAN    | VARCHAR | Nama perusahaan asuransi jiwa                  |
| KATEGORI           | VARCHAR | Kategori usaha (misal: 'Jiwa')                  |
| PREMI_BRUTO_IDR    | BIGINT  | Premi bruto dalam Rupiah                       |
| KLAIM_BRUTO_IDR    | BIGINT  | Klaim bruto dalam Rupiah                       |
| ASET_IDR           | BIGINT  | Total aset dalam Rupiah                        |
| INVESTASI_IDR      | BIGINT  | Total investasi dalam Rupiah                   |
| RBC_PCT            | DOUBLE  | Risk-Based Capital dalam persen (%)            |

### Tabel: channel_distribusi
Data distribusi premi baru per kanal dan perusahaan (5 perusahaan terbesar).
| Kolom              | Tipe    | Deskripsi                                      |
|--------------------|---------|------------------------------------------------|
| PERIODE            | VARCHAR | Kuartal pelaporan                              |
| NAMA_PERUSAHAAN    | VARCHAR | Nama perusahaan asuransi jiwa                  |
| KANAL_DISTRIBUSI   | VARCHAR | Kanal distribusi (Bancassurance, Agency, dll)  |
| APE_IDR            | BIGINT  | Annual Premium Equivalent dalam Rupiah         |
| JUMLAH_POLIS_BARU  | INTEGER | Jumlah polis baru yang diterbitkan             |

### Tabel: klaim_kategori
Data klaim per kategori dan perusahaan (5 perusahaan terbesar).
| Kolom               | Tipe    | Deskripsi                                     |
|---------------------|---------|-----------------------------------------------|
| PERIODE             | VARCHAR | Kuartal pelaporan                             |
| NAMA_PERUSAHAAN     | VARCHAR | Nama perusahaan asuransi jiwa                 |
| KATEGORI_KLAIM      | VARCHAR | Jenis klaim                                   |
| JUMLAH_KLAIM        | INTEGER | Jumlah klaim yang dibayarkan                  |
| NILAI_KLAIM_IDR     | BIGINT  | Total nilai klaim dalam Rupiah                |
| RASIO_TERHADAP_PREMI| DOUBLE  | Rasio nilai klaim terhadap premi (%)          |

---

## Glosarium Asuransi

- **Premi Bruto**: Total premi yang diterima perusahaan dari pemegang polis sebelum dikurangi reasuransi.
- **APE (Annual Premium Equivalent)**: Standar pengukuran bisnis baru; premi tahunan reguler + 10% premi single. Digunakan untuk membandingkan produktivitas distribusi antar kanal.
- **RBC (Risk-Based Capital)**: Rasio kecukupan modal berbasis risiko. OJK mewajibkan minimum 120%. Semakin tinggi RBC, semakin sehat perusahaan secara solvabilitas.
- **Bancassurance**: Kanal distribusi asuransi melalui jaringan perbankan. Di Indonesia merupakan kanal terbesar untuk asuransi jiwa.
- **Klaim Surrender**: Klaim yang timbul karena pemegang polis mengakhiri kontrak lebih awal (menebus nilai tunai polis). Surrender rate tinggi mengindikasikan masalah lapse.

---

## Daftar Perusahaan
industry_aggregate berisi 15 perusahaan: Prudential Life Assurance, Allianz Life Indonesia, AIA Financial, Manulife Indonesia, BRI Life, AXA Mandiri Financial Services, Sequis Life, Asuransi Jiwa Sinarmas MSIG, Cigna Indonesia, Avrist Assurance, FWD Insurance Indonesia, Sun Life Financial Indonesia, Indolife Pensiontama, Astra Aviva Life, Generali Indonesia.
channel_distribusi dan klaim_kategori berisi 5 perusahaan terbesar: BRI Life, Prudential Life Assurance, Allianz Life Indonesia, Manulife Indonesia, AIA Financial.

Periode tersedia: 2024Q1, 2024Q2, 2024Q3, 2024Q4.
""".strip()


if __name__ == "__main__":
    initialize_database()
