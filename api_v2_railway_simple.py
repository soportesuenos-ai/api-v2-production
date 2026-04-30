"""
API v2: Market Discovery + SerpAPI Google Shopping + Google Trends Real
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
    description="Busqueda de productos + Google Trends Real + Meta Ads link",
    version="2.4"
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

class TrendsData(BaseModel):
    producto: str
    interes_global: float
    interes_chile: float
    paises_top: List[str]
    crecimiento_30d: float
    es_viral: bool
    tendencia: str

# ===== GOOGLE TRENDS REAL =====

def obtener_google_trends_real(query: str) -> dict:
    """Obtiene datos reales de Google Trends para Chile"""
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="es-CL", tz=-240, timeout=(10, 25))
        pytrends.build_payload([query], cat=0, timeframe="today 1-m", geo="CL")

        interest_over_time = pytrends.interest_over_time()

        if interest_over_time.empty or query not in interest_over_time.columns:
            return _trends_fallback(query)

        valores = interest_over_time[query].tolist()
        interes_actual = int(valores[-1]) if valores else 0
        interes_inicio = int(valores[0]) if valores else 0
        crecimiento = interes_actual - interes_inicio

        tendencia = "subiendo" if crecimiento > 5 else "bajando" if crecimiento < -5 else "estable"
        es_viral = interes_actual >= 70 and crecimiento >= 20

        return {
            "interes": interes_actual,
            "paises": ["CL"],
            "crecimiento": crecimiento,
            "es_viral": es_viral,
            "tendencia": tendencia,
            "fuente": "google_trends_real"
        }

    except Exception:
        return _trends_fallback(query)


def _trends_fallback(query: str) -> dict:
    """Fallback simulado si Google Trends falla"""
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
            return data
    return {"interes": 30, "paises": ["CL"], "crecimiento": 5, "es_viral": False, "tendencia": "estable", "fuente": "simulado"}


# ===== SERPAPI SHOPPING =====

async def buscar_serpapi(query: str) -> List[dict]:
    api_key = os.environ.get("SERPAPI_KEY", "")
    if not api_key:
        return []

    params = {
        "engine": "google_shopping",
        "q": query,
        "gl": "cl",
        "hl": "es",
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


# ===== ENDPOINTS =====

@app.get("/")
async def root():
    return {
        "nombre": "Market Discovery API v2",
        "version": "2.4",
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
        "version": "2.4",
        "serpapi_conectada": bool(serpapi_key)
    }

@app.get("/api/v2/search", response_model=SearchResult)
async def buscar_producto(query: str):
    if not query or len(query) < 2:
        raise HTTPException(status_code=400, detail="Query minimo 2 caracteres")

    productos_raw = await buscar_serpapi(query)
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
async def obtener_trends(product: str):
    if not product or len(product) < 2:
        raise HTTPException(status_code=400, detail="Product minimo 2 caracteres")

    trends = obtener_google_trends_real(product)

    return {
        "producto": product,
        "interes_global": trends.get("interes", 0),
        "interes_chile": trends.get("interes", 0),
        "paises_top": trends.get("paises", []),
        "crecimiento_30d": trends.get("crecimiento", 0),
        "es_viral": trends.get("es_viral", False),
        "tendencia": trends.get("tendencia", "estable"),
        "fuente": trends.get("fuente", "simulado"),
        "meta_ads_url": f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=CL&q={product}",
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
    """Retorna link directo a Meta Ads Library filtrado por Chile"""
    url = f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=CL&q={query}"
    return {
        "query": query,
        "mensaje": "Abre el link para ver anuncios activos en Chile",
        "url_meta_ads": url,
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
