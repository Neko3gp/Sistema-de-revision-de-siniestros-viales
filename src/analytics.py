from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable

import geopandas as gpd
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
REPORTS_DIR = BASE_DIR / "reports"

ACCIDENTS_PATH = PROCESSED_DIR / "siniestros_asignados.gpkg"
SEGMENTS_PATH = PROCESSED_DIR / "tramos_con_metricas.gpkg"
POINTS_PATH = PROCESSED_DIR / "puntos_criticos.gpkg"


def _safe_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _relative_index(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").fillna(0)
    if values.max() == values.min():
        return pd.Series(0.0, index=values.index)
    return (values - values.min()) / (values.max() - values.min()) * 100


def load_data() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]:
    accidents = gpd.read_file(ACCIDENTS_PATH)
    segments = gpd.read_file(SEGMENTS_PATH)
    points = gpd.read_file(POINTS_PATH)
    return accidents, segments, points


def intersection_ranking(accidents: gpd.GeoDataFrame) -> pd.DataFrame:
    data = accidents.copy()
    data["calle1_norm"] = data["calle1_norm"].map(_safe_text)
    data["calle2_norm"] = data["calle2_norm"].map(_safe_text)
    data = data[data["calle2_norm"] != ""].copy()
    data["cruce"] = data.apply(
        lambda row: " / ".join(sorted((row["calle1_norm"], row["calle2_norm"]))),
        axis=1,
    )
    result = (
        data.groupby("cruce", as_index=False)
        .agg(
            siniestros=("id_unico", "count"),
            severidad=("indice_severidad", "sum"),
            fatales=("clase", lambda s: (s == "Fatal").sum()),
            muertos=("totmuertos", "sum"),
            heridos=("totheridos", "sum"),
            peatones=("involucra_peaton", "sum"),
            motocicletas=("involucra_moto", "sum"),
            geometry=("geometry", lambda values: values.union_all().centroid),
        )
    )
    result["aforo_relativo"] = (
        0.55 * _relative_index(result["siniestros"])
        + 0.30 * _relative_index(result["severidad"])
        + 0.15 * _relative_index(result["peatones"] + result["motocicletas"])
    ).round(2)
    return result.sort_values(["severidad", "siniestros"], ascending=False).reset_index(drop=True)


def segment_ranking(segments: gpd.GeoDataFrame) -> pd.DataFrame:
    result = segments.copy()
    result["aforo_relativo"] = (
        0.60 * _relative_index(result["n_todos"])
        + 0.25 * _relative_index(result["sev_todos"])
        + 0.15 * _relative_index(result["sev_km_todos"])
    ).round(2)
    return result.sort_values(["sev_todos", "n_todos"], ascending=False).reset_index(drop=True)


def road_ranking(segments: gpd.GeoDataFrame) -> pd.DataFrame:
    columns = ["vialidad_canon", "n_todos", "sev_todos", "fatales_todos", "muertos_todos", "heridos_todos",
               "longitud_m", "n_peaton", "n_moto"]
    data = segments[[column for column in columns if column in segments]].copy()
    data["vialidad_canon"] = data["vialidad_canon"].map(_safe_text)
    data = data[data["vialidad_canon"] != ""]
    result = data.groupby("vialidad_canon", as_index=False).sum(numeric_only=True)
    result["aforo_relativo"] = (
        0.55 * _relative_index(result["n_todos"])
        + 0.30 * _relative_index(result["sev_todos"])
        + 0.15 * _relative_index(result["n_peaton"] + result["n_moto"])
    ).round(2)
    return result.sort_values(["sev_todos", "n_todos"], ascending=False).reset_index(drop=True)


def zone_ranking(points: gpd.GeoDataFrame) -> pd.DataFrame:
    result = points.copy()
    result["aforo_relativo"] = (
        0.55 * _relative_index(result["n_siniestros"])
        + 0.30 * _relative_index(result["severidad"])
        + 0.15 * _relative_index(result["n_peaton_ciclista"])
    ).round(2)
    return result.sort_values(["severidad", "n_siniestros"], ascending=False).reset_index(drop=True)


def top_rows(frame: pd.DataFrame, limit: int = 50) -> pd.DataFrame:
    return frame.head(limit).copy()


def _format_value(value: object) -> str:
    if pd.isna(value):
        return "Sin dato"
    if isinstance(value, float):
        return f"{value:,.2f}"
    return f"{value:,}" if isinstance(value, int) else str(value)


def write_pdf_report(title: str, row: pd.Series, output_path: Path) -> Path:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    output_path.parent.mkdir(parents=True, exist_ok=True)
    excluded = {"geometry"}
    items = [(key, _format_value(value)) for key, value in row.items() if key not in excluded]
    with PdfPages(output_path) as pdf:
        fig = plt.figure(figsize=(8.27, 11.69))
        fig.text(0.08, 0.93, title, fontsize=18, weight="bold", va="top")
        fig.text(0.08, 0.885, "Sistema de revisión de siniestros · Chihuahua", fontsize=10, color="#555555")
        y = 0.82
        for key, value in items:
            fig.text(0.08, y, f"{key.replace('_', ' ').title()}:", fontsize=10, weight="bold")
            fig.text(0.38, y, value, fontsize=10)
            y -= 0.032
            if y < 0.08:
                pdf.savefig(fig, bbox_inches="tight")
                plt.close(fig)
                fig = plt.figure(figsize=(8.27, 11.69))
                y = 0.92
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
    return output_path


def write_ml_extract(accidents: gpd.GeoDataFrame, segments: gpd.GeoDataFrame, points: gpd.GeoDataFrame) -> list[Path]:
    outputs = []
    for name, frame in {
        "siniestros_modelo": accidents,
        "tramos_modelo": segments,
        "puntos_criticos_modelo": points,
    }.items():
        target = PROCESSED_DIR / f"{name}.parquet"
        frame.to_parquet(target, index=False)
        outputs.append(target)
    return outputs
