# mae_scraper/scraper/currency_validator.py
"""
Módulo para validação e correção de moeda por marketplace.
Garante que os preços estejam na moeda correta antes do scraping.
"""

import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

# IMPORTA AS FUNÇÕES NECESSÁRIAS PARA REINICIAR O DRIVER
from .driver_handler import initialize_driver, set_delivery_location


# Mapeamento de moedas esperadas por marketplace
CURRENCY_MAP = {
    'US': '$',      # USD - Dollar sign
    'GB': '£',      # GBP - Pound sign
    'DE': '€',      # EUR - Euro sign
    'FR': '€',      # EUR - Euro sign
    'IT': '€',      # EUR - Euro sign
    'ES': '€',      # EUR - Euro sign
    'CA': '$',      # CAD - Dollar sign (mesmo símbolo, mas contexto diferente)
    'MX': '$',      # MXN - Peso sign
}

# Códigos ISO por marketplace — usados para forçar moeda via cookie i18n-prefs
# 'EU' incluído porque mae_config.json usa sales_region_code="EU" para DE/FR/IT/ES
CURRENCY_ISO_MAP = {
    'US': 'USD', 'CA': 'CAD', 'GB': 'GBP',
    'DE': 'EUR', 'FR': 'EUR', 'IT': 'EUR', 'ES': 'EUR', 'MX': 'MXN',
    'EU': 'EUR',
}

# XPath para extração de moeda (ajustado para ser mais robusto)
CURRENCY_XPATH = '//span[contains(@class, "a-price-symbol")]'

# Símbolos alternativos que podem aparecer
CURRENCY_ALIASES = {
    'USD': '$',
    'CAD': '$',
    'GBP': '£',
    'EUR': '€',
    'MXN': '$',
    # Alguns marketplaces mostram o código ISO
    '$': '$',
    '£': '£',
    '€': '€',
}


def _normalize_currency(currency_text):
    """
    Normaliza o texto de moeda extraído.
    """
    if not currency_text:
        return None
    
    normalized = currency_text.strip().upper()
    
    return CURRENCY_ALIASES.get(normalized, currency_text.strip())


def get_expected_currency(marketplace_code):
    """
    Retorna a moeda esperada para um marketplace.
    """
    return CURRENCY_MAP.get(marketplace_code.upper())


def extract_currency_from_page(driver, timeout=5):
    """
    Extrai o símbolo de moeda da página atual.
    """
    try:
        currency_elements = WebDriverWait(driver, timeout).until(
            EC.presence_of_all_elements_located((By.XPATH, CURRENCY_XPATH))
        )
        
        if currency_elements:
            currency_text = currency_elements[0].text.strip()
            normalized = _normalize_currency(currency_text)
            
            print(f"💱 Moeda detectada: '{currency_text}' (normalizado: '{normalized}')")
            return normalized
        else:
            print(f"⚠️  Elementos de moeda encontrados, mas vazios")
            return None
        
    except (TimeoutException, NoSuchElementException):
        print(f"⚠️  Não foi possível extrair moeda (elemento não encontrado)")
        return None
    except Exception as e:
        print(f"⚠️  Erro ao extrair moeda: {e}")
        return None

# --- NOVA FUNÇÃO HELPER ---
def _is_price_present(driver, timeout=3):
    """
    Verifica rapidamente se um elemento de preço (whole) está visível.
    """
    try:
        # Usamos o seletor CSS padrão para o preço
        price_element_css = "span.a-price-whole"
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, price_element_css))
        )
        print("   - (Info) Verificação de preço: Preço ENCONTRADO.")
        return True
    except (TimeoutException, NoSuchElementException):
        print("   - (Info) Verificação de preço: Preço NÃO encontrado.")
        return False
    except Exception:
        # Lida com casos onde o driver pode estar fechado ou a página quebrada
        print("   - (Info) Verificação de preço: Erro ao checar preço.")
        return False # Assume que não está presente se a verificação falhar

# --- LÓGICA ATUALIZADA AQUI ---
def validate_currency(driver, marketplace_code, timeout=5):
    """
    Valida se a moeda da página está correta para o marketplace.
    MODIFICADO: Se a moeda for None, só retorna False (erro) se um preço for encontrado.
    """
    expected = get_expected_currency(marketplace_code)
    
    if not expected:
        print(f"⚠️  Marketplace '{marketplace_code}' não tem moeda mapeada")
        return (True, None, None)
    
    found = extract_currency_from_page(driver, timeout)
    
    # Cenário 1: Moeda foi encontrada (BRL, €, $, £)
    if found is not None:
        is_valid = (found == expected)
        if is_valid:
            print(f"✅ Moeda correta: {found} = {expected}")
        else:
            print(f"❌ Moeda incorreta: esperado '{expected}', encontrado '{found}'")
        return (is_valid, expected, found)
        
    # Cenário 2: Moeda NÃO foi encontrada (found is None)
    else:
        print("   - (Info) Moeda não encontrada (None). Verificando se o preço existe...")
        price_present = _is_price_present(driver)
        
        # Condição de Erro (Sua regra): Moeda=None E Preço=Sim
        if price_present:
            print(f"❌ Moeda incorreta: esperado '{expected}', encontrado 'None' (mas preço existe!)")
            return (False, expected, None) # É um erro, precisa corrigir
        
        # Condição Válida: Moeda=None E Preço=Não
        else:
            print(f"✅ Moeda 'None' (Válido): Produto provavelmente indisponível (sem preço).")
            return (True, expected, None) # Não é um erro, pode prosseguir


def validate_currency_on_product_page(driver, marketplace_code, asin, zip_code, reapply_zip_function, marketplace_config, url):
    """
    Wrapper conveniente para validar moeda em uma página de produto.
    
    Args:
        ...
        marketplace_config: Objeto de configuração
        url: A URL do produto
    
    Returns:
        tuple: (new_driver, is_correct: bool)
    """
    print(f"\n💱 Validando moeda para ASIN {asin} ({marketplace_code})...")
    
    new_driver, is_correct = ensure_correct_currency(
        driver, 
        marketplace_code, 
        zip_code, 
        reapply_zip_function,
        marketplace_config,
        url,
        max_retries=2
    )
    
    if not is_correct:
        print(f"⚠️  AVISO: Moeda permanece incorreta para ASIN {asin}")
        print(f"   Os preços podem estar em moeda errada!")
    
    return (new_driver, is_correct)


def change_amazon_country(driver, marketplace_code, domain, marketplace_config):
    """
    Muda o país/região na Amazon REINICIANDO A SESSÃO.
    """
    import time
    from selenium.webdriver.common.by import By
    # from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    
    print(f"\n🌍 Moeda incorreta. Reiniciando sessão do driver para {marketplace_code}...")
    
    language_code = marketplace_config.get('language_code', 'en-US')
    zip_code = marketplace_config.get('zip_code')

    try:
        driver.quit()
    except Exception as e:
        print(f"   ⚠️  Aviso: Erro ao fechar driver antigo: {e}")
        
    new_driver = initialize_driver(language_code)
    if not new_driver:
        print("   ❌ ERRO CRÍTICO: Falha ao reiniciar o driver.")
        return (None, False)
        
    region_code = marketplace_config.get('sales_region_code', marketplace_code)
    
    success = set_delivery_location(
        new_driver, 
        region_code,
        domain, 
        zip_code
    )
    
    if not success:
        print("   ❌ ERRO CRÍTICO: Falha ao configurar localização no novo driver.")
        new_driver.quit()
        return (None, False)
        
    print("   ✅ Novo driver iniciado e configurado.")
    return (new_driver, True)


def ensure_correct_currency(driver, marketplace_code, zip_code, reapply_zip_function, marketplace_config, url, max_retries=3):
    """
    Garante que a moeda está correta, tentando múltiplas estratégias.
    
    Args:
        ...
        marketplace_config: Objeto de configuração
        url: URL do produto
    
    Returns:
        tuple: (driver, is_valid: bool)
    """
    import time
    from .driver_handler import ensure_zip_is_correct # Import local
    
    # Primeira validação (na página do ASIN)
    # A nova lógica está dentro de validate_currency
    is_valid, expected, found = validate_currency(driver, marketplace_code)
    
    if is_valid:
        return (driver, True)
    
    print(f"\n🔄 Moeda incorreta detectada (Esperado: {expected}, Encontrado: {found}). Tentando corrigir...")
    
    current_url = driver.current_url
    domain = current_url.split('/')[2] if '/' in current_url else 'amazon.com'
    
    current_driver = driver 
    
    for attempt in range(max_retries):
        print(f"\n   {'─'*60}")
        print(f"   Tentativa {attempt + 1}/{max_retries}")
        
        # Estratégia 1: REINICIAR DRIVER
        if attempt == 0:
            print(f"   Estratégia 1: Reiniciando sessão do driver...")
            new_driver, success = change_amazon_country(current_driver, marketplace_code, domain, marketplace_config)
            
            if success:
                current_driver = new_driver 
                print(f"   Navengando de volta para a URL do ASIN: {url}")
                current_driver.get(url) 
                time.sleep(2.5) 
                
                print(f"   Re-validando ZIP na página do ASIN...")
                if not ensure_zip_is_correct(current_driver, marketplace_code, zip_code):
                     print(f"   ⚠️  Falha ao re-validar o ZIP na página do ASIN após reiniciar.")
            else:
                print("   ⚠️  Falha na Estratégia 1 (Reiniciar Driver)")
                return (current_driver, False) 
        
        # Estratégia 2: Reaplicar ZIP (no driver atual)
        elif attempt == 1:
            print(f"   Estratégia 2: Reaplicando ZIP code (na página atual)...")
            try:
                # from selenium.webdriver.support.ui import WebDriverWait
                wait = WebDriverWait(current_driver, 15)
                success = reapply_zip_function(current_driver, marketplace_code, zip_code, wait)
                if success:
                    time.sleep(3) 
            except Exception as e:
                print(f"   ⚠️  Erro ao reaplicar ZIP: {e}")
                success = False
        
        # Estratégia 3: Recarregar
        else:
            print(f"   Estratégia {attempt + 1}: Recarregando a página...")
            try:
                current_driver.refresh()
                time.sleep(3)
            except Exception as e:
                 print(f"   ⚠️  Erro ao recarregar: {e}")

        # Revalida
        is_valid, expected, found = validate_currency(current_driver, marketplace_code)
        
        if is_valid:
            print(f"\n   ✅ Moeda corrigida com sucesso na tentativa {attempt + 1}!")
            return (current_driver, True)
        else:
            print(f"   ⚠️  Moeda ainda incorreta: esperado '{expected}', encontrado '{found}'")
        
        time.sleep(2)
    
    print(f"\n❌ FALHA: Não foi possível corrigir a moeda após {max_retries} tentativas")
    print(f"   Marketplace: {marketplace_code}")
    print(f"   Esperado: {expected}")
    print(f"   Encontrado: {found}")
    
    return (current_driver, False)


def test_currency_detection(driver, marketplace_code):
    """
    Função de teste para verificar detecção de moeda.
    """
    print(f"\n{'='*60}")
    print(f"🧪 TESTE DE DETECÇÃO DE MOEDA - {marketplace_code}")
    print(f"{'='*60}\n")
    
    expected = get_expected_currency(marketplace_code)
    print(f"Moeda esperada para {marketplace_code}: {expected}")
    
    found = extract_currency_from_page(driver)
    print(f"Moeda encontrada na página: {found}")
    
    is_valid, exp, fnd = validate_currency(driver, marketplace_code)
    print(f"\nValidação: {'✅ PASSOU' if is_valid else '❌ FALHOU'}")
    print(f"   Esperado: {exp}")
    print(f"   Encontrado: {fnd}")
    print(f"\n{'='*60}\n")
    
    return is_valid