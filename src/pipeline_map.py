"""Fase 6: mapa interactivo (folium/Leaflet) y mapa estático (matplotlib)."""
import geopandas as gpd, pandas as pd, numpy as np, json, folium
from folium.plugins import HeatMap
from shapely import set_precision
from config import *

COLORES = {0:"#b5b5b5", 1:"#2e9e5b", 2:"#f2d024", 3:"#f28c28", 4:"#d7301f", 5:"#8e24aa"}
NOMBRES = {0:"Sin siniestros", 1:"Bajo", 2:"Medio", 3:"Alto", 4:"Muy alto", 5:"Crítico"}
ANCHO = {"primaria":4.5, "secundaria":3.2, "local":2.2}
idx = {e:i+1 for i, e in enumerate(ETIQUETAS)}; idx["Sin siniestros"] = 0

seg = gpd.read_file("../data/processed/tramos_con_metricas.gpkg")
seg["nt"] = seg.nivel_todos.map(idx); seg["nr"] = seg.nivel_reciente.map(idx)
puntos = gpd.read_file("../data/processed/puntos_criticos.gpkg")
hexg = gpd.read_file("../data/processed/hotspots_gi.gpkg")
sin = gpd.read_file("../data/processed/siniestros_asignados.gpkg")

# La salida histórica del proyecto usa z-score/p-valor; la versión del pipeline
# usa niveles de confianza. Se normaliza aquí para conservar la misma lectura
# visual sin alterar los datos originales.
if "conf_todos" not in hexg:
    confidence = hexg["p_valor"].abs().map(
        lambda value: 99 if value <= 0.01 else 95 if value <= 0.05 else 0
    )
    hexg["conf_todos"] = confidence
    hexg["conf_reciente"] = confidence
    hexg["sev_todos"] = hexg["indice_severidad_total"]
    hexg["sev_reciente"] = hexg["indice_severidad_total"]

# ---------- selección de tramos para el mapa ----------
m_sel = (seg.n_todos > 0) | (seg.jerarquia.isin(["primaria","secundaria"]))
mp = seg[m_sel].copy()
mp = mp.sort_values("nt")          # los más críticos se dibujan al final (encima)
g4 = mp.geometry.simplify(2).to_crs(CRS_WEB)
def coords(geom):
    g = set_precision(geom, 1e-5)
    parts = [g] if g.geom_type == "LineString" else list(g.geoms)
    return [[[round(x,5), round(y,5)] for x, y in p.coords] for p in parts]
feats = []
for (i, r), geom in zip(mp.iterrows(), g4):
    if geom.is_empty: continue
    cs = coords(geom)
    feats.append({"type":"Feature",
      "geometry":{"type":"LineString","coordinates":cs[0]} if len(cs)==1 else {"type":"MultiLineString","coordinates":cs},
      "properties":{"nm":r.nombre_via, "j":r.jerarquia[:3], "L":int(round(r.longitud_m)), "nt":int(r.nt), "nr":int(r.nr),
        "t":[int(r.n_todos), int(r.fatales_todos), int(r.muertos_todos), int(r.heridos_todos), int(r.sev_todos)],
        "r":[int(r.n_reciente), int(r.fatales_reciente), int(r.muertos_reciente), int(r.heridos_reciente), int(r.sev_reciente)],
        "ti":r.tipo_dominante or "", "ca":r.causa_dominante or "", "hp":int(r.hora_pico) if r.n_todos>0 else -1, "dp":r.dia_pico or "",
        "pc":[int(r.n_peaton), int(r.n_ciclista), int(r.n_moto)]}})
geo = {"type":"FeatureCollection","features":feats}
print("tramos en el mapa:", len(feats))

# ---------- mapa ----------
cen = sin.to_crs(CRS_WEB).geometry
m = folium.Map(
    location=[28.66, -106.08],
    zoom_start=12,
    tiles="OpenStreetMap",
    prefer_canvas=True,
    control_scale=True,
)
gj = folium.GeoJson(geo, name="Tramos de riesgo", smooth_factor=0.5,
        style_function=lambda f: {"color":COLORES[f["properties"]["nt"]], "weight":ANCHO[{"pri":"primaria","sec":"secundaria","loc":"local"}[f["properties"]["j"]]] if f["properties"]["nt"]>0 else 1.6,
                                  "opacity":0.95 if f["properties"]["nt"]>0 else 0.55})
gj.add_to(m)

# calor (dos periodos)
for suf, (a, b), vis in (("todos", PERIODOS["todos"], False), ("reciente", PERIODOS["reciente"], False)):
    d = sin[(sin["año"]>=a)&(sin["año"]<=b)].to_crs(CRS_WEB)
    k = d.assign(lat=d.geometry.y.round(4), lon=d.geometry.x.round(4)).groupby(["lat","lon"]).indice_severidad.sum().reset_index()
    k["w"] = (k.indice_severidad / k.indice_severidad.quantile(0.995)).clip(upper=1)
    fg = folium.FeatureGroup(name=f"Mapa de calor {a}-{b}", show=vis)
    HeatMap(k[["lat","lon","w"]].values.tolist(), radius=13, blur=16, min_opacity=0.25, max_zoom=15).add_to(fg)
    fg.add_to(m)

# zonas calientes Gi* (95 y 99 %), ocultas por defecto
for suf, (a,b) in PERIODOS.items():
    h = hexg[hexg[f"conf_{suf}"]>=95].to_crs(CRS_WEB)
    fg = folium.FeatureGroup(name=f"Zonas calientes Gi* {a}-{b} (conf. ≥95 %)", show=False)
    for _, r in h.iterrows():
        folium.Polygon([(y,x) for x,y in r.geometry.exterior.coords], color="#8e24aa" if r[f"conf_{suf}"]==99 else "#c779d4",
                       weight=0.5, fill=True, fill_opacity=0.35,
                       tooltip=f"Gi* confianza {int(r[f'conf_{suf}'])} % · severidad en celda: {int(r[f'sev_{suf}'])}").add_to(fg)
    fg.add_to(m)

# puntos críticos
p4 = puntos.to_crs(CRS_WEB)
fg = folium.FeatureGroup(name=f"Puntos críticos (top {len(p4)}, 2019-2024)", show=True)
for _, r in p4.iterrows():
    gi = f"{int(r.conf_gi_todos)} %" if r.conf_gi_todos else "no significativa"
    pop = (f"<b>#{int(r.ranking)} · {r.vialidades.title()}</b><br>Siniestros: {int(r.n_siniestros)} (2022-24: {int(r.n_reciente)})<br>"
           f"Fatales: {int(r.fatales)} · Muertos: {int(r.muertos)} · Heridos: {int(r.heridos)}<br>Peatón/ciclista: {int(r.n_peaton_ciclista)}<br>"
           f"Tipo dominante: {r.tipo_dominante}<br>Hora pico: {int(r.hora_pico):02d}:00<br>Zona Gi*: {gi}")
    folium.Marker([r.geometry.y, r.geometry.x], popup=folium.Popup(pop, max_width=300),
        tooltip=f"#{int(r.ranking)} {r.vialidades.title()}",
        icon=folium.DivIcon(html=f'<div style="background:#c62828;color:#fff;border:2px solid #fff;border-radius:50%;width:22px;height:22px;line-height:18px;text-align:center;font:bold 10px Arial;box-shadow:0 0 3px #000">{int(r.ranking)}</div>',
                            icon_size=(22,22), icon_anchor=(11,11))).add_to(fg)
fg.add_to(m)
folium.LayerControl(collapsed=False, position="topright").add_to(m)

leyenda = """
<style>
.pnl{position:fixed;z-index:9999;background:rgba(255,255,255,.96);border-radius:8px;box-shadow:0 1px 8px rgba(0,0,0,.35);font:13px/1.35 Arial,sans-serif;color:#222}
.pnl h4{margin:0 0 6px;font-size:14px}
.sw{display:inline-block;width:26px;height:5px;border-radius:2px;margin-right:8px;vertical-align:middle}
</style>
<div class="pnl" style="left:12px;bottom:28px;padding:10px 14px;max-width:290px">
<h4>Siniestralidad vial · Chihuahua</h4>
<div style="margin-bottom:6px"><b>Periodo:</b><br>
<label><input type="radio" name="per" value="t" checked onchange="setPer('t')"> 2019-2024 (todos)</label><br>
<label><input type="radio" name="per" value="r" onchange="setPer('r')"> 2022-2024 (reciente)</label></div>
<b>Nivel de riesgo del tramo</b><br>
%s
<div style="margin-top:6px"><span style="display:inline-block;width:18px;height:18px;line-height:15px;text-align:center;background:#c62828;color:#fff;border-radius:50%%;font:bold 9px Arial;vertical-align:middle;margin-right:6px">1</span>Punto crítico (ranking)</div>
<div style="margin-top:6px;font-size:11px;color:#555">Nivel = severidad por km suavizada (Empirical Bayes). Grosor: vías primarias &gt; secundarias &gt; locales. Fuente: INEGI, 2019-2024. Nota: 2021 muestra un volumen de registros atípicamente alto; interpretar tendencias con cautela.</div>
</div>
""" % "".join(f'<div><span class="sw" style="background:{COLORES[i]}"></span>{NOMBRES[i]}</div>' for i in (5,4,3,2,1,0))
m.get_root().html.add_child(folium.Element(leyenda))
js = """
<script>
window.addEventListener('load', function(){
  var C=%s, N=%s, W={pri:4.5,sec:3.2,loc:2.2}, P='t', capa=%s;
  var T={t:'2019-2024',r:'2022-2024'};
  function estilo(f){var n=f.properties['n'+P]; return {color:C[n], weight:n>0?W[f.properties.j]:1.6, opacity:n>0?0.95:0.55};}
  window.setPer=function(p){P=p; capa.setStyle(estilo); capa.eachLayer(function(l){if(l.feature.properties['n'+P]>=4) l.bringToFront();});};
  var hrs=function(h){return h<0?'—':(h<10?'0':'')+h+':00';};
  capa.eachLayer(function(l){
    var pr=l.feature.properties;
    l.bindTooltip(function(){var n=pr['n'+P];return '<b>'+pr.nm+'</b> · '+N[n];},{sticky:true});
    l.bindPopup(function(){
      var d=pr[P], n=pr['n'+P];
      var s='<div style="min-width:210px"><b>'+pr.nm+'</b><br><span style="color:'+C[n]+'">&#9632;</span> Riesgo: <b>'+N[n]+'</b> ('+T[P]+')<br>'+
        'Tramo de '+pr.L+' m · vía '+(pr.j=='pri'?'primaria':pr.j=='sec'?'secundaria':'local')+'<hr style="margin:4px 0">'+
        'Siniestros: <b>'+d[0]+'</b> · Fatales: '+d[1]+'<br>Muertos: '+d[2]+' · Heridos: '+d[3]+'<br>Índice de severidad: '+d[4];
      if(pr.t[0]>0) s+='<br>Peatón/ciclista/moto: '+pr.pc[0]+'/'+pr.pc[1]+'/'+pr.pc[2]+'<br>Tipo dominante: '+pr.ti+'<br>Causa dominante: '+pr.ca+'<br>Hora pico: '+hrs(pr.hp)+' · Día: '+pr.dp+'<br><i style="font-size:11px">Datos descriptivos: 2019-2024</i>';
      return s+'</div>';});
  });
});
</script>
""" % (json.dumps({str(k):v for k,v in COLORES.items()}), json.dumps({str(k):v for k,v in NOMBRES.items()}), gj.get_name())
# las propiedades nt/nr se acceden como 'n'+P -> renombrar en los datos a n t / n r
m.get_root().html.add_child(folium.Element(js))
m.save("../outputs/mapa_siniestralidad_chihuahua.html")
import os; print("HTML MB:", round(os.path.getsize("../outputs/mapa_siniestralidad_chihuahua.html")/1e6,1))
