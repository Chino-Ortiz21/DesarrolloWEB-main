from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import json
import time
import re

# ==============================================================================
# ESTRATEGIA 1: INFERIR CATEGORÍA DEL NOMBRE/DESCRIPCIÓN DEL PRODUCTO
# Define tus categorías y las palabras clave asociadas
# Actualizado para tus categorías: Abarrotes, Bebidas, Lácteos, Carnes, Frutas/Verduras,
# Bebés, Mascotas, Hogar, Ropa, Tecnología, Juguetes, Farmacia
PRODUCT_CATEGORIES = {
    "Abarrotes": [
        "arroz", "pasta", "azúcar", "sal", "harina", "aceite", "legumbre", "salsa",
        "café", "té", "cereal", "mermelada", "atún", "conserva", "galleta", "chocolate",
        "snacks", "pan de molde", "tortilla", "tostada", "condimento", "especia",
        "vinagre", "mostaza", "mayonesa", "ketchup", "miel", "muesli", "granola",
        "barrita", "sopa", "caldo", "cubo", "fideos", "harina", "premezcla", "levadura",
        "postre instantáneo", "gelatina", "frutos secos", "semillas", "granos"
    ],
    "Bebidas": [
        "bebida", "jugo", "agua", "gaseosa", "néctar", "cerveza", "vino", "alcohol",
        "espumante", "bebida isotónica", "bebida energética", "bebida vegetal",
        "bebida cola", "limonada", "té helado", "soda", "refresco"
    ],
    "Lácteos": [
        "leche", "yogurt", "queso", "mantequilla", "crema", "postre lácteo",
        "leche descremada", "leche semidescremada", "leche entera", "leche sin lactosa",
        "leche cultivada", "leche condensada", "manjar", "margarin", "quesillo",
        "ricotta", "requesón", "probiótico", "kefir"
    ],
    "Carnes": [
        "vacuno", "pollo", "cerdo", "pescado", "marisco", "carne", "embutido",
        "chorizo", "hamburguesa", "salchicha", "vienesas", "longaniza", "pavo",
        "cordero", "filete", "posta", "asado", "costilla", "escalopa", "molida",
        "jamón", "mortadela", "paté", "prieta", "ave"
    ],
    "Frutas/Verduras": [
        "manzana", "plátano", "naranja", "palta", "tomate", "lechuga", "cebolla",
        "papa", "fruta", "verdura", "vegetal", "zanahoria", "zapallo", "pimiento",
        "limón", "kiwi", "uva", "sandía", "melón", "pera", "durazno", "cereza",
        "apio", "brócoli", "coliflor", "espinaca", "champignon", "ají", "champiñón"
    ],
    "Bebés": [
        "pañal", "toallita húmeda", "papilla", "colado", "cereal bebé", "leche infantil",
        "fórmula bebé", "mamadera", "chupete", "biberón", "crema bebé", "shampoo bebé",
        "talco bebé", "juguete bebé", "bebé", "infantil"
    ],
    "Mascotas": [
        "alimento perro", "comida gato", "juguete mascota", "arena gato",
        "snack perro", "mascotas", "comida para perro", "comida para gato",
        "antipulgas", "collar", "correa", "juguete para" # "para" puede ser muy genérico, usar con cautela
    ],
    "Hogar": [
        "limpiador", "detergente", "lavalozas", "cloro", "suavizante", "papel higiénico",
        "toalla", "basura", "desodorante ambiental", "insecticida", "lustramuebles",
        "esponja", "escobilla", "balde", "secador", "trapeador", "jabón de ropa",
        "servilleta", "film", "aluminio", "bolsa de basura", "guante", "limpiavidrios",
        "ambientador", "pilas", "ampolleta", "foco", "vela", "encendedor"
    ],
    "Ropa": [
        "calcetines", "medias", "camiseta", "polera", "pantalón", "ropa interior",
        "chaqueta", "polar", "zapatilla", "sandalia", "pijama", "traje de baño",
        "vestido", "falda", "polerón", "cortaviento"
        # Es muy probable que estos no se encuentren en Santa Isabel, pero se incluyen por tu lista.
    ],
    "Tecnología": [
        "audífono", "cargador", "cable", "pilas", "batería", "smart", "tablet",
        "celular", "impresora", "cartucho", "toner", "computador", "monitor",
        "teclado", "mouse", "parlante", "auricular"
        # Muy poco probable encontrar esto en Santa Isabel, pero se incluyen.
    ],
    "Juguetes": [
        "muñeca", "auto de juguete", "peluche", "bloques", "lego", "puzzles",
        "juego de mesa", "figura de acción", "juguete", "didáctico"
        # Podría haber algunos juguetes pequeños, especialmente en épocas festivas.
    ],
    "Farmacia": [
        "analgésico", "paracetamol", "ibuprofeno", "vitamina", "suplemento",
        "pastilla", "jarabe", "medicamento", "botiquín", "apósito", "curita",
        "algodón", "alcohol", "agua oxigenada", "antiácido", "laxante", "termómetro",
        "mascarilla", "gel sanitizante", "test covid", "preservativo", "salud", "higiene femenina",
        "protector solar", "loción"
        # Es posible que Santa Isabel venda algunos productos de parafarmacia o primeros auxilios.
    ]
}

def classify_product_category(product_name, product_description=""):
    """
    Clasifica un producto en una categoría basándose en palabras clave en su nombre o descripción.
    Prioriza las coincidencias más específicas o más largas si es necesario.
    """
    text_to_analyze = (product_name + " " + product_description).lower()
    
    # Ordenar las categorías por la longitud total de las palabras clave de forma descendente
    # para intentar capturar primero las categorías con palabras clave más específicas o más largas.
    sorted_categories = sorted(PRODUCT_CATEGORIES.items(), key=lambda item: sum(len(k) for k in item[1]), reverse=True)

    for category, keywords in sorted_categories:
        for keyword in keywords:
            # Usar \b para coincidencia de palabra completa (word boundary) para mayor precisión.
            # Por ejemplo, para evitar que "man" de "mantequilla" coincida con "manzana".
            # Es importante asegurarse de que las palabras clave en PRODUCT_CATEGORIES no incluyan
            # espacios al principio/final si se usa \b.
            if re.search(r'\b' + re.escape(keyword.lower()) + r'\b', text_to_analyze):
                return category
    
    return "Otros" # Categoría por defecto si no se encuentra ninguna coincidencia
# ==============================================================================


# Opción alternativa para ChromeDriver automático
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False
    print("Para instalación automática de ChromeDriver: pip install webdriver-manager")

def setup_driver(headless=False):
    """
    Configura el driver de Chrome con ventana a mitad de pantalla.
    """
    chrome_options = Options()
    
    if headless:
        chrome_options.add_argument("--headless")
    
    # Opciones adicionales para evitar detección
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # User agent
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    try:
        if WEBDRIVER_MANAGER_AVAILABLE:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            driver = webdriver.Chrome(options=chrome_options)
        
        # Configurar el tamaño de la ventana a la mitad de la pantalla
        if not headless:
            driver.set_window_size(960, 1080) # Aproximadamente mitad de una pantalla Full HD
            driver.set_window_position(0, 0) # Posicionar en la esquina superior izquierda
        
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver
    except Exception as e:
        print(f"Error al inicializar Chrome: {e}")
        print("\nSOLUCIONES:")
        print("1. Instalar webdriver-manager: pip install webdriver-manager")
        print("2. O descargar ChromeDriver desde: https://chromedriver.chromium.org/")
        print("3. Asegúrate de que Chrome esté instalado")
        return None

def wait_for_products_to_load(driver, timeout=30):
    """
    Espera a que los productos se carguen en la página
    """
    print("Esperando que los productos se carguen...")
    
    selectors_to_try = [
        "a.product-card",
        ".product-card",
        "[data-testid*='product']",
        ".product-item",
        ".product",
        "[class*='product-card']",
        "[class*='product']"
    ]
    
    for selector in selectors_to_try:
        try:
            print(f"Probando selector: {selector}")
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            products = driver.find_elements(By.CSS_SELECTOR, selector)
            if products:
                print(f"✓ Encontrados {len(products)} productos con selector: {selector}")
                return products, selector
        except Exception as e:
            print(f"✗ Selector {selector} no funcionó: {str(e)[:50]}...")
            continue
    
    print("⚠ No se encontraron productos con ningún selector conocido")
    return [], None

def extract_product_info(element):
    """
    Extrae información de un elemento producto
    """
    producto = {}
    
    try:
        # Nombre del producto - múltiples selectores posibles
        name_selectors = [
            ".product-card-name", ".product-name", ".nombre-producto",
            "[data-testid*='name']", "h3", "h4", "h5"
        ]
        nombre = "N/A"
        for selector in name_selectors:
            try:
                name_elem = element.find_element(By.CSS_SELECTOR, selector)
                nombre = name_elem.text.strip()
                if nombre: break
            except: pass
        producto['nombre'] = nombre
        
        descripcion = element.get_attribute('title') or nombre
        producto['descripcion'] = descripcion
        
        # Precios - múltiples selectores posibles
        # El selector principal que encontraste en la imagen para el precio actual/oferta es ".prices-main-price"
        precio_selectors = [
            ".prices-main-price", # Este es el que está en la imagen para el precio actual/oferta
            ".precio-oferta",
            ".price-current",
            ".precio-actual",
            "[data-testid*='price']"
        ]
        precio_oferta = "N/A"
        for selector in precio_selectors:
            try:
                price_elem = element.find_element(By.CSS_SELECTOR, selector)
                precio_text = price_elem.text.strip()
                if precio_text and '$' in precio_text:
                    precio_oferta = precio_text
                    break
            except: pass
        producto['precio_oferta'] = precio_oferta
        
        # Precio original
        # Aquí el cambio clave: ".prices-old-price" es el selector de la imagen.
        original_selectors = [
            ".prices-old-price", # AGREGADO/PRIORIZADO según tu imagen
            ".prices-was-price",
            ".precio-antes",
            ".price-original",
            ".precio-tachado"
        ]
        precio_original = "N/A"
        for selector in original_selectors:
            try:
                orig_elem = element.find_element(By.CSS_SELECTOR, selector)
                precio_original = orig_elem.text.strip()
                if precio_original: break
            except: pass
        producto['precio_original'] = precio_original
        
        # Marca
        brand_selectors = [
            ".product-card-brand", # Este parece un selector probable para la marca
            ".marca",
            ".brand",
            ".categoria" # Mantenemos por si acaso, si a veces se usa para marca
        ]
        marca = "N/A"
        for selector in brand_selectors:
            try:
                brand_elem = element.find_element(By.CSS_SELECTOR, selector)
                marca = brand_elem.text.strip()
                if marca: break
            except: pass
        producto['marca'] = marca

        # ASIGNAR CATEGORÍA USANDO LA FUNCIÓN DE CLASIFICACIÓN
        # Asegúrate de que 'nombre' y 'descripcion' ya estén extraídos antes de esta línea.
        producto['categoria'] = classify_product_category(producto.get('nombre', 'N/A'), producto.get('descripcion', 'N/A'))
        
        # Imagen
        try:
            img_elem = element.find_element(By.TAG_NAME, "img")
            img_src = img_elem.get_attribute('src') or img_elem.get_attribute('data-src')
            producto['imagen'] = img_src if img_src else "N/A"
        except:
            producto['imagen'] = "N/A"
        
        # URL del producto
        try:
            url_elem = None
            if element.tag_name == 'a':
                url_elem = element
            else:
                try: url_elem = element.find_element(By.TAG_NAME, 'a')
                except: pass
            producto['url_producto'] = url_elem.get_attribute('href') if url_elem else "N/A"
        except:
            producto['url_producto'] = "N/A"
        
        producto['fecha_scraping'] = time.strftime('%Y-%m-%d %H:%M:%S')
        
        return producto
        
    except Exception as e:
        print(f"Error extrayendo producto: {e}")
        return None

def get_current_page_number(driver):
    """
    Obtiene el número de la página actual visible en el paginador.
    """
    try:
        active_page_element = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "button.page-number.active"))
        )
        return int(active_page_element.text.strip())
    except Exception as e:
        return 1

def find_next_page_button(driver, current_page_number):
    """
    Busca el botón correspondiente a la siguiente página numerada.
    """
    next_page_to_find = current_page_number + 1
    print(f"Buscando botón para la página: {next_page_to_find}")

    try:
        next_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, f"//button[contains(@class, 'page-number') and text()='{next_page_to_find}']"))
        )
        if "active" not in next_button.get_attribute('class'):
            print(f"✅ Encontrado botón para página {next_page_to_find}.")
            return next_button
        else:
            print(f"⚠️ El botón para la página {next_page_to_find} es el botón activo actual. Fin de paginación.")
            return None
    except Exception as e:
        print(f"❌ No se encontró el botón para la página {next_page_to_find} o no es clickeable: {e}")
        return None

def scrape_products_from_current_page(driver):
    """
    Extrae productos de la página actual.
    """
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3) # Dar tiempo para que los productos finales de la vista carguen
    
    products, selector_used = wait_for_products_to_load(driver)
    
    if not products:
        print("No se encontraron productos con selectores conocidos en esta página.")
        return []
    
    productos_data = []
    print(f"Extrayendo información de {len(products)} productos en esta página...")
    
    for i, product in enumerate(products):
        producto_info = extract_product_info(product)
        if producto_info and producto_info['nombre'] != "N/A":
            productos_data.append(producto_info)
    
    return productos_data

def scrape_santa_isabel_selenium():
    """
    Función principal de scraping usando Selenium con paginación por número de página.
    """
    url = "https://www.santaisabel.cl/santas-ofertas?nombre_promo=menu-conoce-todas-las-ofertas-30012024"
    
    driver = setup_driver(headless=False)
    if not driver:
        return []
    
    all_productos = []
    processed_pages = set()
    max_pages_to_scrape = 100 # <-- CAMBIA ESTE NÚMERO PARA PROBAR MENOS PÁGINAS (ej. 3, 5)
    
    try:
        print(f"Navegando a: {url}")
        driver.get(url)
        
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(5)
        
        print(f"Título de la página: {driver.title}")
        print(f"URL actual: {driver.current_url}")
        
        # Intentar cerrar cookies/popups
        try:
            print("Intentando cerrar popups o aceptar cookies...")
            cookie_buttons = driver.find_elements(By.XPATH, "//button[contains(translate(text(), 'ACEPTAR', 'aceptar'), 'aceptar') or contains(translate(text(), 'CERRAR', 'cerrar'), 'cerrar') or contains(translate(text(), 'OK', 'ok'), 'ok')]")
            if cookie_buttons:
                print(f"Encontrados {len(cookie_buttons)} botones de cookies/popups. Haciendo clic en el primero.")
                driver.execute_script("arguments[0].click();", cookie_buttons[0])
                time.sleep(2)
            else:
                print("No se encontraron botones de cookies/popups evidentes.")
        except Exception as e:
            print(f"No se pudo cerrar el popup de cookies: {e}")

        page_number = 1
        while page_number <= max_pages_to_scrape:
            print(f"\n{'='*50}")
            print(f"📄 PROCESANDO PÁGINA {page_number}")
            print(f"URL: {driver.current_url}")
            print(f"{'='*50}")

            current_url_before_scrape = driver.current_url
            
            productos_pagina = scrape_products_from_current_page(driver)
            
            if not productos_pagina and page_number > 1:
                print(f"⚠️ No se encontraron productos en la página {page_number}. Puede ser el final del catálogo.")
                break
            
            new_product_count = 0
            for prod in productos_pagina:
                if prod['nombre'] != "N/A" and not any(p['nombre'] == prod['nombre'] for p in all_productos):
                    all_productos.append(prod)
                    new_product_count += 1
            
            print(f"✅ Extraídos {new_product_count} productos nuevos de la página {page_number}.")
            print(f"📊 Total acumulado: {len(all_productos)} productos.")

            processed_pages.add(page_number)

            current_displayed_page = get_current_page_number(driver)
            if current_displayed_page != page_number:
                print(f"Advertencia: El navegador muestra página {current_displayed_page}, se esperaba {page_number}. Sincronizando.")
                page_number = current_displayed_page
            
            next_button_to_click = find_next_page_button(driver, page_number)
            
            if next_button_to_click:
                try:
                    print(f"🔄 Haciendo clic en el botón de página {next_button_to_click.text.strip()}...")
                    
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", next_button_to_click)
                    time.sleep(1)
                    
                    next_button_to_click.click()
                    
                    WebDriverWait(driver, 20).until(
                        EC.any_of(
                            EC.url_changes(current_url_before_scrape),
                            EC.text_to_be_present_in_element((By.CSS_SELECTOR, "button.page-number.active"), str(page_number + 1))
                        )
                    )
                    time.sleep(5)
                    
                    new_page_number_after_click = get_current_page_number(driver)
                    if new_page_number_after_click == page_number + 1:
                        print(f"✅ Navegación exitosa a página {new_page_number_after_click}.")
                        page_number = new_page_number_after_click
                    else:
                        print(f"⚠️ No se detectó avance a la siguiente página esperada ({page_number + 1}). Página actual: {new_page_number_after_click}. Terminando paginación.")
                        break

                except Exception as e:
                    print(f"❌ Error al hacer clic o esperar la navegación a la siguiente página: {e}")
                    break
            else:
                print(f"🏁 No se encontró botón para la siguiente página. Fin de la paginación.")
                break
            
        print(f"\n{'='*60}")
        print(f"🎉 SCRAPING COMPLETADO")
        print(f"📊 Total de páginas procesadas: {len(processed_pages)}")
        print(f"📦 Total de productos extraídos: {len(all_productos)}")
        print(f"{'='*60}")
        
        return all_productos
        
    except Exception as e:
        print(f"Error general durante el scraping: {e}")
        return []
    
    finally:
        print("\nPresiona Enter para cerrar el navegador...")
        input()
        driver.quit()

def guardar_productos_json(productos, nombre_archivo='productos_santa_isabel_selenium.json'):
    """
    Guarda los productos en un archivo JSON
    """
    try:
        with open(nombre_archivo, 'w', encoding='utf-8') as f:
            json.dump(productos, f, ensure_ascii=False, indent=2)
        print(f"Productos guardados en {nombre_archivo}")
        return True
    except Exception as e:
        print(f"Error al guardar el archivo JSON: {e}")
        return False

def main():
    """
    Función principal
    """
    print("=== SCRAPER SANTA ISABEL CON SELENIUM ===")
    print("NOTA: Se abrirá un navegador Chrome a la mitad de la pantalla para el scraping.")
    
    productos = scrape_santa_isabel_selenium()
    
    if productos:
        print(f"\n✓ Se extrajeron {len(productos)} productos exitosamente")
        
        if guardar_productos_json(productos):
            print("¡Scraping completado exitosamente!")
            
            print("\n=== EJEMPLOS DE PRODUCTOS EXTRAÍDOS ===")
            for i, producto in enumerate(productos[:5]): # Mostrar 5 ejemplos ahora
                print(f"\nProducto {i+1}:")
                for key, value in producto.items():
                    if key == 'imagen' and len(str(value)) > 50:
                        print(f"  {key}: {str(value)[:50]}...")
                    else:
                        print(f"  {key}: {value}")
        else:
            print("Error al guardar los productos")
    else:
        print("No se pudieron extraer productos")
        print("Revisa la consola para más detalles sobre lo ocurrido.")

if __name__ == "__main__":
    main()