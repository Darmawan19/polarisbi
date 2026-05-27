import duckdb
import streamlit as st

from agent.sql_agent import generate_sql

st.set_page_config(page_title="PolarisBI", page_icon="🧭", layout="wide")

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 💡 Contoh Pertanyaan")

    examples = [
        "Tunjukkan total premi industri asuransi jiwa 2024",
        "Bandingkan APE BRI Life vs Allianz per kanal distribusi",
        "Top 5 perusahaan dengan RBC tertinggi 2024Q4",
        "Rasio klaim kesehatan terhadap total klaim per perusahaan 2024",
        "Tren premi bruto BRI Life per kuartal 2024",
    ]

    for example in examples:
        if st.button(example, use_container_width=True):
            st.session_state["question"] = example

    st.markdown("---")
    st.markdown("### 📊 Data Sources")
    st.markdown(
        """
| Tabel | Deskripsi |
|---|---|
| `industry_aggregate` | Agregat industri asuransi jiwa per periode |
| `channel_distribusi` | APE per kanal & perusahaan |
| `klaim_kategori` | Klaim per kategori & perusahaan |

> ⚠️ Data sintetis mengikuti schema OJK — hanya untuk demo.
"""
    )

# ── Main ─────────────────────────────────────────────────────────────────────

st.title("🧭 PolarisBI")
st.caption(
    "AI Cockpit untuk IT Business Analyst Asuransi — Powered by Claude + DuckDB"
)

question = st.text_input(
    "Pertanyaan Anda",
    value=st.session_state.get("question", ""),
    placeholder="Contoh: total premi industri 2024 per kuartal",
)

if question:
    # ── Generate SQL ──────────────────────────────────────────────────────────
    with st.spinner("🤔 Menganalisis pertanyaan..."):
        try:
            sql, interpretation = generate_sql(question)
        except Exception as e:
            st.error(f"Gagal generate SQL: {e}")
            st.stop()

    if interpretation:
        st.info(interpretation)

    with st.expander("📝 Generated SQL Query", expanded=False):
        st.code(sql, language="sql")

    # ── Execute SQL ───────────────────────────────────────────────────────────
    with st.spinner("⚡ Menjalankan query di DuckDB..."):
        try:
            con = duckdb.connect("polaris.duckdb", read_only=True)
            df = con.execute(sql).df()
            con.close()
        except Exception as e:
            st.error(f"Gagal menjalankan query: {e}")
            st.stop()

    # ── Results ───────────────────────────────────────────────────────────────
    st.markdown("### 📋 Hasil Query")
    st.markdown(f"**{len(df)} baris** ditampilkan")
    st.dataframe(df, use_container_width=True)

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    if numeric_cols:
        with st.expander("📈 Quick Stats (numeric columns)", expanded=False):
            st.dataframe(df[numeric_cols].describe(), use_container_width=True)

# ── Footer ────────────────────────────────────────────────────────────────────

st.markdown("---")
st.caption("PolarisBI v0.1 — Bintang Utara untuk Data Analyst Asuransi 🧭")
