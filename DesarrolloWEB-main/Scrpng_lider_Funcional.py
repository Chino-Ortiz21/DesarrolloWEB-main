import requests
from bs4 import BeautifulSoup
import re
import json

# Mapeo de categorías scrapeadas → categorías frontend
CATEGORY_MAP = {
    "Celulares en oferta": "tecnologia",
    "Ofertas dormitorio": "hogar",
    "Ofertas electrohogar": "hogar",
    "Electrodomésticos en Cyber Day": "hogar",
    "Productos de hogar": "hogar",
    "Pantalla LCD Portátil": "tecnologia",
    "Scooter Eléctrico con Pantalla": "tecnologia",
    "Audífonos": "tecnologia", 
    "lego": "juguetes"
    # Agrega más si scrapeas otras páginas
}


# Almacenar todos los productos
all_products = []

# Headers para simular un navegador
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
}

# Páginas de ofertas que queremos scrapear
offer_pages = {
    "Celulares en oferta": "https://www.lider.cl/catalogo/v/celulares-en-oferta",
    "Ofertas dormitorio": "https://www.lider.cl/catalogo/v/ofertas-dormitorio",
    "Ofertas electrohogar": "https://www.lider.cl/catalogo/v/ofertas-electrohogar",
    "Electrodomésticos en Cyber Day": "https://www.lider.cl/catalogo/v/electro-domesticos-en-cyber-day-2024",
    "Productos de hogar": "https://www.lider.cl/catalogo/v/productos-de-hogar",
    "Pantalla LCD Portátil": "https://apps.lider.cl/catalogo/v/pantalla-lcd-portatil",
    "Scooter Eléctrico con Pantalla": "https://apps.lider.cl/catalogo/v/scooter-electrico-con-pantalla",
    "Audífonos": "https://apps.lider.cl/browse/tecno/audio/audifonos/66849718_14621386_31940338",
    "lego": "https://www.lider.cl/browse/juguetes-y-entretencion/marcas-destacadas/lego/31281781_66672049_53195782"
}

def parse_offers(url):
    try:
        res = requests.get(url, headers=HEADERS)
        res.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] No se pudo acceder a {url}: {e}")
        return []

    if "enable JavaScript" in res.text:
        print("[Aviso] Esta página requiere JavaScript para cargar productos. Considera usar Selenium.")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    links = soup.select('a[href*="/ip/"]')

    productos = []

    for a in links:
        href = a.get("href")
        if not href:
            continue

        url_producto = "https://www.lider.cl" + href if href.startswith("/") else href
        texto = a.get_text(separator=" ", strip=True)

        # Buscar precios
        precios = re.findall(r"\$\d[\d\.]*", texto)
        precio_actual = precios[0] if len(precios) >= 1 else None
        precio_anterior = precios[1] if len(precios) >= 2 else None

        # Calcular descuento
        descuento = None
        if precio_actual and precio_anterior:
            valor_actual = int(precio_actual.replace("$", "").replace(".", ""))
            valor_anterior = int(precio_anterior.replace("$", "").replace(".", ""))
            if valor_anterior > valor_actual:
                descuento = round((valor_anterior - valor_actual) / valor_anterior * 100)

        # Procesar nombre
        nombre = texto
        if " - " in texto:
            nombre = texto.split(" - ", 1)[1]
            nombre = re.sub(r"\$[\d\.]+", "", nombre).strip()
            for palabra in ["Rebaja", "Ahorra"]:
                nombre = nombre.split(palabra)[0].strip()

        productos.append({
            "nombre": nombre,
            "precio_actual": precio_actual,
            "precio_anterior": precio_anterior,
            "descuento": f"{descuento}%" if descuento else "N/D",
            "link": url_producto,
            "categoria": categoria.lower().replace(" ", "-")  # opcionalmente normalizado para filtros

        })

    return productos


# Ejecutar scraping
for categoria, url in offer_pages.items():
    print(f"\n== Ofertas en: {categoria} ==")
    datos = parse_offers(url)
    if not datos:
        print("No se encontraron productos.")
        continue

    # Asignar categoría mapeada
    categoria_normalizada = CATEGORY_MAP.get(categoria, "otros")  # fallback a "otros"
    for p in datos:
        p["categoria"] = categoria_normalizada

    all_products.extend(datos)



# Guardar en archivo JSON
with open("ofertas_lider.json", "w", encoding="utf-8") as f:  
    json.dump(all_products, f, ensure_ascii=False, indent=4)

print(f"\n✅ Guardado {len(all_products)} productos en 'ofertas_lider.json'")