"""
API v2: Market Discovery + SerpAPI Google Shopping + Meta Ads Library
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
    description="Busqueda de productos + Google Trends + Meta Ads",
    version="2.2"
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
    paises_top: List[str]
    crecimiento_30d: float
    es_viral: bool

# ===== GOOGLE TRENDS SIMULADO =====

def obtener_google_trends_simulado(query: str) -> dict:
    trends_db = {
        "curvy gummies":         {"interes": 78, "paises": ["CL","AR","PE","CO"], "crecimiento": 45, "es_viral": True},
        "filtro pelos":          {"interes": 65, "paises": ["CL","AR","MX"],      "crecimiento": 22, "es_viral": False},
        "termo mate":            {"interes": 72, "paises": ["CL","AR","UY"],      "crecimiento": 38, "es_viral": True},
        "crema limpiadora":      {"interes": 58, "paises": ["CL","PE","CO"],      "crecimiento": 15, "es_viral": False},
        "organizador magnetico": {"interes": 55, "paises": ["CL","AR"],           "crecimiento": 28, "es_viral": False},
        "colchon":               {"interes": 60, "paises": ["CL","AR"],           "crecimiento": 10, "es_viral": False},
    }
    query_lower = query.lower()
    for key, data in trends_db.items():
        if key in query_lower or query_lower in key:
            return data
    return {"interes": 30, "paises": ["CL"], "crecimiento": 5, "es_viral": False}

# ===== SERPAPI =====

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
    crecimiento = min(trends_data.get("crecimiento", 0), 100)
    viral_bonus = 20 if trends_data.get("es_viral") else 0
    return min((interes * 0.5) + (crecimiento * 0.3) + viral_bonus, 100)

# ===== ENDPOINTS =====

@app.get("/")
async def root():
    return {
        "nombre": "Market Discovery API v2",
        "version": "2.2",
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
    meta_token = os.environ.get("META_ADS_TOKEN", "")
    return {
        "status": "OK",
        "timestamp": datetime.now().isoformat(),
        "version": "2.2",
        "serpapi_conectada": bool(serpapi_key),
        "meta_ads_conectada": bool(meta_token)
    }

@app.get("/api/v2/search", response_model=SearchResult)
async def buscar_producto(query: str):
    if not query or len(query) < 2:
        raise HTTPException(status_code=400, detail="Query minimo 2 caracteres")

    productos_raw = await buscar_serpapi(query)
    trends = obtener_google_trends_simulado(query)
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

@app.get("/api/v2/trends", response_model=TrendsData)
async def obtener_trends(product: str):
    if not product or len(product) < 2:
        raise HTTPException(status_code=400, detail="Product minimo 2 caracteres")
    trends = obtener_google_trends_simulado(product)
    return TrendsData(
        producto=product,
        interes_global=trends.get("interes", 0),
        paises_top=trends.get("paises", []),
        crecimiento_30d=trends.get("crecimiento", 0),
        es_viral=trends.get("es_viral", False)
    )

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
    """Busca anuncios activos en Meta Ads Library para un producto en Chile"""
    token = os.environ.get("META_ADS_TOKEN", "")
    if not token:
        raise HTTPException(status_code=500, detail="META_ADS_TOKEN no configurado")

    url = "https://graph.facebook.com/v19.0/ads_archive"
    params = {
        "search_terms": query,
        "ad_reached_countries": '["CL"]',
        "ad_active_status": "ACTIVE",
        "fields": "id,ad_creative_body,ad_creative_link_title,page_name,ad_delivery_start_time,publisher_platforms,impressions,spend",
        "limit": 50,
        "access_token": token
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=15)
            data = response.json()

        if "error" in data:
            raise HTTPException(status_code=400, detail=data["error"].get("message", "Error Meta API"))

        anuncios_raw = data.get("data", [])

        anunciantes = {}
        for ad in anuncios_raw:
            page = ad.get("page_name", "Desconocido")
            if page not in anunciantes:
                anunciantes[page] = {
                    "anunciante": page,
                    "total_anuncios": 0,
                    "plataformas": set(),
                    "primer_anuncio": ad.get("ad_delivery_start_time", ""),
                    "anuncios": []
                }
            anunciantes[page]["total_anuncios"] += 1
            for p in ad.get("publisher_platforms", []):
                anunciantes[page]["plataformas"].add(p)
            anunciantes[page]["anuncios"].append({
                "texto": ad.get("ad_creative_body", ""),
                "titulo": ad.get("ad_creative_link_title", ""),
                "inicio": ad.get("ad_delivery_start_time", ""),
                "plataformas": ad.get("publisher_platforms", []),
                "impresiones": ad.get("impressions", {}),
                "gasto": ad.get("spend", {})
            })

        ranking = []
        for page, info in anunciantes.items():
            info["plataformas"] = list(info["plataformas"])
            score = (info["total_anuncios"] * 2) + (len(info["plataformas"]) * 5)
            info["score"] = score
            ranking.append(info)

        top10 = sorted(ranking, key=lambda x: x["score"], reverse=True)[:10]

        return {
            "query": query,
            "total_anunciantes": len(ranking),
            "top10": top10,
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
