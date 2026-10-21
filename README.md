# Sistema de revisión de siniestros viales

Aplicación para explorar la siniestralidad vial de Chihuahua, generar rankings y producir fichas PDF para cruces, tramos, vialidades y zonas críticas.

## Contenido del repositorio

El repositorio está preparado para revisión académica y contiene:

- `app.py`: interfaz web local con Streamlit.
- `run_pipeline.py`: ejecución completa del pipeline.
- `src/`: cálculo de indicadores, rankings y mapa.
- `reports/`: rankings agregados Top 50 y metadatos.
- `docs/`: propuesta del proyecto.
- `requirements.txt`: dependencias de Python.

Por privacidad y seguridad, Git no incluye:

- fuentes originales de accidentes, comercios, población, clima y red vial;
- capas GeoJSON y Parquet, además de capas procesadas que no son necesarias para ejecutar la aplicación;
- mapas HTML generados, cachés, bytecode, archivos temporales y reportes individuales;
- credenciales, archivos `.env` o configuraciones locales.

La aplicación incluye tres GeoPackage procesados y agregados en `data/processed/`, suficientes para ejecutar el mapa y Streamlit sin solicitar archivos adicionales. Las fuentes crudas permanecen fuera del repositorio.

## Requisitos

- Python 3.10 o posterior.
- Dependencias del archivo `requirements.txt`.
- El repositorio ya incluye estos tres insumos procesados en `data/processed/`:

  - `siniestros_asignados.gpkg`
  - `tramos_con_metricas.gpkg`
  - `puntos_criticos.gpkg`

Estos archivos contienen información geoespacial y registros derivados de una fuente pública; no contienen API keys, credenciales ni archivos personales del autor. Las fuentes originales completas no forman parte del repositorio.

## Instalación y ejecución

Desde esta carpeta:

```bash
python -m venv .venv
source .venv/bin/activate       # macOS/Linux
# .venv\Scripts\activate        # Windows
python -m pip install -r requirements.txt
```

```bash
python run_pipeline.py
streamlit run app.py
```

`run_pipeline.py` actualiza los extractos analíticos y genera el mapa Folium en `outputs/mapa_siniestralidad_chihuahua.html`. La aplicación Streamlit muestra ese mapa, permite descargarlo y presenta los rankings agregados.

El mismo pipeline genera un reporte general de todas las intersecciones válidas del histórico. Incluye explicaciones ejecutivas, observaciones de calidad, tendencias anuales, gráficas, tabla de priorización y el catálogo completo de intersecciones.

El pipeline genera:

- `reports/top_50_intersecciones.csv`
- `reports/top_50_tramos.csv`
- `reports/top_50_vialidades.csv`
- `reports/top_50_zonas.csv`
- `data/processed/*_modelo.parquet`
- `reports/metadatos.json`
- `reports/intersecciones_historico.csv`: catálogo completo de intersecciones válidas.
- `reports/intersecciones_tendencia_anual.csv`: indicadores agregados por año.
- `reports/reporte_intersecciones_historico.html`: reporte navegable con texto, tablas y gráficas.
- `reports/reporte_intersecciones_historico.pdf`: versión portable para revisión.

Los archivos generados que puedan contener geometrías detalladas o información de registros individuales están excluidos por `.gitignore`.

## Funcionalidades

- capas de tramos por nivel de riesgo;
- comparación de periodos 2019-2024 y 2022-2024;
- mapas de calor y zonas calientes Gi*;
- puntos críticos numerados con ficha emergente;
- rankings de intersecciones, tramos, vialidades y zonas;
- generación local de fichas PDF.

## Interpretación del aforo relativo

El sistema no contiene conteos observados de vehículos. `aforo_relativo` es un índice proxy de 0 a 100 construido con volumen de siniestros, severidad y participación de peatones, ciclistas y motocicletas. Sirve para priorización comparativa; no representa vehículos por hora.

Si se incorporan aforos reales, deben agregarse como una fuente versionada con fecha, ubicación, sentido, periodo de medición y metodología. El índice proxy no debe mezclarse automáticamente con esa medición.

## Limitaciones conocidas

- El salto de registros de 2021 requiere validación con la fuente antes de usar tendencias temporales como objetivo predictivo.
- Los puntos críticos reflejan concentración de siniestros y pueden estar afectados por geocodificación apilada.
- Los rankings incluidos son agregados y no sustituyen una auditoría de campo.
