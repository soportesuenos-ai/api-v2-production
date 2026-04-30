"""
API v2 SIMPLIFICADA: Market Discovery + Google Trends simulado
Compatible con Railway - Sin dependencias problemáticas
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import os
from typing import List, Optional

app = FastAPI(
    title="Market Discovery API v2",
    description="Búsqueda de productos + Google Trends simulado",
    version="2.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== MODELOS =====

class ProductoBase(BaseModel):
    nombre: str
    precio_usd: float
    competencia: int
    margen: float
    reviews: int
    vendidos: int
    trends_score: float = 0
    google_trends_data: Optional[dict] = None

class SearchResult(BaseModel):
    query: str
    productos: List[ProductoBase]
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
    """Obtiene datos de Google Trends SIMULADOS para un producto"""
    
    # Base de datos simulada de trends
    trends_db = {
        "curvy gummies": {
            "interes": 78,
            "paises": ["CL", "AR", "PE", "CO"],
            "crecimiento": 45,
            "es_viral": True
        },
        "filtro pelos": {
            "interes": 65,
            "paises": ["CL", "AR", "MX"],
            "crecimiento": 22,
            "es_viral": False
        },
        "termo mate": {
            "interes": 72,
            "paises": ["CL", "AR", "UY"],
            "crecimiento": 38,
            "es_viral": True
        },
        "crema limpiadora": {
            "interes": 58,
            "paises": ["CL", "PE", "CO"],
            "crecimiento": 15,
            "es_viral": False
        },
        "organizador magnético": {
            "interes": 55,
            "paises": ["CL", "AR"],
            "crecimiento": 28,
            "es_viral": False
        }
    }
    
    query_lower = query.lower()
    
    # Buscar en base de datos
    for key, data in trends_db.items():
        if key in query_lower or query_lower in key:
            return data
    
    # Si no encuentra, retornar datos genéricos
    return {
        "interes": 30,
        "paises": ["CL"],
        "crecimiento": 5,
        "es_viral": False
    }

# ===== SCRAPING ALIEXPRESS (SIMULADO) =====

async def buscar_aliexpress(query: str) -> List[dict]:
    """Busca productos en AliExpress (SIMULADO)"""
    
    productos_simulados = {
        "curvy gummies": [
            {
                "nombre": "Curvy Gummies Premium - 100 piezas",
                "precio_usd": 2.15,
                "competencia": 45,
                "margen": 78,
                "reviews": 3240,
                "vendidos": 12500,
                "url": "https://www.aliexpress.com/item/1234567890.html"
            },
            {
                "nombre": "Curvy Gummies Deluxe - Pack 200",
                "precio_usd": 3.50,
                "competencia": 38,
                "margen": 72,
                "reviews": 2890,
                "vendidos": 8900,
                "url": "https://www.aliexpress.com/item/1234567891.html"
            }
        ],
        "filtro pelos": [
            {
                "nombre": "Filtro Pelos Pack 10",
                "precio_usd": 3.50,
                "competencia": 23,
                "margen": 73,
                "reviews": 4500,
                "vendidos": 45000,
                "url": "https://www.aliexpress.com/item/5000990.html"
            }
        ],
        "termo mate": [
            {
                "nombre": "Termo Mate Automático Cebante",
                "precio_usd": 14.99,
                "competencia": 18,
                "margen": 68.5,
                "reviews": 2100,
                "vendidos": 28700,
                "url": "https://www.aliexpress.com/item/4000567.html"
            }
        ],
        "crema limpiadora": [
            {
                "nombre": "Crema Limpiadora Extrema 250ml",
                "precio_usd": 5.20,
                "competencia": 32,
                "margen": 75,
                "reviews": 1850,
                "vendidos": 16200,
                "url": "https://www.aliexpress.com/item/3001234.html"
            }
        ],
        "organizador magnético": [
            {
                "nombre": "Organizador Magnético Escritorio",
                "precio_usd": 3.20,
                "competencia": 28,
                "margen": 70,
                "reviews": 920,
                "vendidos": 5600,
                "url": "https://www.aliexpress.com/item/2005678.html"
            }
        ]
    }
    
    query_lower = query.lower()
    for key in productos_simulados:
        if key in query_lower or query_lower in key:
            return productos_simulados[key]
    
    return []

# ===== CALCULO STAR PRODUCT =====

def calcular_star_score(producto: dict, trends_data: dict) -> float:
    """Score 0-100 para identificar productos estrella"""
    
    vendidos_norm = min(producto["vendidos"] / 50, 100)
    competencia_norm = max((100 - producto["competencia"]) / 100 * 100, 0)
    margen_norm = min(producto["margen"], 100)
    trends_norm = trends_data.get("interes", 0)
    
    score = (
        (vendidos_norm * 0.25) +
        (competencia_norm * 0.25) +
        (margen_norm * 0.25) +
        (trends_norm * 0.25)
    )
    
    return min(score, 100)

# ===== ENDPOINTS =====

@app.get("/")
async def root():
    return {
        "nombre": "Market Discovery API v2 (Railway)",
        "version": "2.0",
        "status": "✅ Online",
        "endpoints": [
            "GET /api/v2/search?query=X",
            "GET /api/v2/trends?product=X",
            "GET /api/v2/star-products?keyword=X",
            "GET /health"
        ]
    }

@app.get("/health")
async def health():
    return {
        "status": "✅ OK",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0"
    }

@app.get("/api/v2/search", response_model=SearchResult)
async def buscar_producto(query: str):
    """
    Busca productos en AliExpress + Google Trends
    
    Ejemplo: /api/v2/search?query=curvy%20gummies
    """
    
    if not query or len(query) < 2:
        raise HTTPException(status_code=400, detail="Query mínimo 2 caracteres")
    
    # 1. Buscar en AliExpress (simulado)
    productos = await buscar_aliexpress(query)
    
    # 2. Google Trends (simulado)
    trends = obtener_google_trends_simulado(query)
    
    # 3. Enriquecer productos con Google Trends
    productos_enriquecidos = []
    for prod in productos:
        prod["trends_score"] = calcular_star_score(prod, trends)
        prod["google_trends_data"] = trends
        productos_enriquecidos.append(ProductoBase(**prod))
    
    return SearchResult(
        query=query,
        productos=productos_enriquecidos,
        google_trends_interest=trends.get("interes", 0),
        timestamp=datetime.now().isoformat()
    )

@app.get("/api/v2/trends", response_model=TrendsData)
async def obtener_trends(product: str):
    """
    Obtiene datos de Google Trends para un producto
    
    Ejemplo: /api/v2/trends?product=curvy%20gummies
    """
    
    if not product or len(product) < 2:
        raise HTTPException(status_code=400, detail="Product mínimo 2 caracteres")
    
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
    """
    Obtiene solo productos estrella (score >= 75)
    
    Ejemplo: /api/v2/star-products?keyword=filtro
    """
    
    resultado = await buscar_producto(keyword)
    
    estrellas = [p for p in resultado.productos if p.trends_score >= 75]
    
    return {
        "keyword": keyword,
        "total_encontrados": len(resultado.productos),
        "estrellas": len(estrellas),
        "productos": estrellas,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/v2/productos-virales")
async def obtener_virales():
    """Retorna productos que están viralizando en Google Trends"""
    
    productos_test = ["curvy gummies", "filtro pelos", "termo mate", "crema limpiadora", "organizador magnético"]
    
    virales = []
    
    for prod in productos_test:
        trends = obtener_google_trends_simulado(prod)
        if trends.get("es_viral"):
            virales.append({
                "producto": prod,
                "interes": trends.get("interes"),
                "crecimiento": trends.get("crecimiento"),
                "paises": trends.get("paises")
            })
    
    return {
        "virales_encontrados": len(virales),
        "productos": virales,
        "timestamp": datetime.now().isoformat()
    }

# ===== PARA PRODUCCIÓN (Gunicorn) =====

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
