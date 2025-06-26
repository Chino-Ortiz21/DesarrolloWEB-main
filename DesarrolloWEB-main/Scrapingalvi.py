import json
import time
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager

# === CATEGORÍAS PERSONALIZADAS ===
# Se usan para clasificar los productos una vez extraídos.
PRODUCT_CATEGORIES = {
    "Abarrotes": ["arroz", "pasta", "harina", "salsa", "legumbre", "azúcar", "aceite", "cafe", "te", "mermelada", "conserva", "granos", "cereales", "pastas", "snacks salados"],
    "Bebidas": ["bebida", "agua", "jugo", "néctar", "gaseosa", "isotónica", "energética"],
    "Lácteos": ["leche", "queso", "yogurt", "huevos", "mantequilla", "crema", "postre", "postres lácteos"],
    "Carnes": ["pollo", "vacuno", "cerdo", "hamburguesa", "filete", "salchicha", "embutido", "pavo", "pescado", "marisco"],
    "Frutas/Verduras": ["papa", "tomate", "lechuga", "manzana", "platano", "naranja", "cebolla", "zanahoria", "fruta", "verdura", "hortalizas"],
    "Bebés": ["pañal", "mamadera", "bebé", "infantil", "toallitas", "papilla", "compota", "cereal bebé"],
    "Mascotas": ["alimento", "mascota", "perro", "gato", "pellets", "snack mascota"],
    "Hogar": ["frazada", "plato", "vaso", "servilleta", "utensilio", "basura", "organización", "cocina", "limpieza hogar"],
    "Aseo": ["cloro", "detergente", "limpiador", "lavalozas", "jabón", "shampoo", "acondicionador", "papel", "toalla"],
    "Confitería": ["galleta", "dulce", "caramelo", "chocolate", "snack", "chicle", "bombones", "gomitas"],
    "Panadería": ["pan", "tortilla", "bollito", "repostería", "masa", "bizcocho", "queque", "empanada"],
    "Licores": ["cerveza", "vino", "pisco", "licor", "espumante", "destilado", "ron", "vodka", "whisky"],
    "Cuidado Personal": ["shampoo", "crema", "higiene", "afeitar", "desodorante", "pasta dental", "cepillo", "maquillaje", "perfume", "protector solar"],
    "Otros": [] # Categoría por defecto si no se clasifica
}

def classify_product(nombre, descripcion=""):
    """
    Clasifica un producto en una categoría predefinida basándose en palabras clave.
    """
    text_to_classify = (nombre + " " + descripcion).lower()
    for categoria, keywords in PRODUCT_CATEGORIES.items():
        for keyword in keywords:
            # Usar \b para asegurar que se busque la palabra completa
            if re.search(r'\b' + re.escape(keyword) + r'\b', text_to_classify):
                return categoria
    return "Otros"

def extract_clean_price(price_text):
    """
    Extrae y limpia un precio de una cadena de texto, convirtiéndolo a entero.
    Ej: "$1.234" -> 1234
    " $1.050 c/u" -> 1050
    """
    if not isinstance(price_text, str):
        return None
    # Eliminar símbolo de moneda ($), separador de miles (.), y texto "c/u"
    cleaned_price = re.sub(r'[^\d]', '', price_text)
    try:
        return int(cleaned_price)
    except ValueError:
        return None

def format_price_for_json(price_int):
    """
    Formatea un precio entero a la cadena con formato chileno "$X.YYY"
    """
    if price_int is None:
        return "N/A"
    return f"${price_int:,.0f}".replace(",", ".")

def setup_driver(headless=False): # MODIFICADO: headless=False para ver el navegador
    """
    Configura y devuelve una instancia del WebDriver de Chrome.
    """
    options = Options()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.75 Safari/537.36")

    # Usamos ChromeDriverManager para que no necesites especificar la ruta de ChromeDriver.
    service = Service(ChromeDriverManager().install()) 
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    driver.set_page_load_timeout(60) # Aumentar el tiempo de espera de carga de página

    return driver

def scroll_down_to_load_content(driver, wait, max_scrolls=10):
    """
    Desplaza la página hacia abajo para cargar contenido dinámico.
    """
    last_height = driver.execute_script("return document.body.scrollHeight")
    scroll_count = 0
    while scroll_count < max_scrolls:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)  # Espera para que el nuevo contenido cargue
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            # Si no hay un nuevo scroll, podría ser el final de la página o no hay más contenido.
            # Intenta un scroll suave hasta la parte inferior de la ventana visible para activar cargas
            driver.execute_script("window.scrollBy(0, window.innerHeight);")
            time.sleep(2)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                print("No más contenido para cargar al hacer scroll.")
                break
        last_height = new_height
        scroll_count += 1
        print(f"Scroll down: {scroll_count}")


def scrape_alvi_category(url):
    """
    Scrapea productos de una URL de categoría específica en Alvi.cl.
    Maneja el scroll para cargar más productos y la paginación a través del botón "Siguiente página".
    """
    driver = setup_driver(headless=False) # Usar el valor de setup_driver
    wait = WebDriverWait(driver, 45) # Aumentar el tiempo de espera para elementos
    products_in_category = []
    scraped_product_urls_in_category = set() # Para evitar duplicados en la misma sesión/categoría
    
    print(f"\nIniciando scraping para la categoría: {url}")

    try:
        driver.get(url)
        time.sleep(7) # Espera inicial más larga para que la página cargue completamente

        # Intentar cerrar pop-ups si aparecen (ajustar selectores si es necesario)
        try:
            # Selectores más específicos para pop-ups de VTEX o de ubicación/bienvenida
            # Aumentar el tiempo de espera para el pop-up, es crucial que se cierre.
            close_popup_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 
                    "button[aria-label*='Cerrar'], button[data-testid*='close-button'], .vtex-modal-layout-0-x-closeButton, button.close-button, div.close-button, a.close-button"
                ))
            )
            print(f"Cerrando posible pop-up...")
            close_popup_button.click()
            time.sleep(2)
        except TimeoutException:
            print("No se encontró pop-up de bienvenida/ubicación en 10 segundos o no es necesario cerrarlo.")
        except Exception as e:
            print(f"Error al intentar cerrar pop-up: {e}")

        current_page_num = 1
        # MODIFICADO: Bucle de paginación con límite de 5 páginas
        while current_page_num <= 5: 
            print(f"Scrapeando página {current_page_num} de {url}")
            # Realizar scroll para asegurar que todos los productos de la página se carguen
            scroll_down_to_load_content(driver, wait, max_scrolls=5) # Puedes ajustar max_scrolls

            # Selectores de producto más precisos. Probamos con el `[class^='ProductCard_card__']`
            # que apareció en tu último error, junto con los anteriores.
            product_card_selectors = [
                "[class^='ProductCard_card__']", # Selector más genérico para clases dinámicas como "ProductCard_card__<hash>"
                "div.ShelfAlvi_shelf__ic5TF", # Contenedor principal de cada producto en el listado (si es clase estática)
                ".vtex-product-summary-2-x-container", # Fallback VTEX genérico
                "div[data-vtex-ps-id]" # Otro fallback genérico
            ]

            products_on_current_page = 0
            try:
                # Esperar por al menos un elemento de producto.
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ", ".join(product_card_selectors))))
                # Una vez que la página carga, encontrar todos los elementos.
                product_elements = driver.find_elements(By.CSS_SELECTOR, ", ".join(product_card_selectors))
                print(f"Detectados {len(product_elements)} elementos de producto potenciales en la página actual.")
            except TimeoutException:
                print("No se encontraron elementos de productos en la página actual después de scrolls. Fin de la categoría.")
                break # Salir si no hay productos o hay un timeout

            for el in product_elements:
                try:
                    # Extraer URL del producto
                    # Buscar el enlace que contiene '/product/' en su href
                    product_link_elem = el.find_element(By.CSS_SELECTOR, 'a[href*="/product/"]')
                    url_producto = product_link_elem.get_attribute("href")
                    
                    if url_producto in scraped_product_urls_in_category:
                        continue # Ya extraído en esta sesión o página anterior
                    scraped_product_urls_in_category.add(url_producto)

                    # Extraer Nombre del producto
                    # El nombre suele estar en un <p> con clases como "Text_text__cB7NM" y "Text_text--md__H7JI_"
                    nombre = "N/A"
                    try:
                        # Buscar el <p> que contiene el nombre del producto, que a menudo está dentro de un <a>
                        nombre_elem = el.find_element(By.CSS_SELECTOR, "a[href*='/product/'] p.Text_text__cB7NM.Text_text--md__H7JI_")
                        nombre = nombre_elem.text.strip()
                    except NoSuchElementException:
                        # Fallback a un selector más genérico si el anterior falla
                        try:
                            nombre_elem = el.find_element(By.CSS_SELECTOR, ".vtex-product-summary-2-x-productBrandName, .vtex-product-summary-2-x-productNameContainer span")
                            nombre = nombre_elem.text.strip()
                        except:
                            pass # No se pudo extraer el nombre

                    # Extraer Marca
                    # La marca suele estar en un <p> con clase "ShelfAlvi_brandText__P1CMr"
                    marca = "N/A"
                    try:
                        marca_elem = el.find_element(By.CSS_SELECTOR, "p.ShelfAlvi_brandText__P1CMr")
                        marca = marca_elem.text.strip()
                    except NoSuchElementException:
                        # Fallback VTEX genérico
                        try:
                            marca_elem = el.find_element(By.CSS_SELECTOR, ".vtex-product-summary-2-x-brandName, .vtex-product-summary-2-x-productBrand")
                            marca = marca_elem.text.strip()
                        except:
                            pass

                    # Extraer URL de la imagen
                    imagen = "N/A"
                    try:
                        # La imagen suele ser un <img> con data-nimg="future-fill" dentro de un <div> con Picture_picture__X5s1h
                        imagen_elem = el.find_element(By.CSS_SELECTOR, "img[data-nimg='future-fill']")
                        img_src = imagen_elem.get_attribute("src")
                        if img_src and "data:image" not in img_src: # Evitar base64 si es posible
                            imagen = img_src
                    except NoSuchElementException:
                        # Fallback VTEX genérico
                        try:
                            imagen_elem = el.find_element(By.CSS_SELECTOR, ".vtex-product-summary-2-x-imageNormal, .vtex-search-result-3-x-productImage img")
                            img_src = imagen_elem.get_attribute("src")
                            if img_src and "data:image" not in img_src:
                                imagen = img_src
                        except:
                            pass

                    # Extraer Precio Regular (tachado)
                    precio_original = "N/A"
                    try:
                        # En Alvi debug, está en un <p> con texto "$X.YYY" y clase "Text_text--black__zYYxI" bajo "Precio regular"
                        original_price_text_elem = el.find_element(By.XPATH, ".//p[contains(text(),'Precio regular')]/following-sibling::div//p[contains(@class,'Text_text__cB7NM')]")
                        precio_original = format_price_for_json(extract_clean_price(original_price_text_elem.text))
                    except NoSuchElementException:
                        # Fallback a VTEX genérico
                        try:
                            original_price_elem = el.find_element(By.CSS_SELECTOR, ".vtex-store-components-3-x-listPrice, .vtex-product-price-1-x-listPrice span.vtex-product-price-1-x-listPrice")
                            precio_original = format_price_for_json(extract_clean_price(original_price_elem.text))
                        except:
                            pass

                    # Extraer Precio Oferta (el precio principal de venta)
                    # En Alvi debug, parece ser el "Precio socio" o el precio "Desde X un"
                    precio_oferta = "N/A"
                    try:
                        # Priorizamos el "Precio socio" si existe
                        socio_price_elem = el.find_element(By.XPATH, ".//p[contains(text(),'Precio socio')]/following-sibling::*[2]//span[contains(@class,'ShelfAlvi_textPricePromotion__ZwkNN')]")
                        precio_oferta = format_price_for_json(extract_clean_price(socio_price_elem.text))
                    except NoSuchElementException:
                        # Si no hay precio socio, buscar el precio principal (puede ser el "Desde X un" más bajo o el sellingPrice general)
                        try:
                            # Buscar directamente el precio que aparece grande, que es el de oferta/socio
                            main_offer_price_elem = el.find_element(By.CSS_SELECTOR, ".vtex-store-components-3-x-sellingPrice, .vtex-product-price-1-x-sellingPrice span.vtex-product-price-1-x-sellingPrice, span.ShelfAlvi_textPricePromotion__ZwkNN")
                            precio_oferta = format_price_for_json(extract_clean_price(main_offer_price_elem.text))
                        except:
                            pass

                    # Extraer Precios por Cantidad (ej. "Desde 2 un: $X.YYY c/u", "Ahorra Y%")
                    precios_por_cantidad = []
                    try:
                        # Buscar los contenedores específicos para los precios por cantidad
                        # Utiliza la estructura que se ve en el HTML de depuración:
                        # div que contiene "Desde X un" y otro div para el precio
                        quantity_price_blocks = el.find_elements(By.CSS_SELECTOR, ".baseContainer_container__TSgMX.baseContainer_justify-start___sjrG.baseContainer_align-center__q7f7k.baseContainer_flex-direction--row__4HZkU")
                        
                        for block in quantity_price_blocks:
                            try:
                                # Dentro del bloque, buscar el texto de la cantidad y el precio
                                quantity_text_elem = block.find_element(By.XPATH, ".//p[contains(@class,'Text_text__cB7NM') and contains(@class,'Text_text--sm__KnF3l') and contains(@class,'Text_text--gray__r4RdT')]")
                                price_text_elem = block.find_element(By.XPATH, ".//span[contains(@class,'ShelfAlvi_textPricePromotion__ZwkNN')]")
                                
                                q_text = quantity_text_elem.text.strip()
                                price_text = price_text_elem.text.strip()

                                # Extraer cantidad (ej. "Desde 2 un" -> 2)
                                cantidad_match = re.search(r'Desde\s*(\d+)\s*un', q_text, re.IGNORECASE)
                                cantidad = int(cantidad_match.group(1)) if cantidad_match else 1 # Por defecto 1 si no encuentra "Desde X un"

                                precio_unit_limpio = extract_clean_price(price_text)

                                ahorro_pct = 0
                                try:
                                    # Buscar el porcentaje de ahorro dentro del mismo bloque o un sibling
                                    ahorro_elem = block.find_element(By.XPATH, ".//label[contains(text(),'Ahorra ') and contains(text(),'%')]")
                                    ahorro_match = re.search(r'Ahorra\s*(\d+)%', ahorro_elem.text, re.IGNORECASE)
                                    ahorro_pct = int(ahorro_match.group(1)) if ahorro_match else 0
                                except NoSuchElementException:
                                    pass # No hay ahorro explícito en este bloque

                                if precio_unit_limpio is not None:
                                    if ahorro_pct == 0 and precio_original != "N/A" and extract_clean_price(precio_original) is not None:
                                        original_val = extract_clean_price(precio_original)
                                        if original_val > 0 and original_val > precio_unit_limpio:
                                            ahorro_pct = round(((original_val - precio_unit_limpio) / original_val) * 100)
                                    
                                    precios_por_cantidad.append({
                                        "cantidad_minima": cantidad,
                                        "precio_unitario": format_price_for_json(precio_unit_limpio),
                                        "ahorro_porcentaje": ahorro_pct
                                    })
                            except NoSuchElementException:
                                continue # Este bloque no contiene la info esperada, pasa al siguiente
                            except Exception as e_inner:
                                print(f"Advertencia: Error al parsear bloque de precio por cantidad: {e_inner}")
                                continue

                    except Exception as e_qty:
                        # print(f"Advertencia: No se pudieron extraer todos los precios por cantidad para un producto. Error: {e_qty}")
                        pass


                    # Clasificar el producto
                    categoria_clasificada = classify_product(nombre, descripcion=nombre)

                    products_in_category.append({
                        "nombre": nombre,
                        "descripcion": nombre, # Usamos el nombre como descripción por simplicidad
                        "precio_oferta": precio_oferta,
                        "precio_original": precio_original,
                        "precios_por_cantidad": precios_por_cantidad,
                        "marca": marca,
                        "categoria": categoria_clasificada,
                        "imagen": imagen,
                        "url_producto": url_producto,
                        "fecha_scraping": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                    products_on_current_page += 1

                except StaleElementReferenceException:
                    print(f"Advertencia: StaleElementReferenceException al procesar un producto. Reintentando la página actual.")
                    # Si un elemento se vuelve "stale" (la página se actualizó), forzar la re-búsqueda de todos los elementos.
                    break # Salir del bucle for y re-evaluar la página.
                except NoSuchElementException as e:
                    # Este error significa que un sub-elemento esperado no se encontró en una tarjeta de producto.
                    # No es crítico para el flujo general, pero indica un dato faltante.
                    # print(f"Advertencia: Elemento no encontrado dentro de una tarjeta de producto. Error: {e}")
                    continue # Continúa con el siguiente producto
                except Exception as e:
                    print(f"Error desconocido al procesar un producto (posible URL: {url_producto if 'url_producto' in locals() else 'N/A'}): {e}")
                    continue

            if products_on_current_page == 0 and current_page_num > 1:
                print("No se encontraron nuevos productos en esta página después de desplazar. Posiblemente sea el final.")
                break # Si no hay productos nuevos después del scroll, es el fin de la paginación.
            
            # === Lógica de paginación ===
            # Intentar encontrar el botón de "Siguiente página" o los enlaces numéricos
            next_page_found = False
            # MODIFICADO: Solo intenta avanzar si current_page_num es menor que 5
            if current_page_num < 5: 
                try:
                    # 1. Intentar hacer clic en el botón de flecha ">" de la paginación
                    # Este selector se basa en la imagen que me proporcionaste.
                    arrow_button_selector = "div.Pagination_paginator__arrow__1Yz69 > a[aria-label='Ir a la siguiente página']"
                    next_arrow_button = None
                    try:
                        next_arrow_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, arrow_button_selector)))
                        # Verificar que el botón no esté deshabilitado (clase o atributo)
                        if "disabled" not in next_arrow_button.get_attribute("class") and next_arrow_button.get_attribute("aria-disabled") == "false":
                            print("Haciendo clic en el botón de flecha 'Siguiente página'...")
                            driver.execute_script("arguments[0].click();", next_arrow_button)
                            time.sleep(5) # Esperar a que la nueva página cargue
                            current_page_num += 1
                            next_page_found = True
                        else:
                            print("Botón de flecha 'Siguiente página' deshabilitado.")
                    except TimeoutException:
                        print("No se encontró el botón de flecha 'Siguiente página'.")
                        pass # Continúa intentando con enlaces numéricos

                    # 2. Si la flecha no funcionó o no se encontró, intentar con el enlace numérico de la siguiente página
                    if not next_page_found: 
                        # Buscar el enlace a la siguiente página numérica
                        # Se busca un enlace (a) que contenga un div, con un p cuyo texto sea el número de la siguiente página.
                        # El selector de paginación de Alvi es bastante específico con las clases dinámicas dentro del link.
                        next_page_link_selector = f"//a[contains(@class, 'Link_link--none__') and .//p[text()='{current_page_num + 1}']]"
                        next_page_link = wait.until(EC.element_to_be_clickable((By.XPATH, next_page_link_selector)))
                        print(f"Haciendo clic en el enlace a la página {current_page_num + 1}...")
                        driver.execute_script("arguments[0].click();", next_page_link)
                        time.sleep(5) # Esperar más tiempo para la carga de la nueva página
                        current_page_num += 1
                        next_page_found = True

                except TimeoutException:
                    print(f"No se encontró el botón o enlace a la siguiente página ({current_page_num + 1}). Asumiendo fin de paginación o límite de páginas.")
                    break # No hay más paginación o llegamos al límite
                except Exception as e:
                    print(f"Error al manejar la paginación a la página {current_page_num + 1}: {e}")
                    break # Salir en caso de otros errores de paginación
            else:
                print(f"Alcanzado el límite de {5} páginas. Finalizando scraping de paginación.")
                break # Se alcanzó el límite de páginas

    except Exception as e:
        print(f"Error general durante el scraping de la categoría: {e}")
    finally:
        driver.quit()
        print(f"Finalizado scraping para la categoría: {url}")
    return products_in_category

def main():
    """
    Función principal para ejecutar el scraping de todas las categorías.
    """
    # MODIFICADO: Solo scrapeamos la categoría de "Abarrotes" para pruebas.
    urls_to_scrape = [
        "https://www.alvi.cl/category/congelados"
    ]
    
    all_scraped_products = []
    for category_url in urls_to_scrape:
        products = scrape_alvi_category(category_url)
        all_scraped_products.extend(products)
        print(f"✓ {len(products)} productos extraídos de {category_url}")

    output_file = "productos_alvi.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_scraped_products, f, indent=2, ensure_ascii=False)
    print(f"\n🎉 Scraping completo. Total productos extraídos: {len(all_scraped_products)} en '{output_file}'")

if __name__ == "__main__":
    main()
