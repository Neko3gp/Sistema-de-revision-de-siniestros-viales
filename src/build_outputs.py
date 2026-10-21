from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from analytics import (
    REPORTS_DIR,
    load_data,
    intersection_ranking,
    road_ranking,
    segment_ranking,
    top_rows,
    write_ml_extract,
    zone_ranking,
)
from intersection_report import generate_intersection_report


def main() -> None:
    accidents, segments, points = load_data()
    rankings = {
        "top_50_intersecciones": top_rows(intersection_ranking(accidents)),
        "top_50_tramos": top_rows(segment_ranking(segments)),
        "top_50_vialidades": top_rows(road_ranking(segments)),
        "top_50_zonas": top_rows(zone_ranking(points)),
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    for name, frame in rankings.items():
        frame.drop(columns=["geometry"], errors="ignore").to_csv(
            REPORTS_DIR / f"{name}.csv", index=False, encoding="utf-8"
        )
    ml_outputs = write_ml_extract(accidents, segments, points)
    intersection_outputs = generate_intersection_report(accidents)
    metadata = {
        "version": "1.0",
        "descripcion": "Extractos analíticos para revisión y futura modelación predictiva.",
        "aforo_relativo": "Índice proxy 0-100; no representa vehículos observados.",
        "fuentes": {
            "siniestros": str(Path("data/raw/siniestros_limpios.gpkg")),
            "red_vial": str(Path("data/raw/red_vial_chihuahua.gpkg")),
        },
        "salidas_parquet": [str(path.relative_to(Path(__file__).resolve().parents[1])) for path in ml_outputs],
    }
    (REPORTS_DIR / "metadatos.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Salidas generadas:")
    for path in [*rankings.keys(), *ml_outputs, *intersection_outputs]:
        print(path)


if __name__ == "__main__":
    main()
