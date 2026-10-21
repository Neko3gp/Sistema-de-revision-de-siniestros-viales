from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
from streamlit.components.v1 import html

SRC_DIR = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC_DIR))

from analytics import (  # noqa: E402
    REPORTS_DIR,
    intersection_ranking,
    load_data,
    road_ranking,
    segment_ranking,
    top_rows,
    write_pdf_report,
    zone_ranking,
)

BASE_DIR = Path(__file__).resolve().parent
MAP_PATH = BASE_DIR / "outputs" / "mapa_siniestralidad_chihuahua.html"


st.set_page_config(page_title="Revisión de siniestros Chihuahua", layout="wide")
st.title("Mapa de siniestralidad vial · Chihuahua")
st.caption("Sistema de revisión de siniestros · análisis 2019–2024")

try:
    accidents, segments, points = load_data()
except Exception as exc:
    st.error(f"No fue posible cargar los datos consolidados: {exc}")
    st.stop()

with st.sidebar:
    st.header("Productos del pipeline")
    st.write("La vista principal conserva el mapa Folium original, con sus capas, leyenda y selector de periodo.")
    report_pdf = REPORTS_DIR / "reporte_intersecciones_historico.pdf"
    report_html = REPORTS_DIR / "reporte_intersecciones_historico.html"
    if report_pdf.exists():
        st.download_button(
            "Descargar reporte general PDF",
            data=report_pdf.read_bytes(),
            file_name=report_pdf.name,
            mime="application/pdf",
        )
    if report_html.exists():
        st.download_button(
            "Descargar reporte general HTML",
            data=report_html.read_bytes(),
            file_name=report_html.name,
            mime="text/html",
        )
    if MAP_PATH.exists():
        st.download_button(
            "Descargar mapa HTML",
            data=MAP_PATH.read_bytes(),
            file_name=MAP_PATH.name,
            mime="text/html",
        )
    for report in sorted(REPORTS_DIR.glob("top_50_*.csv")):
        st.download_button(
            report.stem.replace("_", " ").title(),
            data=report.read_bytes(),
            file_name=report.name,
            mime="text/csv",
        )
    st.divider()
    category = st.selectbox("Ranking auxiliar", ["Intersecciones", "Tramos", "Vialidades", "Zonas"])
    limit = st.slider("Elementos a mostrar", min_value=10, max_value=50, value=20, step=10)

frames = {
    "Intersecciones": top_rows(intersection_ranking(accidents), limit),
    "Tramos": top_rows(segment_ranking(segments), limit),
    "Vialidades": top_rows(road_ranking(segments), limit),
    "Zonas": top_rows(zone_ranking(points), limit),
}
ranking = frames[category]

metrics = st.columns(4)
metrics[0].metric("Siniestros", f"{len(accidents):,}")
metrics[1].metric("Tramos analizados", f"{len(segments):,}")
metrics[2].metric("Puntos críticos", f"{len(points):,}")
metrics[3].metric("Elementos en ranking", f"{len(ranking):,}")

st.info(
    "El campo «aforo relativo» es un proxy estadístico basado en siniestros, severidad y usuarios vulnerables. "
    "No sustituye un conteo vehicular de campo."
)

if not MAP_PATH.exists():
    st.warning("El mapa aún no existe. Ejecuta `python run_pipeline.py` para generarlo.")
else:
    html(MAP_PATH.read_text(encoding="utf-8"), height=780, scrolling=False)

display = ranking.drop(columns=["geometry"], errors="ignore")
st.subheader(f"Ranking auxiliar · Top {limit}: {category.lower()}")
st.dataframe(display, use_container_width=True, hide_index=True)

selected_index = st.selectbox(
    "Selecciona un elemento para generar su ficha PDF",
    options=list(range(len(ranking))),
    format_func=lambda i: str(
        ranking.iloc[i].get("cruce")
        or ranking.iloc[i].get("vialidad_canon")
        or f"Punto crítico {ranking.iloc[i].get('ranking', i + 1)}"
    ),
)

if st.button("Generar reporte PDF"):
    selected = ranking.iloc[selected_index]
    label = str(
        selected.get("cruce")
        or selected.get("vialidad_canon")
        or f"Punto crítico {selected.get('ranking', selected_index + 1)}"
    )
    pdf_path = write_pdf_report(f"Reporte individual: {label}", selected, REPORTS_DIR / "seleccionado.pdf")
    st.success(f"Reporte generado: {pdf_path.name}")
    st.download_button(
        "Descargar reporte PDF",
        data=pdf_path.read_bytes(),
        file_name=pdf_path.name,
        mime="application/pdf",
    )
