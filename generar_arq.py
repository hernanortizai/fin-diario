import requests, html, re, os, time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

ARG = timezone(timedelta(hours=-3))
UA = {"User-Agent": "Mozilla/5.0 (compatible; arq-diario/1.0)"}
NOW = datetime.now(timezone.utc)

def gn(q):
    return "https://news.google.com/rss/search?q=" + quote_plus(q) + "&hl=es-419&gl=AR&ceid=AR:es-419"

FEEDS_INT = [
    ("Dezeen", "https://www.dezeen.com/architecture/feed/"),
    ("ArchDaily", "https://www.archdaily.com/feed"),
    ("Designboom", "https://www.designboom.com/architecture/feed/"),
]
FEEDS_ES = [
    ("Plataforma Arquitectura", "https://www.plataformaarquitectura.cl/cl/feed"),
    ("Noticias", gn("arquitectura Argentina obra OR proyecto OR estudio when:7d")),
]
FEEDS_CONC = [("Noticias", gn('concurso arquitectura OR "concurso de anteproyectos" OR "concurso de ideas" when:30d'))]
FEEDS_MERC = [("Noticias", gn('construcción Argentina OR "permisos de obra" OR "crédito hipotecario" OR "costo de construcción" when:7d'))]

RECURSOS = [
    ("Bustler", "https://bustler.net", "Concursos de arquitectura del mundo"),
    ("Competitions.archi", "https://competitions.archi", "Agenda de concursos internacionales"),
    ("Archinect", "https://archinect.com", "Noticias, trabajos y comunidad"),
    ("Architizer", "https://architizer.com", "Premios y visibilidad de proyectos"),
    ("Sociedad Central de Arquitectos", "https://socearq.org", "Concursos y actividades en Argentina"),
    ("FADEA", "https://www.fadea.org.ar", "Federación Argentina de Entidades de Arquitectos"),
    ("ArchDaily", "https://www.archdaily.com", "Publicá tus obras terminadas"),
]

TIPS = [
    "Escribí un caso de estudio de un proyecto terminado: el problema, tu decisión clave y el resultado, con 3 fotos. Es tu mejor herramienta de venta.",
    "Escribile a 3 ex clientes y pedíles una recomendación corta o que te presenten a alguien. Los referidos son el canal más barato.",
    "Definí tu nicho: reformas de PH, casas de fin de semana, locales comerciales. Quien hace todo no es recordado por nada.",
    "Cobrá por etapas (anteproyecto, proyecto ejecutivo, dirección de obra). Ordena tu flujo de caja y evita regalar trabajo.",
    "Todo proyecto con contrato escrito: alcance, etapas, cantidad de revisiones, plazos y forma de pago. Pedí modelos a tu colegio profesional.",
    "Subí a redes un proceso de obra: antes, durante y después, explicando qué decidiste y por qué. Eso demuestra criterio, no solo fotos lindas.",
    "Tomate un café esta semana con un ingeniero, paisajista, inmobiliaria o desarrollador. Las alianzas traen proyectos.",
    "Invertí en buenas fotos de tu mejor obra. Un solo set profesional te rinde años en portfolio, web y redes.",
    "Anotá las horas reales de tu último proyecto y compará con lo que cobraste. Así sabés tu rentabilidad real.",
    "Completá tu perfil de Google Business con fotos, zonas y servicios: mucha gente busca 'arquitecto en [zona]'.",
    "Anotate a un concurso de ideas, aunque sea chico. Suma portfolio, visibilidad y práctica de síntesis.",
    "Armá un PDF de una página con tus servicios, etapas, plazos orientativos y cómo es trabajar con vos.",
    "Diferenciá tu presentación: un recorrido 360 o un render rápido de la propuesta cambia cómo te ve el cliente.",
    "Escribí una nota mensual sobre un problema típico de tus clientes (por ejemplo: cómo encarar la reforma de un PH). Posiciona y trae consultas.",
    "Revisá registros de proveedores y licitaciones de tu municipio o provincia. La obra pública es un mercado poco explorado por estudios chicos.",
    "Llevá una planilla de contactos con fecha de próximo seguimiento. Muchos proyectos se cierran después del primer contacto, no en él.",
    "Pedí siempre un anticipo antes de empezar cada etapa. Es una señal de seriedad para ambas partes.",
    "Hacé un curso corto de la herramienta que más usás o de gestión de proyectos. Mejorar un 10% tu eficiencia es ganar tiempo.",
    "Bloqueá 2 mañanas por semana sin mails ni mensajes para trabajo profundo de diseño. Protegé ese tiempo como si fuera un cliente.",
    "Revisá tu web o portfolio con ojos de cliente: ¿en 10 segundos se entiende qué hacés, para quién y cómo contactarte?",
]
RETOS = [
    "Contactá a 5 personas que podrían recomendarte o contratarte.",
    "Publicá un caso de estudio completo de un proyecto.",
    "Actualizá tu portfolio con un proyecto nuevo o mejorá uno existente.",
    "Buscá un concurso y leé sus bases; decidí si participás.",
    "Tomá 2 cafés con colegas, proveedores o desarrolladores.",
    "Revisá tus honorarios y tu plantilla de contrato.",
    "Pedile una reseña o testimonio a un cliente satisfecho.",
    "Ordená archivos, plantillas y presupuestos para ahorrar tiempo.",
]

def local(t): return t.split("}")[-1]

def parse_date(s):
    if not s: return None
    s = s.strip()
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try: d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception: return None
    if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
    return d

def parse(content, src, is_gn):
    root = ET.fromstring(content)
    out = []
    for it in root.iter():
        if local(it.tag) not in ("item", "entry"): continue
        d = {"src": src, "title": "", "link": "", "img": None, "date": None, "desc": ""}
        body = ""
        for ch in it:
            t = local(ch.tag)
            ns = ch.tag.split("}")[0] if "}" in ch.tag else ""
            if "yahoo" in ns or "mrss" in ns:
                if t in ("content", "thumbnail") and ch.get("url") and not d["img"]:
                    d["img"] = ch.get("url")
                continue
            if t == "title": d["title"] = html.unescape((ch.text or "").strip())
            elif t == "link":
                if not d["link"]: d["link"] = ch.get("href") or (ch.text or "").strip()
            elif t in ("pubDate", "published", "updated", "date"):
                if not d["date"]: d["date"] = parse_date(ch.text)
            elif t == "enclosure":
                if (ch.get("type") or "").startswith("image") and not d["img"]: d["img"] = ch.get("url")
            elif t in ("encoded", "content", "description", "summary"):
                body += ch.text or ""
        if not is_gn:
            if not d["img"]:
                m = re.search(r'<img[^>]+src=["\']([^"\']+)', body)
                if m and not m.group(1).startswith("data:"): d["img"] = m.group(1)
            txt = html.unescape(re.sub(r"<[^>]+>", " ", body))
            d["desc"] = re.sub(r"\s+", " ", txt).strip()[:170]
        else:
            if " - " in d["title"]:
                d["title"], d["src"] = d["title"].rsplit(" - ", 1)
        if d["title"] and d["link"]: out.append(d)
    return out

def fetch(item):
    src, url = item
    try:
        r = requests.get(url, headers=UA, timeout=25)
        if r.status_code == 429:
            time.sleep(8)
            r = requests.get(url, headers=UA, timeout=25)
        r.raise_for_status()
        if "news.google.com" in url:
            time.sleep(3)
        res = parse(r.content, src, "news.google.com" in url)
        print("OK", src, len(res))
        return res
    except Exception as e:
        print("ERROR feed:", src, url, e)
        return []

def collect(feeds, days, each=14):
    res = [fetch(f) for f in feeds]
    cutoff = NOW - timedelta(days=days)
    items, seen = [], set()
    for lst in res:
        for it in lst[:each]:
            k = re.sub(r"\W+", "", it["title"].lower())[:60]
            if not k or k in seen: continue
            if it["date"] and it["date"] < cutoff: continue
            seen.add(k)
            items.append(it)
    items.sort(key=lambda x: x["date"] or datetime(1970, 1, 1, tzinfo=timezone.utc), reverse=True)
    return items

def ago(dt):
    if not dt: return ""
    s = (NOW - dt).total_seconds()
    if s < 3600: return "hace %d min" % max(int(s // 60), 1)
    if s < 86400: return "hace %d h" % int(s // 3600)
    return "hace %d d" % int(s // 86400)

def esc(x): return html.escape(x or "", True)

def img(u):
    return ('<div class="im"><img src="%s" alt="" loading="lazy" referrerpolicy="no-referrer" '
            'onerror="this.parentNode.classList.add(\'noimg\');this.remove()"></div>') % esc(u)

def card(it):
    return ('<a class="card" href="%s" target="_blank" rel="noopener noreferrer">%s'
            '<div class="meta"><span class="tag">%s</span><span>%s</span></div><h3>%s</h3></a>') % (
        esc(it["link"]), img(it["img"]) if it["img"] else "", esc(it["src"]), ago(it["date"]), esc(it["title"]))

def hero(it):
    return ('<a class="hero" href="%s" target="_blank" rel="noopener noreferrer">%s'
            '<div class="ov"><span class="tag">%s</span><h2>%s</h2><p>%s</p></div></a>') % (
        esc(it["link"]), img(it["img"]), esc(it["src"]), esc(it["title"]), esc(it["desc"]))

def side(it):
    return ('<a class="side" href="%s" target="_blank" rel="noopener noreferrer">%s'
            '<div class="meta"><span class="tag">%s</span><span>%s</span></div><h3>%s</h3></a>') % (
        esc(it["link"]), img(it["img"]), esc(it["src"]), ago(it["date"]), esc(it["title"]))

def lista(items, n=8):
    if not items: return '<p class="vacio">Sin novedades por ahora.</p>'
    rows = ""
    for it in items[:n]:
        rows += ('<a class="row" href="%s" target="_blank" rel="noopener noreferrer">'
                 '<span class="rt">%s</span><span class="rm">%s · %s</span></a>') % (
            esc(it["link"]), esc(it["title"]), esc(it["src"]), ago(it["date"]))
    return rows

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

CSS = """:root{--bg:#fff;--fg:#111;--mut:#6b6b6b;--line:#111;--soft:#eee;--acc:#ff4b1f;--card:#f6f6f4}
@media (prefers-color-scheme:dark){:root{--bg:#0e0e0e;--fg:#f2f2f0;--mut:#9a9a96;--line:#f2f2f0;--soft:#2a2a2a;--card:#181818}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.45 "Archivo","Helvetica Neue",Arial,sans-serif}
a{color:inherit;text-decoration:none}
.wrap{max-width:1240px;margin:0 auto;padding:0 24px 80px}
.mast{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:4px solid var(--line);padding:28px 0 12px}
.logo{font-size:clamp(44px,9vw,92px);font-weight:900;letter-spacing:-.05em;line-height:.9}
.logo span{color:var(--acc)}
.fecha{font-size:13px;color:var(--mut);text-align:right;text-transform:capitalize}
.nav{display:flex;gap:22px;padding:12px 0;border-bottom:1px solid var(--soft);font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;overflow-x:auto;white-space:nowrap}
.nav a:hover{color:var(--acc)}
h4.sec{font-size:13px;text-transform:uppercase;letter-spacing:.14em;margin:56px 0 18px;padding-top:10px;border-top:2px solid var(--line);display:flex;justify-content:space-between}
h4.sec small{color:var(--mut);font-weight:400;letter-spacing:.04em;text-transform:none}
.top{display:grid;grid-template-columns:2fr 1fr;gap:24px;margin-top:28px}
.hero{position:relative;display:block;min-height:480px;background:#222;overflow:hidden}
.hero .im{position:absolute;inset:0}
.hero .im img{width:100%;height:100%;object-fit:cover;transition:transform .6s}
.hero:hover .im img{transform:scale(1.03)}
.hero .ov{position:absolute;left:0;right:0;bottom:0;padding:90px 28px 28px;color:#fff;background:linear-gradient(transparent,rgba(0,0,0,.82))}
.hero h2{font-size:clamp(26px,3.6vw,44px);line-height:1.05;letter-spacing:-.03em;margin:8px 0 8px;font-weight:800}
.hero p{margin:0;font-size:15px;opacity:.85;max-width:620px}
.sides{display:grid;gap:24px;align-content:start}
.im{aspect-ratio:4/3;overflow:hidden;background:var(--soft);margin-bottom:10px}
.im img{width:100%;height:100%;object-fit:cover;display:block;transition:transform .5s}
.card:hover .im img,.side:hover .im img{transform:scale(1.04)}
.im.noimg{display:none}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:34px 24px}
.card h3,.side h3{font-size:19px;line-height:1.15;letter-spacing:-.015em;margin:4px 0 0;font-weight:800}
.card:hover h3,.side:hover h3,.row:hover .rt{color:var(--acc)}
.meta{display:flex;gap:10px;font-size:12px;color:var(--mut);align-items:center}
.tag{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.1em;color:var(--acc)}
.hero .tag{background:var(--acc);color:#fff;padding:3px 8px}
.cols{display:grid;grid-template-columns:repeat(2,1fr);gap:40px}
.row{display:block;padding:14px 0;border-bottom:1px solid var(--soft)}
.rt{display:block;font-weight:700;font-size:17px;line-height:1.25}
.rm{font-size:12px;color:var(--mut)}
.vacio{color:var(--mut)}
.crecer{background:var(--card);padding:32px;margin-top:56px}
.crecer h4.sec{margin-top:0;border-color:var(--acc)}
.dos{display:grid;grid-template-columns:2fr 1fr;gap:24px;margin-bottom:34px}
.idea{background:var(--fg);color:var(--bg);padding:28px}
.idea .k{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--acc);font-weight:800}
.idea p{font-size:clamp(20px,2.4vw,28px);line-height:1.2;letter-spacing:-.02em;font-weight:700;margin:10px 0 0}
.reto{border:2px solid var(--acc);padding:28px}
.reto p{font-size:19px;font-weight:700;line-height:1.25;margin:10px 0 0}
.recs{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}
.rec{display:block;border:1px solid var(--soft);padding:16px;background:var(--bg)}
.rec:hover{border-color:var(--acc)}
.rec b{display:block;font-size:16px}
.rec span{font-size:13px;color:var(--mut)}
.pie{margin-top:48px;font-size:12px;color:var(--mut);border-top:1px solid var(--soft);padding-top:14px}
@media(max-width:900px){.top,.dos,.cols{grid-template-columns:1fr}.grid{grid-template-columns:repeat(2,1fr)}.hero{min-height:360px}}
@media(max-width:560px){.grid{grid-template-columns:1fr}.mast{flex-direction:column;align-items:flex-start;gap:8px}.fecha{text-align:left}}"""

def main():
    hoy = datetime.now(ARG)
    fecha = "%s %d de %s de %d · %s hs" % (DIAS[hoy.weekday()], hoy.day, MESES[hoy.month - 1], hoy.year, hoy.strftime("%H:%M"))

    intl = collect(FEEDS_INT, 10)
    es = collect(FEEDS_ES, 10)
    conc = collect(FEEDS_CONC, 30)
    merc = collect(FEEDS_MERC, 7)

    con_img = [i for i in intl if i["img"]]
    top_html = ""
    usados = set()
    if con_img:
        h = con_img[0]
        sd = con_img[1:3]
        usados = {h["link"]} | {s["link"] for s in sd}
        top_html = '<div class="top">%s<div class="sides">%s</div></div>' % (hero(h), "".join(side(s) for s in sd))
    resto = [i for i in intl if i["link"] not in usados][:12]
    grid_html = '<div class="grid">%s</div>' % "".join(card(i) for i in resto) if resto else '<p class="vacio">No se pudieron cargar las noticias internacionales.</p>'

    idea = TIPS[hoy.toordinal() % len(TIPS)]
    reto = RETOS[hoy.isocalendar()[1] % len(RETOS)]
    recs = "".join('<a class="rec" href="%s" target="_blank" rel="noopener noreferrer"><b>%s</b><span>%s</span></a>' % (esc(u), esc(n), esc(d)) for n, u, d in RECURSOS)

    page = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Arquitectura hoy</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;700;800;900&display=swap" rel="stylesheet">
<style>%s</style></head>
<body><div class="wrap">
<div class="mast"><div class="logo">ARQ<span>.</span>hoy</div><div class="fecha">%s</div></div>
<div class="nav"><a href="#mundo">Mundo</a><a href="#local">Argentina</a><a href="#crecer">Crecer como independiente</a><a href="#concursos">Concursos</a><a href="#mercado">Mercado</a></div>
%s
<h4 class="sec" id="mundo">Lo último en arquitectura <small>Dezeen, ArchDaily, Designboom</small></h4>
%s
<h4 class="sec" id="local">Desde Argentina y Latinoamérica</h4>
<div>%s</div>
<div class="crecer" id="crecer">
<h4 class="sec">Para crecer como arquitecto independiente <small>una idea y un reto por día y por semana</small></h4>
<div class="dos"><div class="idea"><div class="k">Idea del día</div><p>%s</p></div><div class="reto"><div class="tag">Reto de la semana</div><p>%s</p></div></div>
<div class="cols">
<div id="concursos"><h4 class="sec">Concursos y anteproyectos <small>último mes</small></h4>%s</div>
<div id="mercado"><h4 class="sec">Mercado y construcción en Argentina <small>última semana</small></h4>%s</div>
</div>
<h4 class="sec">Dónde buscar concursos, trabajo y visibilidad</h4>
<div class="recs">%s</div>
</div>
<div class="pie">Titulares y fotos pertenecen a sus medios de origen; cada nota abre en el sitio original. Verificá siempre fechas y bases de concursos en la fuente oficial. Generado automáticamente.</div>
</div></body></html>""" % (CSS, esc(fecha), top_html, grid_html, '<div class="cols">%s</div>' % "".join(
        '<div>%s</div>' % lista(es[k::2], 6) for k in (0, 1)), esc(idea), esc(reto), lista(conc, 8), lista(merc, 8), recs)

    os.makedirs("arq", exist_ok=True)
    with open(os.path.join("arq", "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    print("OK arq/index.html generado", fecha)

main()
