from __future__ import annotations

import base64
import html
import io
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _intersection_data(accidents: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    data = accidents.copy()
    data["calle1_norm"] = data["calle1_norm"].fillna("").astype(str).str.strip()
    data["calle2_norm"] = data["calle2_norm"].fillna("").astype(str).str.strip()
    missing = int(((data["calle1_norm"] == "") | (data["calle2_norm"] == "")).sum())
    data = data[(data["calle1_norm"] != "") & (data["calle2_norm"] != "")].copy()
    data["interseccion"] = data.apply(
        lambda row: " / ".join(sorted((row["calle1_norm"], row["calle2_norm"]))),
        axis=1,
    )
    data["fatal"] = data["clase"].eq("Fatal").astype(int)
    data["usuario_vulnerable"] = (
        data["involucra_peaton"].fillna(False)
        | data["involucra_ciclista"].fillna(False)
        | data["involucra_moto"].fillna(False)
    ).astype(int)
    data["año"] = pd.to_numeric(data["año"], errors="coerce").astype("Int64")
    data = data.dropna(subset=["año"])

    summary = (
        data.groupby("interseccion", as_index=False)
        .agg(
            siniestros=("id_unico", "count"),
            severidad=("indice_severidad", "sum"),
            severidad_promedio=("indice_severidad", "mean"),
            fatales=("fatal", "sum"),
            muertos=("totmuertos", "sum"),
            heridos=("totheridos", "sum"),
            usuarios_vulnerables=("usuario_vulnerable", "sum"),
            peatones=("involucra_peaton", "sum"),
            ciclistas=("involucra_ciclista", "sum"),
            motocicletas=("involucra_moto", "sum"),
            primer_año=("año", "min"),
            ultimo_año=("año", "max"),
        )
    )
    summary["tasa_fatalidad_pct"] = (
        summary["fatales"] / summary["siniestros"] * 100
    ).round(2)
    summary["ranking"] = (
        summary["severidad"].rank(method="min", ascending=False).astype(int)
    )
    summary = summary.sort_values(
        ["severidad", "siniestros", "fatales"], ascending=False
    ).reset_index(drop=True)

    yearly = (
        data.groupby(["interseccion", "año"], as_index=False)
        .agg(
            siniestros=("id_unico", "count"),
            severidad=("indice_severidad", "sum"),
            fatales=("fatal", "sum"),
            muertos=("totmuertos", "sum"),
            heridos=("totheridos", "sum"),
            usuarios_vulnerables=("usuario_vulnerable", "sum"),
        )
        .sort_values(["interseccion", "año"])
    )
    return summary, yearly, missing


def _yearly_summary(accidents: pd.DataFrame, yearly: pd.DataFrame) -> pd.DataFrame:
    years = sorted(yearly["año"].unique())
    result = (
        yearly.groupby("año", as_index=False)
        .agg(
            siniestros=("siniestros", "sum"),
            severidad=("severidad", "sum"),
            fatales=("fatales", "sum"),
            muertos=("muertos", "sum"),
            heridos=("heridos", "sum"),
            usuarios_vulnerables=("usuarios_vulnerables", "sum"),
            intersecciones_activas=("interseccion", "nunique"),
        )
        .sort_values("año")
    )
    result["registros_originales"] = (
        accidents.groupby("año").size().reindex(years, fill_value=0).values
    )
    result["severidad_promedio"] = (
        result["severidad"] / result["siniestros"]
    ).round(2)
    result["cambio_siniestros_pct"] = (
        result["siniestros"].pct_change() * 100
    ).round(2)
    return result


def _make_charts(summary: pd.DataFrame, yearly: pd.DataFrame, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    yearly_totals = (
        yearly.groupby("año", as_index=False)
        .agg(siniestros=("siniestros", "sum"), fatales=("fatales", "sum"))
        .sort_values("año")
    )
    fig, ax1 = plt.subplots(figsize=(10, 5.5))
    ax1.plot(yearly_totals["año"], yearly_totals["siniestros"], marker="o", color="#1f77b4")
    ax1.set_ylabel("Siniestros", color="#1f77b4")
    ax1.set_xlabel("Año")
    ax1.grid(axis="y", alpha=0.25)
    ax2 = ax1.twinx()
    ax2.bar(yearly_totals["año"], yearly_totals["fatales"], alpha=0.25, color="#c0392b", width=0.55)
    ax2.set_ylabel("Siniestros fatales", color="#c0392b")
    ax1.set_title("Evolución anual del volumen y fatalidad")
    fig.tight_layout()
    path = output_dir / "intersecciones_tendencia_anual.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    paths.append(path)

    top = summary.head(15).sort_values("severidad")
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(top["interseccion"], top["severidad"], color="#7b2cbf")
    ax.set_xlabel("Índice de severidad acumulado")
    ax.set_title("15 intersecciones con mayor severidad acumulada")
    fig.tight_layout()
    path = output_dir / "intersecciones_top_severidad.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    paths.append(path)

    top_names = summary.head(12)["interseccion"].tolist()
    heat = yearly[yearly["interseccion"].isin(top_names)].pivot(
        index="interseccion", columns="año", values="siniestros"
    ).fillna(0)
    heat = heat.reindex(top_names)
    fig, ax = plt.subplots(figsize=(10, 6.5))
    image = ax.imshow(heat.values, aspect="auto", cmap="YlOrRd")
    ax.set_yticks(range(len(heat.index)), labels=heat.index)
    ax.set_xticks(range(len(heat.columns)), labels=[str(x) for x in heat.columns])
    ax.set_xlabel("Año")
    ax.set_title("Evolución de siniestros en las 12 intersecciones más severas")
    fig.colorbar(image, ax=ax, label="Siniestros")
    fig.tight_layout()
    path = output_dir / "intersecciones_heatmap_anual.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    paths.append(path)
    return paths


def _trend_text(yearly_summary: pd.DataFrame) -> list[str]:
    first = yearly_summary.iloc[0]
    last = yearly_summary.iloc[-1]
    volume_change = (last["siniestros"] / first["siniestros"] - 1) * 100
    peak = yearly_summary.loc[yearly_summary["siniestros"].idxmax()]
    fatal_peak = yearly_summary.loc[yearly_summary["fatales"].idxmax()]
    direction = "aumentó" if volume_change >= 0 else "disminuyó"
    return [
        f"El histórico abarca {int(first['año'])}-{int(last['año'])}. Entre el primer y último año, el volumen {direction} {abs(volume_change):.1f}% ({int(first['siniestros']):,} a {int(last['siniestros']):,} siniestros).",
        f"El máximo volumen se observó en {int(peak['año'])}, con {int(peak['siniestros']):,} siniestros y {int(peak['intersecciones_activas']):,} intersecciones activas.",
        f"El mayor número de eventos fatales se observó en {int(fatal_peak['año'])}, con {int(fatal_peak['fatales']):,} casos.",
        "Las variaciones anuales deben interpretarse junto con cambios en cobertura, captura y geocodificación; un aumento de registros no prueba por sí solo un aumento real de riesgo.",
    ]


def _observations(summary: pd.DataFrame, yearly_summary: pd.DataFrame, missing: int) -> list[str]:
    total = summary["siniestros"].sum()
    top10 = summary.head(10)["siniestros"].sum()
    concentration = top10 / total * 100
    vulnerable = summary["usuarios_vulnerables"].sum()
    fatal = summary["fatales"].sum()
    return [
        f"Se identificaron {len(summary):,} intersecciones con ambos nombres de calle y {int(total):,} siniestros asociados. {missing:,} registros ({missing / (total + missing) * 100:.2f}%) no tenían una segunda calle válida y se excluyeron del ranking de intersecciones.",
        f"Las 10 intersecciones más severas concentran {concentration:.1f}% de los siniestros clasificados como intersección. Esto sugiere priorizar intervenciones focalizadas, sin concluir que el resto de la red sea irrelevante.",
        f"Se contabilizaron {int(fatal):,} siniestros fatales y {int(vulnerable):,} eventos con peatones, ciclistas o motocicletas involucrados. La severidad debe analizarse junto con exposición y aforos reales antes de asignar causalidad.",
        f"El promedio de intersecciones activas por año fue {yearly_summary['intersecciones_activas'].mean():,.0f}; la cobertura espacial cambia con el tiempo, por lo que conviene comparar también tasas normalizadas cuando existan aforos o población expuesta.",
    ]


def _html_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    data = frame if max_rows is None else frame.head(max_rows)
    return data.to_html(index=False, classes="data-table", border=0, float_format=lambda value: f"{value:,.2f}")


def _image_data_uri(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _write_pdf(
    path: Path,
    yearly_summary: pd.DataFrame,
    summary: pd.DataFrame,
    trend_text: list[str],
    observations: list[str],
    chart_paths: list[Path],
) -> None:
    from matplotlib.backends.backend_pdf import PdfPages

    with PdfPages(path) as pdf:
        pages: list[tuple[str, list[str]]] = [
            (
                "Reporte general de intersecciones viales",
                [
                    "Sistema de revisión de siniestros · Chihuahua",
                    "Cobertura: histórico completo disponible en la fuente procesada.",
                    "",
                    "Resumen ejecutivo",
                    *trend_text,
                    "",
                    "Observaciones de calidad y priorización",
                    *observations,
                ],
            ),
            ("Indicadores anuales", []),
            ("Intersecciones prioritarias", []),
        ]
        for title, lines in pages:
            fig = plt.figure(figsize=(8.27, 11.69))
            fig.text(0.07, 0.94, title, fontsize=18, weight="bold", va="top")
            y = 0.88
            for line in lines:
                fig.text(0.07, y, line, fontsize=10, va="top", wrap=True)
                y -= 0.045 if len(line) < 130 else 0.075
            if title == "Indicadores anuales":
                table = yearly_summary.round(2).to_string(index=False)
                fig.text(0.07, 0.87, table, family="monospace", fontsize=8, va="top")
            if title == "Intersecciones prioritarias":
                table = summary.head(20)[
                    ["ranking", "interseccion", "siniestros", "severidad", "fatales", "usuarios_vulnerables"]
                ].to_string(index=False)
                fig.text(0.07, 0.87, table, family="monospace", fontsize=8, va="top")
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
        for chart in chart_paths:
            image = plt.imread(chart)
            fig, ax = plt.subplots(figsize=(11.69, 8.27))
            ax.imshow(image)
            ax.axis("off")
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)


def generate_intersection_report(accidents: pd.DataFrame) -> list[Path]:
    summary, yearly, missing = _intersection_data(accidents)
    yearly_summary = _yearly_summary(accidents, yearly)
    chart_dir = REPORTS_DIR / "graficas_intersecciones"
    chart_paths = _make_charts(summary, yearly, chart_dir)
    summary_path = REPORTS_DIR / "intersecciones_historico.csv"
    yearly_path = REPORTS_DIR / "intersecciones_tendencia_anual.csv"
    summary.to_csv(summary_path, index=False, encoding="utf-8")
    yearly_summary.to_csv(yearly_path, index=False, encoding="utf-8")

    trend_text = _trend_text(yearly_summary)
    observations = _observations(summary, yearly_summary, missing)
    html_path = REPORTS_DIR / "reporte_intersecciones_historico.html"
    chart_html = "\n".join(
        f'<figure><img src="{_image_data_uri(chart)}"><figcaption>{html.escape(chart.stem.replace("_", " ").title())}</figcaption></figure>'
        for chart in chart_paths
    )
    html_content = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Reporte general de intersecciones</title>
<style>
body {{ font-family: Arial, sans-serif; max-width: 1250px; margin: 2rem auto; color: #202124; line-height: 1.45; }}
h1, h2 {{ color: #3d246c; }} .note {{ background: #f4f1fa; padding: 1rem; border-left: 4px solid #7b2cbf; }}
figure {{ margin: 1.5rem 0; }} img {{ max-width: 100%; }} figcaption {{ text-align: center; color: #555; }}
.data-table {{ border-collapse: collapse; width: 100%; font-size: .82rem; }} .data-table th, .data-table td {{ border: 1px solid #ddd; padding: .35rem; }} .data-table th {{ background: #eee; }}
</style></head><body>
<h1>Reporte general de intersecciones viales</h1>
<p><strong>Municipio/ámbito:</strong> Chihuahua · <strong>Histórico:</strong> {int(yearly_summary['año'].min())}-{int(yearly_summary['año'].max())}</p>
<div class="note"><strong>Alcance:</strong> el reporte agrega todos los registros con dos calles normalizadas. No contiene coordenadas ni registros individuales; las cifras son agregadas por intersección.</div>
<h2>Resumen ejecutivo</h2><ul>{"".join(f"<li>{html.escape(item)}</li>" for item in trend_text)}</ul>
<h2>Observaciones técnicas</h2><ul>{"".join(f"<li>{html.escape(item)}</li>" for item in observations)}</ul>
<h2>Tendencia anual</h2>{_html_table(yearly_summary)}
<h2>Gráficas</h2>{chart_html}
<h2>20 intersecciones prioritarias</h2>{_html_table(summary[['ranking','interseccion','siniestros','severidad','severidad_promedio','fatales','muertos','heridos','usuarios_vulnerables','tasa_fatalidad_pct']].head(20))}
<h2>Catálogo completo de intersecciones</h2>
<p>El archivo <code>intersecciones_historico.csv</code> contiene el catálogo completo y el archivo <code>intersecciones_tendencia_anual.csv</code> contiene la serie anual.</p>
{_html_table(summary)}
</body></html>"""
    html_path.write_text(html_content, encoding="utf-8")

    pdf_path = REPORTS_DIR / "reporte_intersecciones_historico.pdf"
    _write_pdf(pdf_path, yearly_summary, summary, trend_text, observations, chart_paths)
    return [summary_path, yearly_path, html_path, pdf_path, *chart_paths]
