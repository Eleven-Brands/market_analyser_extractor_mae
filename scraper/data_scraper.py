# mae_scraper/data_scraper.py
import datetime
import re
import json
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

from .driver_handler import ensure_zip_is_correct

# <<< 1. ADICIONADO marketplace_config=None
def scrape_single_product(driver, url, asin, marketplace_code, xpaths, replacements, bsr_search_text, expected_zip=None, validate_currency=True, marketplace_config=None):
    """Extrai todos os dados de uma página de produto usando lógicas flexíveis e configuráveis."""

    driver.get(url)

    # Validação de ZIP
    if expected_zip:
        if not ensure_zip_is_correct(driver, marketplace_code, expected_zip):
            print(f"⚠️  ZIP incorreto para ASIN {asin}, mesmo após tentativas de correção. Os dados podem ser imprecisos.")

    # ✨ NOVA VALIDAÇÃO DE MOEDA
    # <<< 2. ADICIONADO check marketplace_config
    if validate_currency and expected_zip and marketplace_config:
        try:
            from .currency_validator import validate_currency_on_product_page
            from .driver_handler import _apply_zip_code_only
            # from selenium.webdriver.support.ui import WebDriverWait

            wait = WebDriverWait(driver, 15)

            # <<< 3. CAPTURA new_driver e currency_ok
            new_driver, currency_ok = validate_currency_on_product_page(
                driver,
                marketplace_code,
                asin,
                expected_zip,
                lambda d, mc, zc, w: _apply_zip_code_only(d, mc, zc, w),
                marketplace_config, # <<< 4. PASSA marketplace_config
                url # <<< 5. PASSA url
            )

            # <<< 6. ATUALIZA o driver local se ele foi reiniciado
            if new_driver != driver:
                print(f"   🔄 (Scraper) Driver foi reiniciado (ASIN {asin}). Atualizando referência local.")
                driver = new_driver

            if not currency_ok:
                print(f"⚠️  ATENÇÃO: ASIN {asin} pode ter preço em moeda incorreta!")

        except ImportError:
            pass  # Módulo não disponível, pula validação
        except Exception as e:
            print(f"⚠️  Erro na validação de moeda para ASIN {asin}: {e}")

    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    data = {}
    data['Date'] = datetime.date.today().strftime("%m/%d/%Y")
    data['ASIN'] = asin
    data['Link'] = url
    data['Country'] = marketplace_code

    # --- FUNÇÃO AUXILIAR COM LÓGICA DE FALLBACK ---
    BY_MAP = {
        'ID': By.ID
        , 'XPATH': By.XPATH
        , 'CSS_SELECTOR': By.CSS_SELECTOR
        , 'CLASS_NAME': By.CLASS_NAME
        , 'NAME': By.NAME
    }

    def find_with_fallback(config, get_attribute=None, parent=driver):
        """
        Tenta encontrar um elemento usando uma lista de seletores alternativos.
        Para ao encontrar o primeiro que funcione.
        """
        selectors = config if isinstance(config, list) else [config]
        for selector_obj in selectors:
            try:
                by = BY_MAP[selector_obj['by']]
                value = selector_obj['value']
                element = parent.find_element(by, value)

                if get_attribute:
                    return element.get_attribute(get_attribute).strip()
                return element.text.strip()
            except:
                continue
        return 'Not Found'

    # --- EXTRAÇÃO DE DADOS ---

    data['Color Name'] = find_with_fallback(xpaths['color_name'])
    data['Size Name'] = find_with_fallback(xpaths['size_name'])

    brand_text = find_with_fallback(xpaths['brand'])
    if brand_text != 'Not Found' and replacements:
        brand_text = brand_text.replace(replacements.get('brand_prefix', ''), '').replace(replacements.get('brand_suffix', ''), '')
    data['Brand'] = brand_text

    data['Name'] = find_with_fallback(xpaths['product_title'])
    data['Stock'] = find_with_fallback(xpaths['stock']).replace('\n', ' ').replace('\r', '')
    data['Merchant'] = find_with_fallback(xpaths['merchant'])
    data['Product Category'] = find_with_fallback(xpaths['product_category']).replace('\n', '')
    data['Product Category GL'] = find_with_fallback(xpaths['product_category_gl'], get_attribute='value').replace('gl_', '')

    # =====================================================================
    # FIX: Extração do ASIN da página via URL (mais confiável que HTML)
    # O seletor HTML dependia de `id='prodDetails'`, que a Amazon removeu
    # em muitas páginas. A URL sempre contém o ASIN real após redirect.
    # =====================================================================
    asin_from_url = None
    try:
        current_url = driver.current_url
        url_match = re.search(r'/dp/([A-Z0-9]{10})', current_url)
        if url_match:
            asin_from_url = url_match.group(1)
    except Exception:
        pass

    if asin_from_url:
        data['ASIN Product Page'] = asin_from_url
    else:
        # Fallback para seletores HTML (caso URL não tenha o padrão /dp/ASIN)
        data['ASIN Product Page'] = find_with_fallback(xpaths['asin_product_page'])
    # =====================================================================

    data['Date Created'] = find_with_fallback(xpaths['date_created'])
    data['Number of ratings'] = find_with_fallback(xpaths['number_of_ratings'], get_attribute='innerHTML')
    data['List Price'] = find_with_fallback(xpaths['list_price'])
    data['Limited Time Deal'] = find_with_fallback(xpaths['limited_time_deal'])
    data['Prime'] = find_with_fallback(xpaths['prime_day_deal'])
    data['Prev Month Qty'] = find_with_fallback(xpaths['prev_month_qty'])
    data['Frequently Returned'] = find_with_fallback(xpaths['freq_returned_badge'])
    data['Coupon'] = find_with_fallback(xpaths['coupon'])
    data['Deal'] = find_with_fallback(xpaths['deal'])
    data['PED'] = find_with_fallback(xpaths['ped'])
    data['BSR 1'] = 'Not Found'
    data['BSR 2'] = 'Not Found'
    data['BSR 3'] = 'Not Found'
    data['Product Type'] = 'Not Found'
    data['DOW'] = 'Not Found'
    data['Product Category Nodes'] = 'Not Found'

    # ✨ NOVO CAMPO: Freq Badge
    data['Freq Badge'] = 'Not Found'
    try:
        freq_badge_element = driver.find_element(By.XPATH, '//*[@id="NEW_1_nostos_badge"]')
        data['Freq Badge'] = freq_badge_element.text.strip() if freq_badge_element.text else 'Not Found'
    except NoSuchElementException:
        pass
    except Exception as e:
        print(f"Debug (Freq Badge): Erro ao extrair para ASIN {asin}: {e}")

    rating_text = find_with_fallback(xpaths['rating_stars'], get_attribute='innerHTML')
    rating_text_cleaned = rating_text.replace(',', '.')
    match = re.search(r'\d+\.?\d*', rating_text_cleaned)
    data['Rating Stars'] = match.group() if match else 'Not Found'

    try:
        container = driver.find_element(BY_MAP[xpaths['price_container']['by']], xpaths['price_container']['value'])
        whole = container.find_element(BY_MAP[xpaths['price_whole']['by']], xpaths['price_whole']['value']).text
        fraction = container.find_element(BY_MAP[xpaths['price_fraction']['by']], xpaths['price_fraction']['value']).text
        data['Price'] = f"{whole}.{fraction}".replace(",", "")
    except:
        data['Price'] = 'Not Found'

    try:
        feature_elements = driver.find_elements(BY_MAP[xpaths['features']['by']], xpaths['features']['value'])
        feature_list = []
        for elem in feature_elements:
            text = elem.text.strip()
            if text:
                clean_text = text.replace('\n', ' ').replace('\r', '').replace('\t', ' ')
                clean_text = ' '.join(clean_text.split())
                clean_text = clean_text.replace('"', "'")
                feature_list.append(clean_text)

        data['Features'] = " | ".join(feature_list).replace('–', '-') if feature_list else 'Not Found'
    except:
        data['Features'] = 'Not Found'

    # ✨ LÓGICA ATUALIZADA DO BADGE - AGORA BUSCA APENAS XPATH ESPECÍFICO
    data['Badge'] = 'Not Found'
    try:
        badge_element = driver.find_element(
            By.XPATH,
            "//span[contains(@class, 'mvt') and contains(@class, 'badge')]"
        )
        badge_text = badge_element.text.strip()
        if badge_text:
            data['Badge'] = badge_text
    except NoSuchElementException:
        pass
    except Exception as e:
        print(f"Debug (Badge): Erro ao extrair para ASIN {asin}: {e}")

    try:
        # 1. Encontra o container principal que guarda as informações de BSR
        container_config = xpaths['bsr_container']
        container = driver.find_element(BY_MAP[container_config['by']], container_config['value'])

        # 2. Encontra todas as linhas da tabela dentro do container
        table_rows = container.find_elements(By.TAG_NAME, 'tr')

        # 3. Itera nas linhas para encontrar a que contém o texto de BSR
        for row in table_rows:
            header_element = row.find_element(By.TAG_NAME, 'th')
            if bsr_search_text in header_element.text:
                # 4. Encontrou a linha correta, agora pega os valores
                value_element = row.find_element(By.TAG_NAME, 'td')
                bsr_values = value_element.text.split('\n')

                # 5. Atribui para as colunas BSR 1 e BSR 2
                if len(bsr_values) > 0:
                    data['BSR 1'] = bsr_values[0].strip()
                if len(bsr_values) > 1:
                    data['BSR 2'] = bsr_values[1].strip()
                if len(bsr_values) > 2:
                    data['BSR 3'] = bsr_values[2].strip()

                # 6. Para o loop, pois já encontrou o que precisava
                break
    except Exception:
        pass

    try:
        # 1. Pega o HTML da página e parseia com BeautifulSoup
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        # 2. Busca o script que contém "immutableParams"
        scripts = soup.find_all("script")
        target_script = None
        for script in scripts:
            if script.string and "immutableParams" in script.string:
                target_script = script.string
                break

        if target_script:
            # 3. Isola o JSON bruto com Expressão Regular (Regex)
            json_match = re.search(r'("immutableParams"\s*:\s*{.*?})', target_script, re.DOTALL)
            if json_match:
                json_fragment = "{" + json_match.group(1) + "}"

                # 4. Converte em dicionário Python e extrai os dados
                json_data = json.loads(json_fragment)
                immutable = json_data.get("immutableParams", {})

                data['Product Type'] = immutable.get("ptd", 'Not Found')
                data['DOW'] = immutable.get("pgid", 'Not Found')
    except Exception as e:
        print(f"Debug (ptd/pgid): Erro ao parsear script para ASIN {asin}: {e}")
        pass

    try:
        # 1. Encontra todos os elementos de link dentro do breadcrumb
        link_elements_config = xpaths['product_category_links']
        links = driver.find_elements(BY_MAP[link_elements_config['by']], link_elements_config['value'])

        node_ids = []
        # 2. Itera em cada link para extrair o node
        for link in links:
            href = link.get_attribute('href')
            if href:
                # 3. Usa Regex para encontrar 'node=' seguido de números
                match = re.search(r'node=(\d+)', href)
                if match:
                    node_ids.append(match.group(1))

        # 4. Junta os nodes encontrados com o separador '›'
        if node_ids:
            data['Product Category Nodes'] = '›'.join(node_ids)

    except Exception as e:
        print(f"Debug (Nodes): Erro ao extrair nodes de categoria para ASIN {asin}: {e}")
        pass

    # <<< 7. RETORNA (driver, data)
    return (driver, data)

def scrape_keyword_page(page_source, keyword, marketplace_config):
    """
    Realiza o parser do HTML de uma página de resultados com BeautifulSoup,
    com tratamento de erros robusto.
    """
    results = []
    soup = BeautifulSoup(page_source, 'html.parser')

    products = soup.find_all("div", {"data-component-type": "s-search-result"})
    print(f"   - Encontrados {len(products)} produtos na página.")

    current_date = datetime.date.today().strftime('%Y-%m-%d')
    country_code = marketplace_config.get('sales_region_code', 'N/A')
    search_texts = marketplace_config.get('search_texts', {})
    sponsored_text = search_texts.get('sponsored_text', 'Sponsored')
    bought_text = search_texts.get('bought_text', 'bought in past month')
    coupon_suffix = search_texts.get('coupon_suffix_text', 'with coupon')
    kw_xpaths = marketplace_config.get('kw_xpaths', {})

    for rank, item in enumerate(products, start=1):
        asin = item.get("data-asin", "").strip()
        if not asin: continue

        title = item.find("h2").get_text(strip=True) if item.find("h2") else "Not Found"
        is_sponsored = item.find("span", string=lambda t: t and sponsored_text in t) is not None

        price_element = item.select_one("span.a-price > span.a-offscreen")
        price = price_element.get_text(strip=True) if price_element else "Not Found"

        reviews_element = item.select_one("span.a-size-base.s-underline-text")
        num_reviews = reviews_element.get_text(strip=True) if reviews_element else "Not Found"

        bought_element = item.find("span", string=lambda t: t and bought_text in t)
        bought_past_month = bought_element.get_text(strip=True) if bought_element else "Not Found"

        badge_text = "Not Found"

        try:
            top_badge_element = item.select_one(kw_xpaths.get('top_badge', {}).get('value'))
            if top_badge_element:
                badge_text = top_badge_element.get_text(strip=True)
            else:
                deal_badge_element = item.select_one(kw_xpaths.get('deal_badge', {}).get('value'))
                if deal_badge_element:
                    badge_text = deal_badge_element.get_text(strip=True)
                else:
                    save_deal_element = item.select_one(kw_xpaths.get('save_deal_badge', {}).get('value'))
                    if save_deal_element:
                        full_text = save_deal_element.get_text(strip=True)
                        if isinstance(full_text, str) and coupon_suffix in full_text:
                            badge_text = full_text.split(coupon_suffix)[0].strip()
                    else:
                        coupon_badge_element = item.select_one(kw_xpaths.get('coupon_badge', {}).get('value'))
                        if coupon_badge_element:
                            full_text = coupon_badge_element.get_text(strip=True)
                            if isinstance(full_text, str) and coupon_suffix in full_text:
                                badge_text = full_text.split(coupon_suffix)[0].strip()
        except Exception:
            badge_text = "Not Found"

        results.append({
            "Date": current_date,
            "Country": country_code,
            "Keyword": keyword,
            "Rank": rank,
            "ASIN": asin,
            "Title": title,
            "Sponsored": "Yes" if is_sponsored else "No",
            "Price": price,
            "Num Reviews": num_reviews,
            "Bought Past Month": bought_past_month,
            "Deal": badge_text
        })

    return results
