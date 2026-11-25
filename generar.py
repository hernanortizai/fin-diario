import requests, html
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

ARG = timezone(timedelta(hours=-3))
UA = {"User-Agent": "Mozilla/5.0"}

FAV_ACCIONES = ["ALUA","BMA","CEPU","GGAL","LOMA","PAMP","TXAR","YPFD"]
FAV_CEDEARS  = ["AAPL","AMZN","GOOGL","KO","MELI","MSFT","NVDA","TSLA"]
FAV_BONOS    = ["AE38","AL30","AL35","GD30","GD35","GD38","GD41"]

# Universo para "mejores del mes" (editalo a gusto)
UNI_ACCIONES = ["ALUA","BMA","CEPU","GGAL","LOMA","PAMP","TXAR","YPFD","BBAR","TGNO4","COME","TECO2","TGSU2","VALO","SUPV","CRES","EDN","MIRG","TRAN","CVH"]
UNI_CEDEARS  = ["AAPL","AMZN","GOOGL","KO","MELI","MSFT","NVDA","TSLA","META","JPM","DIS","BABA","AMD","NFLX","PBR","VIST","SPY","QQQ","GLOB","MRNA"]
UNI_BONOS    = ["AL29","AL30","AL35","AE38","AL41","GD29","GD30","GD35","GD38","GD41","GD46"]

def get(url):
    r = requests.get(url, headers=UA, timeout=25)
    r.raise_for_status()
    return r

def fmt(n, d=2):
    if n is None: return "-"
    return f"{n:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def pct(n):
    cls = "pos" if n >= 0 else "neg"
    return f"<td class='{cls}'>{fmt(n)}%</td>"

def safe(fn, default):
    try: return fn()
    except Exception as e:
        print("ERROR:", fn.__name__ if hasattr(fn, "__name__") else "", e)
        return default

# ---------- Dolar y riesgo pais ----------
def dolares():
    return get("https://dolarapi.com/v1/dolares").json()

def riesgo():
    j = get("https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais/ultimo").json()
    return j["valor"], j["fecha"]

def sec_dolar():
    d = safe(dolares, [])
    rp = safe(riesgo, (None, ""))
    by = {x["casa"]: x for x in d}
    cards = ""
    for casa, nom in [("oficial","Dólar Oficial"),("bolsa","Dólar MEP"),("contadoconliqui","Dólar CCL")]:
        if casa in by:
            cards += f"<div class='card'><div class='mut'>{nom}</div><div class='big'>$ {fmt(by[casa]['venta'])}</div></div>"
    if rp[0] is not None:
        cards += f"<div class='card'><div class='mut'>Riesgo país</div><div class='big'>{fmt(rp[0],0)}</div><div class='mut'>{rp[1]}</div></div>"
    if "oficial" in by and "contadoconliqui" in by:
        b = (by["contadoconliqui"]["venta"] / by["oficial"]["venta"] - 1) * 100
        cards += f"<div class='card'><div class='mut'>Brecha CCL vs oficial</div><div class='big'>{fmt(b,1)}%</div></div>"
    rows = ""
    for x in d:
        rows += f"<tr><td>{html.escape(x['nombre'])}</td><td>{fmt(x.get('compra'))}</td><td>{fmt(x.get('venta'))}</td><td>{x.get('fechaActualizacion','')[:16].replace('T',' ')}</td></tr>"
    return (f"<h2>Dólar y riesgo país</h2><div class='grid'>{cards}</div>"
            f"<div class='card scroll' style='margin-top:14px'><table><tr><th>Tipo</th><th>Compra</th><th>Venta</th><th>Actualizado</th></tr>{rows}</table></div>")

# ---------- Tablas de mercado ----------
def tabla(titulo, filas):
    body = ""
    for r in filas:
        body += (f"<tr><td class='sim'>{html.escape(str(r['symbol']))}</td><td>{fmt(r['c'])}</td>"
                 f"{pct(r['pct_change'])}<td>{fmt(r.get('v',0),0)}</td></tr>")
    return (f"<div class='card scroll'><div class='mut'>{titulo}</div><table>"
            f"<tr><th>Símbolo</th><th>Último</th><th>Var. %</th><th>Volumen</th></tr>{body}</table></div>")

def live(tipo):
    return [x for x in get(f"https://data912.com/live/{tipo}").json() if x.get("c")]

def bloque_mercado(titulo, tipo_live, favs):
    data = safe(lambda: live(tipo_live), [])
    by = {x["symbol"]: x for x in data}
    fav = [by[s] for s in favs if s in by]
    top = sorted(data, key=lambda x: x.get("v") or 0, reverse=True)[:40]
    top = [x for x in top if x.get("pct_change") is not None]
    sube = sorted(top, key=lambda x: x["pct_change"], reverse=True)[:6]
    baja = sorted(top, key=lambda x: x["pct_change"])[:6]
    return (f"<h2>{titulo}</h2>" + tabla("Mis favoritos", fav) +
            "<div class='grid2' style='margin-top:14px'>" +
            tabla("Los que más suben (entre los más operados)", sube) +
            tabla("Los que más bajan (entre los más operados)", baja) + "</div>")

# ---------- Ranking del mes ----------
def rend(args):
    tipo, t = args
    try:
        h = get(f"https://data912.com/historical/{tipo}/{t}").json()
        h = sorted(h, key=lambda x: x["date"])
        limite = (datetime.now(ARG) - timedelta(days=30)).strftime("%Y-%m-%d")
        prev = [x for x in h if x["date"] <= limite]
        if not prev: return None
        return (t, (h[-1]["c"] / prev[-1]["c"] - 1) * 100)
    except Exception:
        return None

def ranking(tipo, tickers):
    with ThreadPoolExecutor(8) as ex:
        res = [r for r in ex.map(rend, [(tipo, t) for t in tickers]) if r]
    return sorted(res, key=lambda x: x[1], reverse=True)

def tabla_mes(titulo, rows):
    body = "".join(f"<tr><td class='sim'>{t}</td>{pct(v)}</tr>" for t, v in rows)
    return (f"<div class='card scroll'><div class='mut'>{titulo}</div><table>"
            f"<tr><th>Símbolo</th><th>Rend. 30 días</th></tr>{body}</table></div>")

def sec_mes():
    out = "<h2>Mejores y peores del mes (30 días)</h2>"
    for nombre, tipo, uni in [("Acciones","stocks",UNI_ACCIONES),("CEDEARs","cedears",UNI_CEDEARS),("Bonos","bonds",UNI_BONOS)]:
        r = safe(lambda: ranking(tipo, uni), [])
        if not r: continue
        out += (f"<div class='grid2' style='margin-top:14px'>" +
                tabla_mes(f"{nombre}: mejores del mes", r[:5]) +
                tabla_mes(f"{nombre}: peores del mes", r[::-1][:5]) + "</div>")
    return out

# ---------- Noticias ----------
def sec_noticias():
    def f():
        url = "https://news.google.com/rss/search?q=riesgo+pa%C3%ADs+d%C3%B3lar+merval+when:1d&hl=es-419&gl=AR&ceid=AR:es-419"
        root = ET.fromstring(get(url).content)
        items = []
        for it in root.iter("item"):
            items.append((it.findtext("title"), it.findtext("link"), it.findtext("pubDate")))
        return items[:12]
    items = safe(f, [])
    body = ""
    for t, l, d in items:
        try: d = parsedate_to_datetime(d).astimezone(ARG).strftime("%d/%m %H:%M")
        except Exception: pass
        body += f"<div class='nota-item'><a href='{html.escape(l)}' target='_blank' rel='noopener noreferrer'>{html.escape(t)}</a><div class='mut'>{d}</div></div>"
    return f"<h2>Noticias de las últimas 24 h</h2><div class='card'>{body}</div>"

CSS = """:root{--bg:#0b0d10;--card:#14171c;--line:#23272e;--txt:#e8eaed;--mut:#8b929c;--acc:#e8a33d;--pos:#4cc38a;--neg:#e5645b}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);font:15px/1.5 system-ui,Segoe UI,sans-serif}
.wrap{max-width:1150px;margin:0 auto;padding:32px 24px 60px}
.kicker{color:var(--acc);letter-spacing:.18em;font-size:12px;font-weight:700;text-transform:uppercase}
.fecha{color:var(--mut);margin:4px 0 24px}
h2{font-size:12px;letter-spacing:.16em;color:var(--mut);text-transform:uppercase;margin:34px 0 12px;font-weight:600}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:14px}
.big{font-size:26px;font-weight:700}
.mut{color:var(--mut);font-size:13px}
table{width:100%;border-collapse:collapse;font-size:14px;margin-top:8px}
th{color:var(--mut);font-weight:600;text-align:right;padding:8px 10px;border-bottom:1px solid var(--line);font-size:12px;text-transform:uppercase;letter-spacing:.06em}
td{padding:9px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left}
.sim{font-weight:700}
.pos{color:var(--pos)}.neg{color:var(--neg)}
.scroll{overflow-x:auto}
.nota-item{padding:10px 0;border-bottom:1px solid var(--line)}
.nota-item a{color:var(--txt);text-decoration:none}
.nota-item a:hover{color:var(--acc)}
.nota{color:var(--mut);font-size:12px;margin-top:30px}"""

def main():
    ahora = datetime.now(ARG).strftime("%d/%m/%Y %H:%M")
    partes = [
        sec_dolar(),
        bloque_mercado("Acciones argentinas (BYMA)", "arg_stocks", FAV_ACCIONES),
        bloque_mercado("CEDEARs", "arg_cedears", FAV_CEDEARS),
        bloque_mercado("Bonos argentinos", "arg_bonds", FAV_BONOS),
        sec_mes(),
        sec_noticias(),
    ]
    page = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Finanzas hoy</title><style>{CSS}</style></head>
<body><div class="wrap">
<div class="kicker">Finanzas hoy</div>
<div class="fecha">{ahora} (hora Argentina) · mercado argentino y mundo · datos públicos</div>
{''.join(partes)}
<div class="nota">Precios de data912 son referenciales y pueden tener demora (no son tiempo real): confirmá siempre en IOL antes de operar.
Este panel ordena información; no es asesoramiento financiero y las decisiones son tuyas.</div>
</div></body></html>"""
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(page)
    print("OK index.html generado", ahora)

main()
