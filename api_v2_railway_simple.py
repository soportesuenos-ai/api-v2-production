"""
API v2: Market Discovery + SerpAPI + Google Trends bilingue + Meta Ads
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import os
from typing import List, Optional
import httpx

app = FastAPI(
    title="Market Discovery API v2",
    description="Busqueda de productos + Google Trends bilingue + Meta Ads",
    version="2.6"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== MODELOS =====

class Producto(BaseModel):
    nombre: str
    precio: str
    fuente: str
    url: str
    thumbnail: Optional[str] = ""
    trends_score: float = 0
    interes_trends: float = 0
    es_viral: bool = False

class SearchResult(BaseModel):
    query: str
    productos: List[Producto]
    google_trends_interest: float
    timestamp: str

# ===== TRADUCCION =====

def traducir_al_ingles(texto: str) -> str:
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source="es", target="en").translate(texto)
    except Exception:
        return texto

# ===== GOOGLE TRENDS BILINGUE =====

def obtener_trends_para_query(query: str, geo: str = "CL") -> dict:
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="es-CL", tz=-240, timeout=(10, 25))
        pytrends.build_payload([query], cat=0, timeframe="today 1-m", geo=geo)
        df = pytrends.interest_over_time()
        if df.empty or query not in df.columns:
            return None
        valores = df[query].tolist()
        interes = int(valores[-1]) if valores else 0
        crecimiento = int(valores[-1]) - int(valores[0]) if len(valores) > 1 else 0
        return {"interes": interes, "crecimiento": crecimiento}
    except Exception:
        return None


def obtener_google_trends_real(query: str, geo: str = "CL") -> dict:
    query_en = traducir_al_ingles(query)
    use_english = query_en.lower() != query.lower()

    resultado_es = obtener_trends_para_query(query, geo)
    resultado_en = obtener_trends_para_query(query_en, geo) if use_english else None

    if resultado_es and resultado_en:
        datos = resultado_en if resultado_en["interes"] > resultado_es["interes"] else resultado_es
        idioma_usado = "en" if resultado_en["interes"] > resultado_es["interes"] else "es"
    elif resultado_es:
        datos = resultado_es
        idioma_usado = "es"
    elif resultado_en:
        datos = resultado_en
        idioma_usado = "en"
    else:
        return _trends_fallback(query)

    interes = datos["interes"]
    crecimiento = datos["crecimiento"]
    tendencia = "subiendo" if crecimiento > 5 else "bajando" if crecimiento < -5 else "estable"
    es_viral = interes >= 70 and crecimiento >= 20

    return {
        "interes": interes,
        "paises": ["CL"],
        "crecimiento": crecimiento,
        "es_viral": es_viral,
        "tendencia": tendencia,
        "fuente": "google_trends_real",
        "idioma_usado": idioma_usado,
        "query_en": query_en if use_english else None
    }


def _trends_fallback(query: str) -> dict:
    trends_db = {
        "curvy gummies":         {"interes": 78, "paises": ["CL","AR","PE","CO"], "crecimiento": 45, "es_viral": True,  "tendencia": "subiendo"},
        "filtro pelos":          {"interes": 65, "paises": ["CL","AR","MX"],      "crecimiento": 22, "es_viral": False, "tendencia": "estable"},
        "termo mate":            {"interes": 72, "paises": ["CL","AR","UY"],      "crecimiento": 38, "es_viral": True,  "tendencia": "subiendo"},
        "crema limpiadora":      {"interes": 58, "paises": ["CL","PE","CO"],      "crecimiento": 15, "es_viral": False, "tendencia": "estable"},
        "organizador magnetico": {"interes": 55, "paises": ["CL","AR"],           "crecimiento": 28, "es_viral": False, "tendencia": "subiendo"},
        "colchon":               {"interes": 60, "paises": ["CL","AR"],           "crecimiento": 10, "es_viral": False, "tendencia": "estable"},
    }
    query_lower = query.lower()
    for key, data in trends_db.items():
        if key in query_lower or query_lower in key:
            data["fuente"] = "simulado"
            data["idioma_usado"] = "es"
            return data
    return {"interes": 30, "paises": ["CL"], "crecimiento": 5, "es_viral": False, "tendencia": "estable", "fuente": "simulado", "idioma_usado": "es"}


# ===== SERPAPI SHOPPING =====

async def buscar_serpapi(query: str, gl: str = "cl", hl: str = "es") -> List[dict]:
    api_key = os.environ.get("SERPAPI_KEY", "")
    if not api_key:
        return []

    params = {
        "engine": "google_shopping",
        "q": query,
        "gl": gl,
        "hl": hl,
        "api_key": api_key
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://serpapi.com/search", params=params, timeout=15)
            data = response.json()
        productos = []
        for item in data.get("shopping_results", [])[:8]:
            productos.append({
                "nombre":    item.get("title", "Sin nombre"),
                "precio":    item.get("price", "N/A"),
                "fuente":    item.get("source", ""),
                "url":       item.get("product_link") or item.get("link", ""),
                "thumbnail": item.get("thumbnail", ""),
            })
        return productos
    except Exception:
        return []

# ===== SCORE =====

def calcular_score(trends_data: dict) -> float:
    interes = trends_data.get("interes", 0)
    crecimiento = min(max(trends_data.get("crecimiento", 0), 0), 100)
    viral_bonus = 20 if trends_data.get("es_viral") else 0
    return min((interes * 0.5) + (crecimiento * 0.3) + viral_bonus, 100)

# ===== META ADS URL =====

def meta_ads_url(query: str) -> str:
    from urllib.parse import quote
    q = quote(query)
    return f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=CL&q={q}&search_type=keyword_unordered&media_type=all"

# ===== ENDPOINTS =====

@app.get("/")
async def root():
    return {
        "nombre": "Market Discovery API v2",
        "version": "2.6",
        "status": "Online",
        "endpoints": [
            "GET /api/v2/search?query=X",
            "GET /api/v2/trends?product=X",
            "GET /api/v2/star-products?keyword=X",
            "GET /api/v2/meta-ads?query=X",
            "GET /health"
        ]
    }

@app.get("/health")
async def health():
    serpapi_key = os.environ.get("SERPAPI_KEY", "")
    return {
        "status": "OK",
        "timestamp": datetime.now().isoformat(),
        "version": "2.6",
        "serpapi_conectada": bool(serpapi_key)
    }

@app.get("/api/v2/search", response_model=SearchResult)
async def buscar_producto(query: str, gl: str = "cl", hl: str = "es"):
    if not query or len(query) < 2:
        raise HTTPException(status_code=400, detail="Query minimo 2 caracteres")

    productos_raw = await buscar_serpapi(query, gl, hl)
    trends = obtener_google_trends_real(query)
    score = calcular_score(trends)

    productos = []
    for p in productos_raw:
        productos.append(Producto(
            nombre=p["nombre"],
            precio=p["precio"],
            fuente=p["fuente"],
            url=p["url"],
            thumbnail=p["thumbnail"],
            trends_score=score,
            interes_trends=trends.get("interes", 0),
            es_viral=trends.get("es_viral", False)
        ))

    return SearchResult(
        query=query,
        productos=productos,
        google_trends_interest=trends.get("interes", 0),
        timestamp=datetime.now().isoformat()
    )

@app.get("/api/v2/trends")
async def obtener_trends(product: str, geo: str = "CL"):
    if not product or len(product) < 2:
        raise HTTPException(status_code=400, detail="Product minimo 2 caracteres")

    trends = obtener_google_trends_real(product, geo)

    return {
        "producto": product,
        "interes_global": trends.get("interes", 0),
        "interes_chile": trends.get("interes", 0),
        "paises_top": trends.get("paises", []),
        "crecimiento_30d": trends.get("crecimiento", 0),
        "es_viral": trends.get("es_viral", False),
        "tendencia": trends.get("tendencia", "estable"),
        "fuente": trends.get("fuente", "simulado"),
        "idioma_usado": trends.get("idioma_usado", "es"),
        "query_en": trends.get("query_en"),
        "meta_ads_url": meta_ads_url(product),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/v2/star-products")
async def obtener_star_products(keyword: str):
    resultado = await buscar_producto(keyword)
    estrellas = [p for p in resultado.productos if p.trends_score >= 60]
    return {
        "keyword": keyword,
        "total_encontrados": len(resultado.productos),
        "estrellas": len(estrellas),
        "productos": estrellas,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/v2/meta-ads")
async def buscar_meta_ads(query: str):
    return {
        "query": query,
        "mensaje": "Abre el link para ver anuncios activos en Chile",
        "url_meta_ads": meta_ads_url(query),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/v2/trending-chile")
async def trending_chile():
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="es-CL", tz=-240, timeout=(10, 25))
        df = pytrends.trending_searches(pn="chile")
        terminos = df[0].tolist()[:20]
        resultado = []
        for t in terminos:
            resultado.append({"producto": t, "meta_ads_url": meta_ads_url(t)})
        return {"fuente": "google_trends_real", "pais": "Chile", "total": len(resultado), "trending": resultado, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        return {"fuente": "error", "error": str(e), "trending": [], "timestamp": datetime.now().isoformat()}

@app.get("/api/v2/tiktok-trending")
async def tiktok_trending(country: str = "US", keyword: str = ""):
    """Obtiene top ads de TikTok Creative Center via Apify"""
    apify_token = os.environ.get("APIFY_TOKEN", "")
    if not apify_token:
        raise HTTPException(status_code=500, detail="APIFY_TOKEN no configurado")

    try:
        import asyncio
        actor_id = "codebyte~tiktok-creative-center-top-ads"
        run_input = {
            "country_code": country,
            "period": "7",
            "limit": 20,
            "order_by": "like"
        }
        if keyword:
            run_input["keyword"] = keyword

        async with httpx.AsyncClient(timeout=60) as client:
            run_resp = await client.post(
                f"https://api.apify.com/v2/acts/{actor_id}/runs",
                params={"token": apify_token},
                json=run_input
            )
            run_data = run_resp.json()
            run_id = run_data.get("data", {}).get("id")

            if not run_id:
                raise Exception(f"Run no iniciado: {run_data}")

            for _ in range(15):
                await asyncio.sleep(4)
                status_resp = await client.get(
                    f"https://api.apify.com/v2/actor-runs/{run_id}",
                    params={"token": apify_token}
                )
                status = status_resp.json().get("data", {}).get("status", "")
                if status == "SUCCEEDED":
                    break
                elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
                    raise Exception(f"Run {status}")

            results_resp = await client.get(
                f"https://api.apify.com/v2/actor-runs/{run_id}/dataset/items",
                params={"token": apify_token, "limit": 20}
            )
            items = results_resp.json()

        anuncios = []
        for item in items:
            video_info = item.get("video_info", {})
            anuncios.append({
                "titulo": item.get("ad_title", ""),
                "marca": item.get("brand_name", ""),
                "likes": item.get("like", 0),
                "ctr": item.get("ctr", 0),
                "thumbnail": video_info.get("cover", ""),
                "duracion": video_info.get("duration", 0),
                "landing_page": item.get("landing_page", ""),
                "paises": item.get("country_code", []),
                "objetivo": item.get("objective_key", ""),
                "keywords": item.get("keyword_list", [])
            })

        return {
            "country": country,
            "keyword": keyword,
            "total": len(anuncios),
            "anuncios": anuncios,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        return {
            "country": country,
            "total": 0,
            "anuncios": [],
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
