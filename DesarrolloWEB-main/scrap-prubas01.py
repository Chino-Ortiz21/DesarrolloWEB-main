# Importa las librerías necesarias
from playwright.sync_api import sync_playwright # Para la automatización del navegador
import json # Para guardar los datos en formato JSON
import re # Para expresiones regulares, útil para limpiar precios
import time # Para añadir pausas explícitas
import random # Para generar retrasos aleatorios y simular comportamiento humano
import unicodedata # Para normalizar texto (quitar acentos)

def scrape_lider_products(url, output_file="ofertas_lider.json"): # MODIFICADO: Nombre de archivo de salida
    """
    Realiza scraping de productos de una URL específica de Lider.cl
    y guarda los datos en un archivo JSON, incluyendo la navegación por paginación
    y técnicas anti-bot avanzadas.

    Args:
        url (str): La URL base de la página de Lider.cl a scrapear.
        output_file (str): El nombre del archivo JSON donde se guardarán los datos.
    """
    all_products_data = [] # Lista para almacenar los datos de todos los productos de todas las páginas

    # Mapeo de categorías de Lider a tus categorías predefinidas
    # Si una categoría de Lider no tiene un mapeo claro, se usará 'Todas las ofertas' como fallback
    category_mapping_dict = {
        "todas las ofertas": "Todas las ofertas",
        "abarrotes": "Abarrotes",
        "bebidas": "Bebidas",
        "lacteos": "Lácteos",
        "carnes": "Carnes",
        "frutas y verduras": "Frutas y Verduras",
        "bebes": "Bebés",
        "mascotas": "Mascotas",
        "hogar": "Hogar",
        "ropa": "Ropa",
        "tecnologia": "Tecnología",
        "juguetes": "Juguetes",
        "farmacia": "Farmacia",
        # Mapeos adicionales para categorías de Lider que pueden aparecer en las migas de pan
        # O si se quieren agrupar en una de tus categorías existentes
        "electronica": "Tecnología",
        "electrodomesticos": "Hogar",
        "muebles": "Hogar",
        "deportes": "Hogar", # Asignación genérica si no hay una mejor
        "automovil": "Hogar", # Asignación general para 'Automóvil'
        "neumaticos": "Hogar", # Asignación general
        "llantas": "Hogar", # Asignación general
        "perfumeria": "Farmacia", # Asignación general
        "mundo bebe": "Bebés" # Ejemplo de alias
    }

    def normalize_text(text):
        """Normaliza el texto a minúsculas y elimina acentos."""
        if isinstance(text, str):
            text = text.lower()
            text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
        return text

    def get_mapped_category(breadcrumbs, product_name):
        """
        Intenta mapear la categoría de las migas de pan o el nombre del producto
        a una de las categorías predefinidas por el usuario.
        """
        for crumb in reversed(breadcrumbs): # Empezar por la más específica
            normalized_crumb = normalize_text(crumb)
            for keyword, mapped_cat in category_mapping_dict.items():
                if keyword in normalized_crumb:
                    return mapped_cat
        
        # Si no hay mapeo directo por breadcrumbs, intentar con el nombre del producto
        normalized_product_name = normalize_text(product_name)
        for keyword, mapped_cat in category_mapping_dict.items():
            if keyword in normalized_product_name:
                return mapped_cat

        return "Todas las ofertas" # Fallback si no se encuentra ningún mapeo

    # Inicia Playwright y lanza un navegador Chromium
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False, # Mantener en False para depuración visual
            slow_mo=random.randint(100, 300), # Retraso aleatorio por operación (ms)
            args=[ # Argumentos para evitar detección de automatización
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--disable-features=IsolateOrigins,site-per-process' # Puede ayudar con iframes
            ]
        )
        
        # Crear contexto con user agent y viewport realistas
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'es-CL,es;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1', # Do Not Track header
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        )
        
        page = context.new_page()
        
        # Inyectar script para eliminar propiedades que indican automatización (ej. navigator.webdriver)
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5], // Simular plugins comunes
            });
            
            Object.defineProperty(navigator, 'languages', {
                get: () => ['es-CL', 'es', 'en'], // Simular idiomas
            });
            
            window.chrome = { // Simular objeto chrome
                runtime: {},
            };
            
            Object.defineProperty(navigator, 'permissions', { // Simular permisos
                get: () => ({
                    query: () => Promise.resolve({ state: 'granted' }),
                }),
            });
            
            // Más técnicas de ofuscación
            ['iframe', 'frame', 'embed'].forEach(tag => {
                HTMLOrSVGElement.prototype.attachShadow = () => null; // Deshabilitar Shadow DOM
            });
            
            // Algunas páginas usan esto para detectar automatización
            window.outerWidth = window.innerWidth;
            window.outerHeight = window.innerHeight;
        """)

        # Manejar automáticamente los diálogos (alertas, confirmaciones, prompts)
        page.on("dialog", lambda dialog: dialog.accept()) 
        page_number = 1

        def handle_captcha_advanced():
            """
            Manejo avanzado de CAPTCHA con múltiples estrategias.
            Retorna True si el CAPTCHA parece resuelto o no se detectó, False si falló.
            """
            print("🔍 Verificando presencia de CAPTCHA...")
            
            # Selectores comunes para iframes de CAPTCHA o contenedores visibles
            captcha_iframe_selectors = [
                "#px-captcha-modal",
                "iframe[src*='captcha']",
                "iframe[title*='captcha']",
                ".g-recaptcha iframe", # Para reCAPTCHA
                "#challenge-stage", # Cloudflare
                ".cf-browser-verification" # Cloudflare
            ]
            
            captcha_detected = False
            target_iframe = None
            
            # Buscar el iframe o contenedor principal del CAPTCHA
            for selector in captcha_iframe_selectors:
                if page.is_visible(selector, timeout=2000):
                    print(f"🚨 CAPTCHA detectado con selector: {selector}")
                    # Si es un iframe, intenta obtenerlo como frame_locator
                    if "iframe" in selector:
                        target_iframe = page.frame_locator(selector)
                        if target_iframe.count() > 0: # Asegurarse de que el iframe existe
                            captcha_detected = True
                            break
                    else: # Si no es un iframe, es un contenedor en la página principal
                        captcha_detected = True
                        break # Ya encontramos el contenedor principal, no es un iframe

            if not captcha_detected:
                print("✅ No se detectó CAPTCHA")
                return True
            
            print("🤖 Intentando resolver CAPTCHA...")
            
            try:
                # Estrategia 1: Botón de presionar y mantener (para PX/PerimeterX)
                # Si encontramos un iframe para CAPTCHA, intentamos interactuar dentro de él.
                if target_iframe:
                    print("Método 1: Buscando botón 'Pulsa y mantener pulsado' dentro del iframe...")
                    
                    button_texts = [
                        "Pulsa y mantener pulsado", # Tu caso específico
                        "PULSAR Y MANTENER PULSADO",
                        "Press and Hold",
                        "Hold",
                        "Mantener presionado"
                    ]
                    
                    button_found = False
                    for text in button_texts:
                        try:
                            # Localizador sensible a mayúsculas/minúsculas y espacios
                            hold_button = target_iframe.locator(f'button:has-text("{text}")')
                            if hold_button.is_visible(timeout=5000): # Aumentado timeout para visibilidad del botón
                                print(f"Botón encontrado: '{text}'")
                                
                                time.sleep(random.uniform(1, 3)) # Pausa pre-clic
                                
                                # Obtener coordenadas del botón y mover el mouse de forma natural
                                box = hold_button.bounding_box()
                                if box:
                                    page.mouse.move(
                                        box["x"] + box["width"] / 2 + random.randint(-5, 5),
                                        box["y"] + box["height"] / 2 + random.randint(-5, 5)
                                    )
                                    
                                    # Presionar y mantener con variación de tiempo
                                    page.mouse.down()
                                    hold_time = random.uniform(8, 15) # Tiempo de hold más largo y variable
                                    print(f"Manteniendo presionado por {hold_time:.1f} segundos...")
                                    time.sleep(hold_time)
                                    page.mouse.up()
                                    
                                    button_found = True
                                    break
                                else:
                                    print(f"No se pudo obtener el bounding box para el botón '{text}'")
                        except Exception as e_btn:
                            print(f"Error al buscar/interactuar con botón '{text}': {e_btn}")
                            continue
                    
                    if button_found:
                        print("✅ Botón procesado. Esperando resolución...")
                        # Esperar a que el modal del CAPTCHA o el iframe desaparezcan
                        try:
                            # Esperamos que el elemento principal del CAPTCHA esté oculto
                            page.wait_for_selector(selector, state="hidden", timeout=30000) 
                            print("✅ CAPTCHA resuelto exitosamente o ha desaparecido.")
                            time.sleep(random.uniform(3, 5)) # Pausa adicional
                            return True
                        except Exception as e_resolve:
                            print(f"⚠️ Timeout esperando resolución de CAPTCHA o no desapareció: {e_resolve}")
                            # Si el modal no desaparece, puede que no se haya resuelto
                            return False
                
                # Estrategia 2: Checkbox de verificación (para reCAPTCHA u otros)
                checkbox_selectors = [
                    "input[type='checkbox'][name*='captcha']", # General
                    ".recaptcha-checkbox",
                    "#recaptcha-anchor",
                    "div[role='checkbox']"
                ]
                
                for selector in checkbox_selectors:
                    if page.is_visible(selector, timeout=2000):
                        print(f"Encontrado checkbox de verificación: {selector}. Haciendo clic...")
                        page.click(selector)
                        time.sleep(random.uniform(3, 6)) # Pausa para que se resuelva
                        # Esperar que el checkbox no esté visible o que cambie su estado a resuelto
                        try:
                            page.wait_for_selector(selector, state="hidden", timeout=15000)
                            print("✅ Checkbox resuelto exitosamente.")
                            return True
                        except:
                            print("⚠️ Timeout esperando resolución del checkbox.")
                            return False
                
                # Estrategia 3: Espera manual (último recurso)
                print("🔄 No se pudo resolver automáticamente. Esperando resolución manual...")
                print("Por favor, resuelve el CAPTCHA manualmente en el navegador abierto.")
                
                # Esperar hasta 120 segundos para resolución manual
                for i in range(120):
                    time.sleep(1)
                    # Verificar si *ninguno* de los selectores de CAPTCHA sigue visible
                    if not any(page.is_visible(sel, timeout=100) for sel in captcha_iframe_selectors):
                        print("✅ CAPTCHA resuelto manualmente")
                        return True
                    if i % 10 == 0:
                        print(f"Esperando resolución manual... ({120-i}s restantes)")
                
                print("❌ Timeout en resolución de CAPTCHA manual. No se pudo continuar.")
                return False
                
            except Exception as e:
                print(f"❌ Error general en manejo de CAPTCHA: {e}")
                return False

        def safe_navigate_to_page(target_url, retries=3):
            """Navegación segura con reintentos y manejo de CAPTCHA,
            además de verificación de contenido de producto."""
            for attempt in range(retries):
                try:
                    print(f"🌐 Navegando a: {target_url} (Intento {attempt + 1})")
                    # MODIFICACIÓN: Cambiar wait_until a "load" para asegurar la carga completa de recursos
                    page.goto(target_url, wait_until="load", timeout=90000) 
                    
                    time.sleep(random.uniform(2, 5)) # Pausa aleatoria
                    
                    if not handle_captcha_advanced():
                        if attempt < retries - 1:
                            print("🔄 Reintentando navegación después de fallo de CAPTCHA...")
                            continue
                        else:
                            # Lanzar excepción para que el script se detenga si el CAPTCHA no se resuelve
                            raise Exception("No se pudo resolver el CAPTCHA después de varios intentos.")
                    
                    # MODIFICACIÓN: Después de resolver CAPTCHA o si no hay, esperar al selector de productos
                    # Este selector es el que usamos para los elementos de producto
                    product_item_base_selector_check = '.mb0.ph0-xl.pt0-xl.bb.b--near-white.w-25.pb3-m.ph1'
                    try:
                        print("Verificando si los productos se cargaron correctamente en la página...")
                        # Esperar por cualquier estado 'visible' o 'attached' del selector para mayor flexibilidad
                        page.wait_for_selector(product_item_base_selector_check, state='visible', timeout=30000)
                        print("✅ Productos detectados después de navegación/CAPTCHA.")
                        return True
                    except Exception as e_prod_wait:
                        print(f"⚠️ No se detectaron productos después de navegación/CAPTCHA: {e_prod_wait}")
                        if attempt < retries - 1:
                            print("🔄 Reintentando navegación...")
                            time.sleep(random.uniform(5, 10)) # Pausa antes de reintentar
                            continue
                        else:
                            # Si después de reintentos no hay productos, es un fallo crítico
                            raise Exception(f"No se encontraron productos en la página principal después de {retries} intentos. URL: {target_url}")
                    
                except Exception as e:
                    print(f"❌ Error en navegación (intento {attempt + 1}): {e}")
                    if attempt < retries - 1:
                        time.sleep(random.uniform(5, 10)) # Pausa más larga antes de reintentar
                    else:
                        raise e # Lanza el error si se acabaron los reintentos
            return False # Nunca debería llegar aquí si retries > 0 y se lanza excepción

        # Navegación inicial
        try:
            if not safe_navigate_to_page(url):
                print("❌ No se pudo iniciar el scraping debido a problemas de navegación o CAPTCHA inicial.")
                browser.close()
                return # Salir si la navegación inicial falla
        except Exception as e:
            print(f"❌ Error fatal en la navegación inicial: {e}")
            browser.close()
            return # Salir si hay un error fatal en la navegación inicial

        while True:
            print(f"\n--- 📄 Procesando página {page_number} ---")

            try:
                # Verificar elementos de productos
                product_item_base_selector = '.mb0.ph0-xl.pt0-xl.bb.b--near-white.w-25.pb3-m.ph1'
                
                # Intentar esperar el selector principal de productos. Si falla, probar alternativas.
                try:
                    # Este wait_for_selector ya debería haber sido satisfecho por safe_navigate_to_page
                    # Pero lo mantenemos como una doble verificación o para cuando la paginación cambie el selector
                    page.wait_for_selector(product_item_base_selector, timeout=10000) # Reducido timeout ya que ya lo esperamos antes
                except:
                    print("⚠️ No se encontraron productos con el selector principal en la página actual, probando alternativo...")
                    alternative_selectors = [
                        '[data-automation-id="product-item"]', # Otro selector posible
                        '.product-tile',
                        '.product-card',
                        '[data-testid="product-tile"]'
                    ]
                    
                    found_alt = False
                    for alt_selector in alternative_selectors:
                        try:
                            page.wait_for_selector(alt_selector, timeout=5000)
                            product_item_base_selector = alt_selector # Usar el selector alternativo encontrado
                            found_alt = True
                            break
                        except:
                            continue
                    
                    if not found_alt:
                        print("❌ No se encontraron productos en esta página con ningún selector. Finalizando.")
                        break # Salir si no hay productos

                print(f"✅ Productos detectados en página {page_number}")

                # Scroll inteligente con detección de carga
                previous_product_count = 0
                scroll_attempts = 0
                max_scroll_attempts = 20 # Número máximo de scrolls por página
                no_change_count = 0 # Contador para salir si el número de productos no cambia

                while scroll_attempts < max_scroll_attempts and no_change_count < 3:
                    # Scroll suave para simular humano
                    page.evaluate("""
                        window.scrollTo({
                            top: document.body.scrollHeight,
                            behavior: 'smooth'
                        });
                    """)
                    
                    time.sleep(random.uniform(3, 6)) # Pausa variable para carga
                    
                    current_products_in_view = page.query_selector_all(product_item_base_selector)
                    current_count = len(current_products_in_view)
                    
                    print(f"📊 Página {page_number}: {current_count} productos después de scroll {scroll_attempts + 1}")
                    
                    if current_count > previous_product_count:
                        no_change_count = 0
                        previous_product_count = current_count
                    else:
                        no_change_count += 1 # Aumentar si no hay cambio
                    
                    scroll_attempts += 1

                print(f"📈 Total productos visibles en página {page_number}: {previous_product_count}")

                # Extraer categoría (de las migas de pan)
                category_elements = page.query_selector_all('nav.breadcrumb span')
                categories_text = [re.sub(r'\s+', ' ', el.inner_text()).strip() 
                                    for el in category_elements if el.inner_text().strip()]
                
                # Obtiene todos los elementos de producto de la página actual, después de todos los scrolls
                current_page_product_elements = page.query_selector_all(product_item_base_selector)
                print(f"🔄 Extrayendo datos de {len(current_page_product_elements)} productos...")

                if not current_page_product_elements: # Doble verificación si no hay productos
                    print("❌ No se encontraron productos para extraer en esta página. Finalizando.")
                    break

                for i, product_el in enumerate(current_page_product_elements):
                    try:
                        nombre = ""
                        descripcion = "" # Inicializar descripción
                        precio_actual = None
                        precio_anterior = None
                        descuento = 0
                        link = ""
                        imagen = "" # Reincorporado para asegurar que se extrae la imagen
                        
                        # Extraer nombre (varios selectores)
                        name_selectors = [
                            'span[data-automation-id="product-title"]',
                            '.w_q67L', 
                            'h3[itemprop="name"]', 
                            '.product-name',
                            'a[data-automation-id="product-title"] .product-title-text'
                        ]
                        for selector in name_selectors:
                            name_el = product_el.query_selector(selector)
                            if name_el and name_el.inner_text().strip():
                                nombre = name_el.inner_text().strip()
                                break
                        
                        # Intentar extraer descripción si existe un selector específico
                        description_selectors = [
                            '.product-item__description', 
                            '.product-description',
                            '[itemprop="description"]'
                        ]
                        for selector in description_selectors:
                            desc_el = product_el.query_selector(selector)
                            if desc_el and desc_el.inner_text().strip() and desc_el.inner_text().strip() != nombre:
                                descripcion = desc_el.inner_text().strip()
                                break
                        
                        # Si no se encontró una descripción diferente, usa el nombre
                        if not descripcion:
                            descripcion = nombre
                            
                        # Extraer link del producto
                        link_el = product_el.query_selector('a[link-identifier]') or product_el.query_selector('a[itemprop="url"]')
                        if link_el:
                            relative_link = link_el.get_attribute('href')
                            if relative_link:
                                link = "https://www.lider.cl" + relative_link 
                        
                        # Extraer precio actual (varios selectores)
                        price_current_selectors = [
                            'div[data-automation-id="product-price"] .b.black', 
                            '.price-current',
                            '.current-price',
                            '[data-automation-id="product-price"] span:first-child',
                            '.product-price-current',
                            '[itemprop="price"]'
                        ]
                        for selector in price_current_selectors:
                            price_el = product_el.query_selector(selector)
                            if price_el and price_el.inner_text().strip():
                                price_text = price_el.inner_text().strip()
                                price_match = re.search(r'[\d.]+', price_text.replace('.', '').replace(',', ''))
                                if price_match:
                                    precio_actual = int(price_match.group())
                                    break

                        # Extraer precio original (varios selectores)
                        price_original_selectors = [
                            'div[data-automation-id="product-price"] .gray.strike', 
                            '.price-original',
                            '.original-price',
                            '.strike',
                            '.product-price-old'
                        ]
                        for selector in price_original_selectors:
                            original_el = product_el.query_selector(selector)
                            if original_el and original_el.inner_text().strip():
                                original_text = original_el.inner_text().strip()
                                original_match = re.search(r'[\d.]+', original_text.replace('.', '').replace(',', ''))
                                if original_match:
                                    precio_anterior = int(original_match.group())
                                    break
                                
                        # Extraer imagen (reincorporado y mejorado)
                        image_selectors = [
                            'img[data-testid="productTileImage"]',
                            'img[data-automation-id="product-image"]',
                            '.product-image img',
                            'img'
                        ]
                        for selector in image_selectors:
                            img_el = product_el.query_selector(selector)
                            if img_el:
                                image_url = (img_el.get_attribute('src') or 
                                             img_el.get_attribute('data-src') or 
                                             (img_el.get_attribute('srcset') or '').split(' ')[0])
                                if image_url:
                                    imagen = image_url
                                    break


                        # Calcular descuento
                        if precio_actual is not None and precio_anterior is not None and precio_anterior > 0:
                            descuento = round(((precio_anterior - precio_actual) / precio_anterior) * 100)
                            if descuento < 0: # Asegurarse de que el descuento no sea negativo
                                descuento = 0
                        elif precio_actual is not None and precio_anterior is None:
                            descuento = 0 
                        
                        # Obtener la categoría mapeada. Se pasa el nombre del producto también como fallback.
                        categoria = get_mapped_category(categories_text, nombre)

                        # Añadir el producto a la lista con el formato solicitado
                        if nombre and precio_actual is not None:
                            all_products_data.append({
                                "nombre": nombre,
                                "descripcion": descripcion, 
                                "precio_actual": precio_actual,
                                "precio_anterior": precio_anterior,
                                "descuento": descuento,
                                "link": link,
                                "categoria": categoria,
                                "imagen": imagen # Asegurarse de que la imagen se incluya
                            })
                        
                        if (i + 1) % 10 == 0: 
                            print(f"  📦 Procesados {i + 1}/{len(current_page_product_elements)} productos")
                            
                    except Exception as e_product:
                        print(f"⚠️ Error extrayendo producto {i + 1}: {e_product}")
                        continue 

                print(f"✅ Página {page_number} completada. Total productos acumulados: {len(all_products_data)}")

                # --- Lógica para Paginación ---
                next_page_selectors = [
                    'a[aria-label="Página siguiente"]',
                    'button[aria-label="Página siguiente"]',
                    '.pagination-next',
                    '[data-automation-id="next-page"]',
                    'a.page-link.next' 
                ]

                next_button = None
                for selector in next_page_selectors:
                    try:
                        next_button = page.query_selector(selector)
                        if next_button and next_button.is_visible() and not next_button.is_disabled():
                            print(f"➡️ Botón 'Página siguiente' encontrado con selector '{selector}'.")
                            break
                        else:
                            next_button = None 
                    except Exception as e_next_btn:
                        print(f"Debug: Selector '{selector}' falló: {e_next_btn}")
                        next_button = None

                if next_button:
                    print(f"➡️ Navegando a página {page_number + 1}...")
                    
                    next_button.click(timeout=30000)
                    time.sleep(random.uniform(3, 6))
                    
                    page.wait_for_load_state("domcontentloaded", timeout=90000)
                    handle_captcha_advanced() 
                    page.wait_for_load_state("networkidle", timeout=60000)

                    page_number += 1
                else:
                    print("🏁 No se encontró el botón 'Página siguiente' o está deshabilitado. Fin de la paginación.")
                    break 
                
            except Exception as e:
                print(f"❌ Error crítico en página {page_number}: {e}")
                print("Asumiendo que no hay más páginas o ocurrió un error irrecuperable. Deteniendo el scraping.")
                break 

        print(f"\n🎉 Scraping completado!")
        print(f"📊 Total productos extraídos: {len(all_products_data)}")
        print(f"📄 Páginas procesadas: {page_number}")

        # Guardar datos
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_products_data, f, ensure_ascii=False, indent=4)
        
        print(f"💾 Datos guardados en: {output_file}")
        
        # Mostrar resumen
        if all_products_data:
            categories = set(product['categoria'] for product in all_products_data)
            print(f"🏷️ Categorías encontradas: {', '.join(categories)}")
            
            prices = [p['precio_actual'] for p in all_products_data if p['precio_actual']]
            if prices:
                print(f"💰 Rango de precios: ${min(prices):,} - ${max(prices):,}")

        browser.close()

# URL a scrapear
url_to_scrape = "https://www.lider.cl/browse/automovil/neumaticos-y-llantas/llantas/10661928_41321373_27892378"

if __name__ == "__main__":
    scrape_lider_products(url_to_scrape, "pruebas_scraping01.json")
