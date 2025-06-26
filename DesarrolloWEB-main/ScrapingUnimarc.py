import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import json
import re
from datetime import datetime
import time

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
        # Es muy probable que estos no se encuentren en Unimarc, pero se incluyen por tu lista.
    ],
    "Tecnología": [
        "audífono", "cargador", "cable", "pilas", "batería", "smart", "tablet",
        "celular", "impresora", "cartucho", "toner", "computador", "monitor",
        "teclado", "mouse", "parlante", "auricular"
        # Muy poco probable encontrar esto en Unimarc, pero se incluyen.
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
        # Es posible que Unimarc venda algunos productos de parafarmacia o primeros auxilios.
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


class UnimarcScraper:
    def __init__(self, headless=True, debug=False):
        self.base_url = "https://www.unimarc.cl"
        self.ofertas_url_base = "https://www.unimarc.cl/ofertas/ofertas-unimarc" # Base URL for offers
        self.headless = headless
        self.debug = debug
        self.driver = None
        self.wait = None
        
    def setup_driver(self):
        """Configura el driver de Selenium"""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Suprimir logs innecesarios
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 15)
            print("Driver configurado exitosamente")
            if not self.headless:
                print("Navegador visible abierto - puedes ver lo que está haciendo")
        except Exception as e:
            print(f"Error al configurar el driver: {e}")
            print("Asegúrate de tener ChromeDriver instalado y en el PATH.")
            print("Puedes instalarlo con 'pip install webdriver-manager' y luego usar 'webdriver_manager.chrome.ChromeDriverManager().install()'.")
            return False
        return True
    
    def close_driver(self):
        """Cierra el driver"""
        if self.driver and not self.debug:
            self.driver.quit()
        elif self.debug:
            input("Presiona Enter para cerrar el navegador...")
            self.driver.quit()
    
    def clean_text(self, text):
        """Limpia y normaliza el texto"""
        if not text:
            return ""
        return re.sub(r'\s+', ' ', text.strip())
    
    def extract_price(self, price_text):
        """
        Extrae el precio numérico (float) del texto, manejando formato chileno (punto para miles, coma para decimales).
        """
        if self.debug:
            print(f"DEBUG: Input a extract_price: '{price_text}'")

        if not price_text:
            if self.debug:
                print("DEBUG: Input de precio vacío.")
            return None
        
        # Eliminar símbolos de moneda y otros caracteres no numéricos, excepto puntos y comas
        clean_text = re.sub(r'[^\d.,]', '', str(price_text))
        if self.debug:
            print(f"DEBUG: Texto limpio antes de normalizar: '{clean_text}'")

        # Normalizar el formato chileno a formato estándar de float (punto decimal)
        if ',' in clean_text and '.' in clean_text:
            # Si hay ambos, y la coma es el último separador, asumimos coma decimal. Ej: "1.234,50" -> "1234.50"
            if clean_text.rfind(',') > clean_text.rfind('.'):
                clean_text = clean_text.replace('.', '').replace(',', '.')
            else: # Si el punto es el último separador, asumimos punto decimal. Ej: "1,234.50" (menos común en Chile)
                clean_text = clean_text.replace(',', '') # Remover comas de miles
        elif ',' in clean_text:
            clean_text = clean_text.replace(',', '.')
        elif '.' in clean_text:
            # Si solo hay puntos, asumimos puntos de miles, a menos que sea un número pequeño como "1.5"
            # Si tiene solo un punto y menos de 3 dígitos después, asumimos decimal
            if clean_text.count('.') == 1 and len(clean_text.split('.')[-1]) < 3:
                pass # Ya está en formato decimal correcto
            else: # Asumir que son miles
                clean_text = clean_text.replace('.', '')
                
        if self.debug:
            print(f"DEBUG: Texto limpio después de normalizar: '{clean_text}'")

        try:
            price_val = float(clean_text)
            # Validar que sea un precio realista (ej. entre 10 y 10,000,000 CLP)
            if 10 <= price_val <= 10000000:
                if self.debug:
                    print(f"DEBUG: Precio extraído (float): {price_val}")
                return price_val
            else:
                if self.debug:
                    print(f"DEBUG: Precio {price_val} fuera de rango realista.")
                return None
        except ValueError:
            if self.debug:
                print(f"DEBUG: ValueError al convertir '{clean_text}' a float.")
            return None
        return None
    
    def wait_and_scroll(self):
        """Espera a que la página cargue los contenedores de productos y luego hace scroll para cargar más contenido dinámico."""
        print("Esperando a que los productos en la página carguen completamente y haciendo scroll...")
        
        try:
            # Esperar a que al menos un contenedor de producto esté presente
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'section[id^="shelf__vertical--"].smu-impressed')))
            print("Contenedores de productos iniciales cargados.")
        except TimeoutException:
            print("La página tardó demasiado en cargar los contenedores de productos. Continuando con el scroll.")
            
        scroll_height = self.driver.execute_script("return document.body.scrollHeight")
        last_scroll_height = 0
        scroll_attempts = 0
        max_scroll_attempts = 5 # Limitar los intentos para evitar bucles infinitos
        
        while scroll_height > last_scroll_height and scroll_attempts < max_scroll_attempts:
            last_scroll_height = scroll_height
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2) # Pausa para que cargue el lazy loading
            scroll_height = self.driver.execute_script("return document.body.scrollHeight")
            scroll_attempts += 1
            if self.debug:
                print(f"DEBUG: Scrolled. Current height: {scroll_height}, Attempts: {scroll_attempts}")
        
        self.driver.execute_script("window.scrollTo(0, 0);") # Volver al inicio
        time.sleep(1)
        print("Scroll completado.")
        
    def find_product_containers(self):
        """Encuentra contenedores de productos usando los selectores más precisos."""
        # Basado en el HTML completo proporcionado, el contenedor más fiable es la sección.
        # <section class="baseContainer_container__TSgMX ... smu-impressed" role="" id="shelf__vertical--hamburguesa-vacuno-la-crianza-premium-1-kg" ...>
        selectors_to_try = [
            'section[id^="shelf__vertical--"].smu-impressed', # Selector principal y más específico
            'div.baseContainer_container__TSgMX.ab__shelves.abc__shelves.baseContainer_justify-start___sjrG', # Contenedor externo del card (si la sección no funciona)
        ]
        
        all_potential_products = []
        
        for selector in selectors_to_try:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    all_potential_products.extend(elements)
                    if self.debug:
                        print(f"DEBUG: Encontrados {len(elements)} elementos con selector: '{selector}'")
            except Exception as e:
                if self.debug:
                    print(f"DEBUG: Selector '{selector}' falló: {e}")
                continue
        
        unique_products = []
        seen_product_identifiers = set() 
        
        for product_elem in all_potential_products:
            try:
                # Usar la URL del producto como identificador único si es posible
                # Buscar el enlace principal dentro de este contenedor de producto
                product_link_elem = product_elem.find_elements(By.CSS_SELECTOR, 
                    'div[id="shelf__title"] > a.Link_link___5dmQ[href*="/product/"]')
                product_url = ''
                if product_link_elem:
                    href = product_link_elem[0].get_attribute('href')
                    if href and href.startswith('/product/'):
                        product_url = self.base_url + href
                    elif href and self.base_url in href:
                        product_url = href
                
                # Si tenemos una URL única, la usamos. Si no, usamos el innerHTML como antes.
                identifier = product_url if product_url else hash(product_elem.get_attribute('innerHTML'))

                if identifier in seen_product_identifiers:
                    continue # Ya procesado
                
                # Heurísticas para validar si es un producto real (puede que el selector sea demasiado amplio)
                has_name = bool(product_elem.find_elements(By.CSS_SELECTOR, 'p.Shelf_nameProduct__CXI5M'))
                has_offer_price = bool(product_elem.find_elements(By.CSS_SELECTOR, 'p[id^="listPrice__offerPrice--discountprice-"]'))
                has_img = bool(product_elem.find_elements(By.TAG_NAME, 'img'))
                
                if has_name and has_offer_price and has_img: # Requerir estos elementos clave
                    unique_products.append(product_elem)
                    seen_product_identifiers.add(identifier)
                    
            except Exception as e:
                if self.debug:
                    print(f"DEBUG: Error al validar elemento potencial de producto: {e}")
                continue
        
        print(f"Total productos únicos y válidos encontrados: {len(unique_products)}")
        return unique_products
    
    def extract_product_data(self, product_element, index):
        """Extrae datos de un elemento de producto usando los selectores precisos."""
        product_data = {
            'nombre': '',
            'descripcion': '',
            'precio_original': None, 
            'precio_oferta': None,   
            'marca': '',
            'categoria': 'Desconocida', # Por defecto, será actualizado por la función
            'imagen': '',
            'url_producto': '',
            'fecha_scraping': datetime.now().isoformat()
        }
        
        try:
            if self.debug:
                print(f"\n--- PROCESANDO PRODUCTO {index} ---")
            
            # El HTML proporcionado indica que la URL, nombre y marca están dentro del div con id="shelf__title"
            shelf_title_div = product_element.find_elements(By.ID, 'shelf__title')
            
            if shelf_title_div:
                main_product_link = shelf_title_div[0].find_elements(By.CSS_SELECTOR, 'a.Link_link___5dmQ.Link_link--none__BjwPj[href*="/product/"]')
            else:
                # Si no se encuentra shelf__title, buscar el enlace principal directamente en el product_element
                main_product_link = product_element.find_elements(By.CSS_SELECTOR, 'a.Link_link___5dmQ.Link_link--none__BjwPj[href*="/product/"]')

            if main_product_link:
                href = main_product_link[0].get_attribute('href')
                if href:
                    if href.startswith('/product/'):
                        product_data['url_producto'] = self.base_url + href
                    else:
                        product_data['url_producto'] = href
                
                # Extraer nombre del <p> con clase Shelf_nameProduct__CXI5M dentro del enlace
                name_elem = main_product_link[0].find_elements(By.CSS_SELECTOR, 'p.Shelf_nameProduct__CXI5M')
                if name_elem:
                    product_data['nombre'] = self.clean_text(name_elem[0].text)
                    product_data['descripcion'] = product_data['nombre'] # Descripción es el mismo nombre por ahora
                
                # Extraer marca del <p> con clase Shelf_brandText__sGfsS dentro del enlace
                brand_elem = main_product_link[0].find_elements(By.CSS_SELECTOR, 'p.Shelf_brandText__sGfsS')
                if brand_elem:
                    product_data['marca'] = self.clean_text(brand_elem[0].text)

            # Extraer Imagen del Producto
            # La imagen también está dentro del enlace principal, o en un div de imagen dentro del contenedor general.
            img_elem = product_element.find_elements(By.CSS_SELECTOR, 'img[src*="unimarc.vtexassets.com"]')
            if img_elem:
                src = img_elem[0].get_attribute('src') or img_elem[0].get_attribute('data-src')
                if src and (src.startswith('http') or src.startswith('//') or src.startswith('/')):
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/') and not src.startswith(self.base_url):
                        src = self.base_url + src
                    product_data['imagen'] = src

            # Extraer Precio de Oferta
            offer_price_selectors = [
                'p[id^="listPrice__offerPrice--discountprice-"][class*="Text_text--xl__l05SR"]',
                'p.Text_text--xl__l05SR', # More general class for large text, often prices
                'p[class*="price"]', # Generic price class
                'span[class*="price"]',
                'div[class*="price"]'
            ]
            for selector in offer_price_selectors:
                try:
                    offer_price_elem = product_element.find_elements(By.CSS_SELECTOR, selector)
                    if offer_price_elem:
                        # Prioritize the one that contains '$' and is not empty
                        for elem in offer_price_elem:
                            if '$' in elem.text and self.clean_text(elem.text):
                                numeric_offer_price = self.extract_price(elem.text)
                                if numeric_offer_price is not None:
                                    product_data['precio_oferta'] = f"${numeric_offer_price:,.0f}".replace(",", ".")
                                    if self.debug:
                                        print(f"DEBUG: Oferta encontrada con selector '{selector}': {elem.text}")
                                    break # Found a valid offer price, move on
                        if product_data['precio_oferta'] is not None:
                            break # Break from outer loop if price found
                except Exception as e:
                    if self.debug:
                        print(f"DEBUG: Fallo al intentar selector de oferta '{selector}': {e}")
                    continue
            
            # Extraer Precio Original (tachado)
            original_price_selectors = [
                'p[id^="listPrice__offerPrice--listprice-"][class*="Text_text--line-through__1V_2e"]',
                'p.Text_text--line-through__1V_2e', # More general class for line-through text
                'span[class*="line-through"]', # Generic line-through class
                'div[class*="line-through"]',
                'p[class*="old-price"]',
                'span[class*="old-price"]',
                'div[class*="old-price"]'
            ]
            for selector in original_price_selectors:
                try:
                    original_price_elem = product_element.find_elements(By.CSS_SELECTOR, selector)
                    if original_price_elem:
                        for elem in original_price_elem:
                            if '$' in elem.text and self.clean_text(elem.text):
                                numeric_original_price = self.extract_price(elem.text)
                                if numeric_original_price is not None:
                                    product_data['precio_original'] = f"${numeric_original_price:,.0f}".replace(",", ".")
                                    if self.debug:
                                        print(f"DEBUG: Original encontrado con selector '{selector}': {elem.text}")
                                    break # Found a valid original price, move on
                        if product_data['precio_original'] is not None:
                            break # Break from outer loop if price found
                except Exception as e:
                    if self.debug:
                        print(f"DEBUG: Fallo al intentar selector original '{selector}': {e}")
                    continue

            # Asignar categoría utilizando la función de clasificación
            product_data['categoria'] = classify_product_category(product_data['nombre'], product_data['descripcion'])


            if self.debug:
                print(f"DEBUG: Datos extraídos para producto {index}:")
                for key, value in product_data.items():
                    if key != 'fecha_scraping' and (value is not None and value != ''):
                        print(f"  {key}: {value}")
                if product_data['precio_oferta'] is None:
                    print(f"DEBUG: Precio de oferta para producto {product_data['nombre'][:30]}... no capturado.")
                if product_data['precio_original'] is None:
                    print(f"DEBUG: Precio original para producto {product_data['nombre'][:30]}... no capturado.")
            
        except Exception as e:
            print(f"ERROR: Error extrayendo datos del producto {index}: {e}")
        
        return product_data
    
    def scrape_ofertas(self):
        """Realiza el scraping de ofertas"""
        if not self.setup_driver():
            return []
        
        all_products_data = []
        current_page_num = 1
        # Establece un límite bajo para pruebas. Cambiar a None o un número alto para raspar todo.
        max_pages_to_scrape = None # Cambiado a 10 páginas para pruebas
        
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Navegando a la página de ofertas: {self.ofertas_url_base}")
            self.driver.get(self.ofertas_url_base)
            
            if not self.headless:
                print("🔍 Navegador visible abierto - puedes ver lo que está haciendo")
            
            while True:
                if max_pages_to_scrape is not None and current_page_num > max_pages_to_scrape:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Límite de {max_pages_to_scrape} páginas alcanzado. Terminando paginación.")
                    break

                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] --- Procesando Página {current_page_num} ---")
                
                # Esperar y hacer scroll para cargar contenido dinámico
                self.wait_and_scroll()
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Buscando contenedores de productos en Página {current_page_num}...")
                products_on_page = self.find_product_containers()
                
                if not products_on_page and current_page_num == 1:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ No se encontraron productos en la primera página con los selectores y heurísticas actuales.")
                    if not self.headless:
                        input("Presiona Enter para continuar (revisa la página manualmente si quieres intentar depurar)...")
                    break # Salir si no hay productos en la primera página
                elif not products_on_page and current_page_num > 1:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] No se encontraron más productos en la página {current_page_num}. Fin de la paginación.")
                    break # Fin de la paginación

                print(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ Procesando {len(products_on_page)} elementos de productos únicos en Página {current_page_num}...")
                
                for i, product_element in enumerate(products_on_page):
                    try:
                        if self.debug or not self.headless:
                            # Resaltar el elemento actual para visualización en modo no-headless
                            self.driver.execute_script(
                                "arguments[0].style.border='3px solid red'; arguments[0].scrollIntoView({block: 'center'});", product_element)
                            time.sleep(0.1) # Pausa corta para visualización
                        
                        product_info = self.extract_product_data(product_element, i+1)
                        
                        if (product_info['nombre'] or 
                            product_info['precio_oferta'] is not None or 
                            product_info['precio_original'] is not None):
                            all_products_data.append(product_info)
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ Producto {i+1} (Pág {current_page_num}) agregado: {product_info['nombre'][:50]}... (Oferta: {product_info['precio_oferta']})")
                        else:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠ Producto {i+1} (Pág {current_page_num}) sin datos suficientes para ser útil. Saltando.")
                            
                        if self.debug or not self.headless:
                            # Quitar resaltado
                            self.driver.execute_script(
                                "arguments[0].style.border='';", product_element)
                            
                    except StaleElementReferenceException:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠ Elemento estancado (StaleElementReferenceException) para producto {i+1} en Página {current_page_num}. Reintentando o saltando.")
                        continue
                    except Exception as e:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error procesando producto {i+1} (Pág {current_page_num}): {e}")
                        continue
                
                # --- Lógica de Paginación ---
                next_page_arrow_link = None
                try:
                    # Esperar un momento adicional para que los elementos de paginación se rendericen
                    time.sleep(2) 

                    # Construir el selector CSS para el enlace de la flecha derecha (siguiente página)
                    # La URL del enlace a la página 2 es "/ofertas/ofertas-unimarc?&amp;page=2"
                    # Usamos '&page=' para mayor compatibilidad con & y &amp;
                    target_next_page_url_segment = f"/ofertas/ofertas-unimarc?&page={current_page_num + 1}"
                    
                    # Intentar encontrar el enlace exacto a la siguiente página y esperar a que sea clicable
                    # Buscamos el <a> que contenga el SVG con id="ArrowRightNavigate" y el href de la siguiente página.
                    # El selector CSS para esto sería:
                    # a[href*="/ofertas/ofertas-unimarc?&page={next_page_num_expected}"] svg#ArrowRightNavigate
                    # Sin embargo, el click debe ser en el <a>, no en el SVG.
                    # Vamos a buscar el <a> que tenga el href correcto y dentro tenga el SVG.
                    
                    # XPath es más flexible para esto:
                    # //a[contains(@href, '{target_next_page_url_segment}') and .//*[name()='svg' and @id='ArrowRightNavigate']]
                    
                    next_page_num_expected = current_page_num + 1
                    
                    xpath_for_next_arrow = f'//a[contains(@href, "page={next_page_num_expected}") and .//*[name()="svg" and @id="ArrowRightNavigate"]]'

                    if self.debug:
                        print(f"DEBUG: Buscando enlace de flecha derecha para la página {next_page_num_expected} con XPath: {xpath_for_next_arrow}")

                    next_page_arrow_link = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, xpath_for_next_arrow)),
                        f"No se encontró el enlace de flecha derecha clicable para la página {next_page_num_expected}."
                    )
                    
                    if self.debug:
                        print(f"DEBUG: ✅ Enlace de flecha derecha a página {next_page_num_expected} encontrado y clicable: {next_page_arrow_link.get_attribute('href')}")
                        
                except TimeoutException as te:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Timeout al buscar el enlace de paginación: {te}. Fin de la paginación.")
                    break # No hay más páginas o el enlace no apareció a tiempo
                except NoSuchElementException as nsee:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Enlace de paginación no encontrado: {nsee}. Fin de la paginación.")
                    break
                except Exception as e:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error inesperado en la lógica de paginación al encontrar enlaces: {e}. Terminando paginación.")
                    break

                # Si se encontró y es clicable, hacemos clic y esperamos la carga de la nueva página.
                if next_page_arrow_link:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Haciendo clic en el enlace de la flecha a la página siguiente: {next_page_arrow_link.get_attribute('href')}")
                    
                    # Store the URL before click to confirm it changes
                    old_url = self.driver.current_url
                    
                    try:
                        # Desplazarse al elemento para asegurar que sea visible y clicable
                        self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", next_page_arrow_link)
                        time.sleep(1) # Pequeña pausa para el scroll
                        
                        next_page_arrow_link.click() # Hacer clic en el enlace de la flecha de la siguiente página

                        # Esperar a que la URL cambie A LA URL DE LA SIGUIENTE PÁGINA ESPECÍFICA
                        expected_new_url_pattern = f"{self.ofertas_url_base}\\?.*page={current_page_num + 1}"
                        self.wait.until(EC.url_matches(expected_new_url_pattern),
                                        f"La URL no cambió a la esperada ({expected_new_url_pattern}) después de hacer clic.")
                        
                        # Después de que la URL cambie, esperar que los elementos de productos en la *nueva* página estén presentes
                        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'section[id^="shelf__vertical--"].smu-impressed')),
                                        "No se encontraron productos en la nueva página después del cambio de URL.")
                        
                        current_page_num += 1 # Incrementar el número de página actual solo después de una navegación exitosa
                        time.sleep(3) # Dar tiempo adicional para que el contenido se renderice completamente
                    except StaleElementReferenceException:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠ El enlace de la página siguiente se volvió obsoleto al hacer clic. Terminando paginación.")
                        break
                    except TimeoutException as te:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ La nueva página no cargó después de hacer clic en el enlace: {te}. Terminando paginación.")
                        break
                    except Exception as e:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error al hacer clic o esperar la carga de la nueva página: {e}. Terminando paginación.")
                        break
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] No se encontró un enlace válido a la siguiente página. Fin de la paginación.")
                    break
            
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🎉 Scraping completado. {len(all_products_data)} productos extraídos.")
            return all_products_data
            
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error inesperado durante el scraping: {e}")
            return []
        finally:
            self.close_driver() # Siempre cerrar el driver
    
    def save_to_json(self, data, filename=None):
        """Guarda los datos en un archivo JSON"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"unimarc_ofertas_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str) 
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 💾 Datos guardados en: {filename}")
            return filename
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error al guardar el archivo: {e}")
            return None

def main():
    """Función principal para ejecutar el scraper"""
    print("=== 🛒 SCRAPER UNIMARC OFERTAS ===")
    print("Nota: Este script utiliza Selenium y requiere ChromeDriver.")
    print("Si encuentras problemas, verifica tu instalación de ChromeDriver.")
    print()
    
    # Configuraciones interactivas
    headless_input = input("¿Ejecutar en modo headless (sin ventana del navegador visible)? (y/n, default=n): ").lower()
    headless = headless_input == 'y' or headless_input == '' 
    
    debug_input = input("¿Activar modo debug (más información y navegador abierto al final si no es headless)? (y/n, default=n): ").lower()
    debug = debug_input == 'y'
    
    scraper = UnimarcScraper(headless=headless, debug=debug)
    
    try:
        # Realizar scraping
        productos = scraper.scrape_ofertas()
        
        if productos:
            # Guardar en JSON
            filename = scraper.save_to_json(productos)
            
            # Mostrar estadísticas
            print(f"\n=== 📊 RESUMEN DEL SCRAPING ===")
            print(f"Total productos extraídos: {len(productos)}")
            print(f"Productos con nombre: {len([p for p in productos if p['nombre']])}")
            print(f"Productos con precio de oferta: {len([p for p in productos if p['precio_oferta'] is not None])}")
            print(f"Productos con precio original: {len([p for p in productos if p['precio_original'] is not None])}")
            print(f"Productos con imagen: {len([p for p in productos if p['imagen']])}")
            print(f"Productos con URL: {len([p for p in productos if p['url_producto']])}")
            print(f"Archivo JSON guardado en: {filename if filename else 'Error al guardar'}")
            
            # Mostrar algunos ejemplos de productos
            print(f"\n=== 🔍 EJEMPLOS DE PRODUCTOS EXTRAÍDOS (primeros 5) ===")
            valid_products_sample = [p for p in productos if p['nombre'] or p['precio_oferta']][:5]
            for i, producto in enumerate(valid_products_sample):
                print(f"\n📦 Producto {i+1}:")
                # Los precios ahora son cadenas, se imprimen directamente
                print(f"  📝 Nombre: {producto['nombre'] or 'N/A'}")
                print(f"  💰 Precio Original: {producto['precio_original'] or 'N/A'}")
                print(f"  🏷️ Precio Oferta: {producto['precio_oferta'] or 'N/A'}")
                print(f"  🖼️ URL Imagen: {'✓' if producto['imagen'] else '✗'}")
                print(f"  🔗 URL Producto: {'✓' if producto['url_producto'] else '✗'}")
                print(f"  🏷️ Categoría: {producto['categoria'] or 'N/A'}") # Mostrar la categoría
        else:
            print("\n❌ No se encontraron productos o hubo un error grave durante el scraping.")
            print("💡 Sugerencias:")
            print("  - Intenta ejecutar el script sin modo headless (responde 'n' a la primera pregunta) para ver la página cargando.")
            print("  - Activa el modo debug (responde 'y' a la segunda pregunta) para ver más detalles en la consola.")
            print("  - Asegúrate de tener una conexión a internet estable y que la URL de Unimarc esté accesible.")
            
    except KeyboardInterrupt:
        print("\n⚠️ Scraping interrumpido por el usuario.")
    except Exception as e:
        print(f"❌ Error inesperado en la función principal: {e}")

if __name__ == "__main__":
    main()
