# mae_scraper/scraper/driver_handler.py
import time
import re
import subprocess
import os
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, SessionNotCreatedException, NoSuchElementException

def get_chrome_version():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon") as key:
            version = winreg.QueryValueEx(key, "version")[0]
            return int(re.search(r"^(\d+)", version).group(1))
    except Exception:
        try:
            result = subprocess.run(["google-chrome", "--version"], capture_output=True, text=True)
            return int(re.search(r"(\d+)\.\d+\.\d+", result.stdout).group(1))
        except Exception as e:
            raise Exception(f"Não foi possível detectar a versão do Chrome. Erro: {e}")

import random

def get_random_viewport():
    """Retorna resoluções comuns de desktop"""
    viewports = [
        "1920,1080", "1366,768", "1536,864", 
        "1440,900", "1600,900", "1680,1050"
    ]
    return random.choice(viewports)

def initialize_driver(language_code):
    """Versão melhorada com mais variações para evitar detecção"""
    retry_count = 0
    max_retries = 3

    while retry_count < max_retries:
        try:
            chrome_version = get_chrome_version()
            options = uc.ChromeOptions()
            
            options.add_argument(f'--lang={language_code}')
            options.add_argument('--disable-gpu')
            
            viewport = get_random_viewport()
            options.add_argument(f'--window-size={viewport}')
            
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--exclude-switches=["enable-automation"]')
            options.add_argument('--useAutomationExtension=false')
            options.add_argument('--disable-extensions-http-throttling')
            
            prefs = {
                "profile.default_content_setting_values": {
                    "notifications": 2,
                },
                "profile.managed_default_content_settings": {
                    "images": 2
                },
                "intl.accept_languages": language_code
            }
            options.add_experimental_option("prefs", prefs)
            
            driver = uc.Chrome(version_main=chrome_version, options=options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            print(f"Driver aprimorado iniciado com idioma: {language_code} e viewport: {viewport}")
            return driver
            
        except (SessionNotCreatedException, Exception) as e:
            retry_count += 1
            print(f"Erro ao inicializar driver aprimorado: {e}")
            if retry_count < max_retries:
                time.sleep(3)
    
    print("ERRO: Falha ao inicializar driver após múltiplas tentativas.")
    return None


def login_to_amazon(driver, domain, email=None, password=None):
    """
    ⚠️ AVISO DE SEGURANÇA E COMPLIANCE ⚠️
    
    Esta função realiza login automático na Amazon, o que:
    1. Viola os Termos de Serviço da Amazon
    2. Pode resultar em bloqueio permanente da conta
    3. Expõe credenciais se não usar variáveis de ambiente
    
    USE POR SUA CONTA E RISCO.
    
    Args:
        driver: Selenium WebDriver
        domain: Domínio da Amazon (ex: amazon.com)
        email: Email de login (melhor usar variável de ambiente)
        password: Senha (melhor usar variável de ambiente)
    
    Returns:
        bool: True se login bem-sucedido, False caso contrário
    """
    
    # ✅ SEGURANÇA: Prioriza variáveis de ambiente
    if not email:
        email = os.getenv('AMAZON_EMAIL')
    if not password:
        password = os.getenv('AMAZON_PASSWORD')
    
    if not email or not password:
        print("❌ ERRO: Credenciais não fornecidas. Defina AMAZON_EMAIL e AMAZON_PASSWORD como variáveis de ambiente.")
        return False
    
    print(f"\n🔐 Iniciando login na Amazon ({domain})...")
    print("⚠️  AVISO: Login automático viola os Termos de Serviço da Amazon")
    
    wait = WebDriverWait(driver, 20)
    
    try:
        # 1. Vai para a página de login
        login_url = f"https://{domain}/ap/signin"
        driver.get(login_url)
        time.sleep(random.uniform(2, 4))
        
        # 2. Aceita cookies se aparecer
        try:
            cookie_button = driver.find_element(By.ID, "sp-cc-accept")
            cookie_button.click()
            time.sleep(1)
        except NoSuchElementException:
            pass
        
        # 3. Preenche email
        try:
            email_field = wait.until(
                EC.presence_of_element_located((By.ID, "ap_email"))
            )
            email_field.clear()
            time.sleep(random.uniform(0.5, 1.5))
            
            # Simula digitação humana
            for char in email:
                email_field.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
            
            time.sleep(random.uniform(1, 2))
            
            # Clica em continuar
            continue_button = driver.find_element(By.ID, "continue")
            continue_button.click()
            time.sleep(random.uniform(2, 3))
            
        except Exception as e:
            print(f"❌ Erro ao preencher email: {e}")
            return False
        
        # 4. Preenche senha
        try:
            password_field = wait.until(
                EC.presence_of_element_located((By.ID, "ap_password"))
            )
            password_field.clear()
            time.sleep(random.uniform(0.5, 1.5))
            
            # Simula digitação humana
            for char in password:
                password_field.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
            
            time.sleep(random.uniform(1, 2))
            
            # Clica em Sign-In
            signin_button = driver.find_element(By.ID, "signInSubmit")
            signin_button.click()
            time.sleep(random.uniform(3, 5))
            
        except Exception as e:
            print(f"❌ Erro ao preencher senha: {e}")
            return False
        
        # 5. Verifica se login foi bem-sucedido
        # Procura por elementos que indicam que está logado
        try:
            # Aguarda a página carregar completamente
            wait.until(EC.presence_of_element_located((By.ID, "nav-link-accountList")))
            
            # Verifica se não está em página de erro
            if "ap/signin" in driver.current_url or "ap_error" in driver.page_source.lower():
                print("❌ Login falhou - verifique credenciais ou possível CAPTCHA")
                return False
            
            print("✅ Login realizado com sucesso!")
            return True
            
        except TimeoutException:
            print("❌ Timeout ao verificar login - possível CAPTCHA ou erro")
            return False
        
    except Exception as e:
        print(f"❌ Erro inesperado durante login: {e}")
        return False


def _normalize_text(text):
    """
    Normaliza texto removendo espaços extras e caracteres invisíveis.
    """
    if not text:
        return ""
    normalized = re.sub(r'\s+', ' ', text.strip())
    normalized = re.sub(r'[\u200b-\u200f\u202a-\u202e\ufeff]', '', normalized)
    return normalized


def _extract_zip_from_text(text, expected_zip):
    """
    Extrai o ZIP code do texto exibido, lidando com formatação e truncamento.
    """
    normalized_text = _normalize_text(text).lower()
    expected_zip_normalized = expected_zip.lower()

    if "brazil" in normalized_text:
        return None

    expected_zip_alphanum = re.sub(r'[^a-z0-9]', '', expected_zip_normalized)
    potential_codes_in_text = re.findall(r'[a-z0-9]+', normalized_text)

    for code_part in potential_codes_in_text:
        temp_code = "".join(potential_codes_in_text[-2:])
        if expected_zip_alphanum.startswith(temp_code):
            return expected_zip

    if expected_zip in normalized_text:
        return expected_zip
    
    zip_match = re.search(r'\b\d{5}\b', normalized_text)
    if zip_match and zip_match.group() in expected_zip:
        return expected_zip
    
    return None


def validate_zip_on_page(driver, expected_zip, zip_selector="#glow-ingress-line2", timeout=5):
    """
    Valida se o ZIP correto está aplicado na página atual.
    
    Returns:
        tuple: (is_valid: bool, extracted_text: str, extracted_zip: str or None)
    """
    try:
        zip_element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, zip_selector))
        )
        
        extracted_text = _normalize_text(zip_element.text)
        
        if extracted_text.lower() == "brazil":
            print(f"⚠️  ZIP ausente detectado: texto='{extracted_text}'")
            return (False, extracted_text, None)
        
        extracted_zip = _extract_zip_from_text(extracted_text, expected_zip)
        
        if extracted_zip:
            print(f"🔍 ZIP validado: '{extracted_text}' (ZIP: {extracted_zip})")
            return (True, extracted_text, extracted_zip)
        else:
            print(f"❌ ZIP incorreto: esperado='{expected_zip}', encontrado='{extracted_text}'")
            return (False, extracted_text, None)
            
    except Exception as e:
        print(f"⚠️  Erro ao validar ZIP: {e}")
        return (False, "", None)


def _apply_zip_code_only(driver, marketplace_code, zip_code, wait):
    """
    Aplica o ZIP code (apenas o fluxo de Apply, sem Continue).
    Retorna True se conseguiu aplicar, False caso contrário.
    """
    try:
        # --- MODIFICAÇÃO 1: Clique robusto no Cookie Banner ---
        try:
            # Espera o botão de cookie ficar clicável (max 10 segundos)
            cookie_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="sp-cc-accept"]'))
            )
            
            # Tenta um clique normal primeiro
            try:
                cookie_button.click()
                print("   - (Debug) Cookie button 'sp-cc-accept' clicado via standard click.")
            except Exception:
                # Se falhar (ex: interceptado), usa clique JavaScript
                print(f"   - (Debug) Standard click falhou, tentando JS click...")
                driver.execute_script("arguments[0].click();", cookie_button)
                print(f"   - (Debug) Cookie button 'sp-cc-accept' clicado via JS.")
                
            # Espera o modal/overlay desaparecer
            time.sleep(1.5) 
            
        except (NoSuchElementException, TimeoutException):
            # Se o banner não aparecer em 10s, segue em frente
            print("   - (Debug) Cookie banner 'sp-cc-accept' não encontrado ou não clicável.")
            pass
        except Exception as e:
            print(f"   - (Debug) Erro inesperado ao clicar no cookie button: {e}")
            pass # Tenta continuar mesmo assim
        # --- FIM DA MODIFICAÇÃO 1 ---

        deliver_dropdown = wait.until(
            EC.element_to_be_clickable((By.ID, "nav-global-location-slot"))
        )
        deliver_dropdown.click()
        time.sleep(1)
        
        if marketplace_code == 'CA':
            zip_parts = zip_code.split(' ')
            if len(zip_parts) != 2:
                print(f"⚠️  Formato inválido de ZIP para CA: {zip_code}")
                return False
                
            zip_input0 = wait.until(
                EC.visibility_of_element_located((By.ID, "GLUXZipUpdateInput_0"))
            )
            zip_input0.clear()
            time.sleep(0.3)
            zip_input0.send_keys(zip_parts[0])
            
            zip_input1 = wait.until(
                EC.visibility_of_element_located((By.ID, "GLUXZipUpdateInput_1"))
            )
            zip_input1.clear()
            time.sleep(0.3)
            zip_input1.send_keys(zip_parts[1])
        else:
            zip_input = wait.until(
                EC.visibility_of_element_located((By.ID, "GLUXZipUpdateInput"))
            )
            zip_input.clear()
            time.sleep(0.3)
            zip_input.send_keys(zip_code)
        
        apply_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//span[@id='GLUXZipUpdate']/span/input"))
        )
        apply_button.click()
        print(f"✅ Apply clicado para ZIP: {zip_code}")
        
        # --- MODIFICAÇÃO 2: Pausa para recarregar ---
        # Adiciona uma pausa extra AQUI para a página recarregar pós-Apply
        # antes que a validação de moeda ocorra.
        time.sleep(2.5) 
        # --- FIM DA MODIFICAÇÃO 2 ---
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao aplicar ZIP: {e}")
        return False


def _force_currency_via_cookie(driver, marketplace_code, domain):
    """
    Define o cookie i18n-prefs para forçar a moeda correta, sobrescrevendo
    a detecção por geolocalização de IP (ex: máquina no Brasil acessando UK).
    Deve ser chamada APÓS o primeiro carregamento da página do domínio.
    """
    from .currency_validator import CURRENCY_ISO_MAP
    currency = CURRENCY_ISO_MAP.get(marketplace_code.upper())
    if not currency:
        return

    try:
        driver.add_cookie({
            "name": "i18n-prefs",
            "value": currency,
            "domain": f".{domain}",
            "path": "/",
        })
        driver.refresh()
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "twotabsearchtextbox"))
        )
        print(f"   ✅ Cookie de moeda definido: i18n-prefs={currency} em .{domain}")
    except Exception as e:
        print(f"   ⚠️  Falha ao definir cookie de moeda: {e}")


def set_delivery_location(driver, marketplace_code, domain, zip_code, login_email=None, login_password=None, validate_currency=True):
    """
    Carrega a página da Amazon, faz login (se credenciais fornecidas) e aplica o ZIP code.

    Args:
        driver: Selenium WebDriver
        marketplace_code: Código do marketplace
        domain: Domínio da Amazon
        zip_code: ZIP code para configurar
        login_email: (Opcional) Email para login
        login_password: (Opcional) Senha para login
        validate_currency: Se True, valida moeda após aplicar ZIP
    """
    print(f"\n🌐 Configurando localização para {domain}...")
    wait = WebDriverWait(driver, 15)

    # --- CARREGAR PÁGINA PRINCIPAL ---
    load_success = False
    for attempt in range(3):
        try:
            driver.get(f"https://{domain}/ref=nav_logo")
            wait.until(EC.presence_of_element_located((By.ID, "twotabsearchtextbox")))
            print(f"✅ Página da Amazon carregada (tentativa {attempt + 1})")
            load_success = True
            break
        except TimeoutException:
            print(f"⏱️  Timeout na tentativa {attempt + 1}/3")
            if attempt < 2:
                driver.refresh()
                time.sleep(3)

    if not load_success:
        print("🔄 Tentando via Google...")
        for google_attempt in range(3):
            try:
                driver.get('https://www.google.com')
                time.sleep(2)

                if "google.com/sorry/" in driver.current_url:
                    print(f"⚠️  Google bloqueou (tentativa {google_attempt + 1}/3)")
                    time.sleep(5)
                    continue

                search_box = wait.until(EC.presence_of_element_located((By.NAME, 'q')))
                search_box.send_keys(domain)
                search_box.send_keys(Keys.RETURN)

                first_result = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, f"a[href*='https://www.{domain}']"))
                )
                first_result.click()
                wait.until(EC.presence_of_element_located((By.ID, "twotabsearchtextbox")))

                print("✅ Página carregada via Google")
                load_success = True
                break

            except Exception as e:
                print(f"❌ Falha no Google (tentativa {google_attempt + 1}/3): {e}")
                if google_attempt == 2:
                    return False

    if not load_success:
        print("❌ FALHA CRÍTICA: Não foi possível carregar a Amazon")
        return False

    # --- FORÇAR MOEDA CORRETA VIA COOKIE (antes do ZIP) ---
    # Necessário quando a máquina está no Brasil: Amazon detecta IP BR e define
    # i18n-prefs=BRL por padrão. O cookie sobrescreve essa preferência.
    _force_currency_via_cookie(driver, marketplace_code, domain)

    # --- FAZER LOGIN (SE CREDENCIAIS FORNECIDAS) ---
    if login_email or os.getenv('AMAZON_EMAIL'):
        if not login_to_amazon(driver, domain, login_email, login_password):
            print("⚠️  Login falhou, mas continuando com scraping...")
            # Não retorna False - permite continuar mesmo se login falhar

    # --- APLICAR ZIP CODE ---
    if not zip_code:
        print("ℹ️  Sem ZIP code configurado para este marketplace")
        return True

    print(f"\n🔮 Aplicando ZIP code inicial: {zip_code}")

    for attempt in range(3):
        if _apply_zip_code_only(driver, marketplace_code, zip_code, wait):
            print(f"🎉 ZIP CODE INICIAL APLICADO (tentativa {attempt + 1}).")
            return True
        else:
            print(f"⚠️  Tentativa {attempt + 1}/3: Falha ao aplicar ZIP")
            time.sleep(3)

    print("❌ FALHA CRÍTICA: Não foi possível aplicar o ZIP code após 3 tentativas")
    return False


def ensure_zip_is_correct(driver, marketplace_code, expected_zip, max_retries=3):
    """
    Garante que o ZIP correto está aplicado na página atual.
    """
    is_valid, text, extracted = validate_zip_on_page(driver, expected_zip)
    
    if is_valid:
        return True
    
    print(f"🔄 ZIP incorreto na página. Reaplicando...")
    wait = WebDriverWait(driver, 15)
    
    for attempt in range(max_retries):
        if _apply_zip_code_only(driver, marketplace_code, expected_zip, wait):
            time.sleep(2)
            
            is_valid, text, extracted = validate_zip_on_page(driver, expected_zip)
            if is_valid:
                print(f"✅ ZIP reaplicado com sucesso na tentativa {attempt + 1}")
                return True
            else:
                print(f"⚠️  Tentativa {attempt + 1}/{max_retries}: ZIP ainda incorreto ('{text}')")
        
        time.sleep(2)
    
    final_valid, final_text, final_zip = validate_zip_on_page(driver, expected_zip)
    print(f"❌ ERRO CRÍTICO: ZIP permanece incorreto após {max_retries} tentativas")
    print(f"   Esperado: '{expected_zip}'")
    print(f"   Encontrado: '{final_text}'")
    
    return False