# mae_scraper/session_manager.py - COM VERIFICAÇÕES ALEATÓRIAS
import time
import random
from datetime import datetime, timedelta
from .driver_handler import initialize_driver, set_delivery_location

class SessionManager:
    def __init__(self, max_products_per_session=50, min_session_break=10, max_session_break=30, 
                 login_email=None, login_password=None, random_check_probability=0.15):
        """
        NOVO: random_check_probability - Probabilidade de fazer verificação aleatória (padrão: 15%)
        
        max_products_per_session: Máximo de produtos por sessão
        min_session_break: Tempo mínimo entre sessões em segundos
        max_session_break: Tempo máximo entre sessões em segundos
        login_email: (Opcional) Email para login na Amazon
        login_password: (Opcional) Senha para login na Amazon
        random_check_probability: Chance de verificar ZIP/moeda aleatoriamente (0.0 a 1.0)
        """
        self.driver = None
        self.product_count = 0
        self.session_start_time = None
        self.max_products = max_products_per_session
        self.min_break = min_session_break
        self.max_break = max_session_break
        self.total_sessions = 0
        
        self.login_email = login_email
        self.login_password = login_password
        
        # NOVO: Configuração de verificações aleatórias
        self.random_check_probability = random_check_probability
        
        # Cache de validações para a sessão
        self._zip_validated_this_session = False
        self._currency_validated_this_session = False
        
        # NOVO: Contadores para estatísticas
        self._random_checks_performed = 0
        self._random_checks_failed = 0
        
    def needs_new_session(self):
        """Verifica se precisa iniciar nova sessão"""
        if not self.driver:
            return True
            
        if self.product_count >= self.max_products:
            return True
            
        if self.session_start_time:
            session_duration = datetime.now() - self.session_start_time
            if session_duration > timedelta(minutes=60):
                return True
                
        return False
    
    def _should_perform_random_check(self):
        """
        Decide se deve fazer uma verificação aleatória neste produto.
        
        Lógica:
        - Sempre retorna False no primeiro produto (já valida obrigatoriamente)
        - 15% de chance de validar nos demais produtos
        - Aumenta probabilidade nos últimos 10 produtos da sessão (30%)
        
        Returns:
            bool: True se deve validar, False caso contrário
        """
        # Nunca valida no primeiro produto (já é validado obrigatoriamente)
        if self.product_count == 0:
            return False
        
        # Aumenta probabilidade nos últimos 10 produtos da sessão
        remaining = self.max_products - self.product_count
        if remaining <= 10:
            increased_probability = self.random_check_probability * 2  # Dobra a chance
            return random.random() < increased_probability
        
        # Probabilidade normal
        return random.random() < self.random_check_probability
    
    def start_new_session(self, language_code, marketplace_config):
        """Inicia uma nova sessão com pausa natural"""
        
        if self.driver:
            print(f"\n🔄 Finalizando sessão #{self.total_sessions} após {self.product_count} produtos...")
            
            # NOVO: Exibe estatísticas de verificações aleatórias
            if self._random_checks_performed > 0:
                success_rate = ((self._random_checks_performed - self._random_checks_failed) / 
                               self._random_checks_performed * 100)
                print(f"   📊 Verificações aleatórias: {self._random_checks_performed} "
                      f"(Sucesso: {success_rate:.1f}%)")
            
            self.close_session()
            
            break_time = random.uniform(self.min_break * 0.7, self.max_break * 0.7)
            print(f"⏱️  Pausa entre sessões: {break_time:.1f}s")
            time.sleep(break_time)
        
        self.total_sessions += 1
        print(f"\n🚀 Iniciando sessão #{self.total_sessions}...")
        
        self.driver = initialize_driver(language_code)
        if not self.driver:
            print("❌ Falha ao inicializar driver")
            return False
            
        success = set_delivery_location(
            self.driver, 
            marketplace_config.get('sales_region_code', marketplace_config.get('name', 'Unknown')),
            marketplace_config['domain'], 
            marketplace_config.get('zip_code'),
            login_email=self.login_email,
            login_password=self.login_password
        )
        
        if not success:
            print("❌ Falha ao configurar localização")
            self.close_session()
            return False
            
        self.product_count = 0
        self.session_start_time = datetime.now()
        
        # Marca validações como feitas na inicialização
        self._zip_validated_this_session = True
        self._currency_validated_this_session = True
        
        # Reset dos contadores de verificações aleatórias
        self._random_checks_performed = 0
        self._random_checks_failed = 0
        
        print(f"✅ Sessão #{self.total_sessions} pronta! Limite: {self.max_products} produtos")
        print(f"   🎲 Verificações aleatórias: {int(self.random_check_probability * 100)}% de chance por produto")
        print("")
        return True
    
    def scrape_product(self, scrape_function, url, asin, marketplace_code, xpaths, replacements, 
                      bsr_search_text, expected_zip=None, marketplace_config=None):
        """
        Wrapper para scraping com verificações aleatórias de ZIP/moeda.
        """
        if self.needs_new_session():
            print("⚠️  Sessão expirada - será renovada no próximo lote")
            return None
            
        self._human_delay()
        
        try:
            # LÓGICA DE VALIDAÇÃO MELHORADA
            # Primeiro produto: SEMPRE valida
            # Demais produtos: Valida aleatoriamente
            is_first_product = (self.product_count == 0)
            should_random_check = self._should_perform_random_check()
            
            # Decide se valida ZIP
            validate_zip_this_time = is_first_product or should_random_check
            
            # Decide se valida moeda
            validate_currency_this_time = is_first_product or should_random_check
            
            # Log de verificação aleatória (apenas se não for o primeiro)
            if should_random_check and not is_first_product:
                self._random_checks_performed += 1
                print(f"   🎲 Verificação aleatória #{self._random_checks_performed} "
                      f"(ASIN: {asin}, Produto #{self.product_count + 1})")
            
            new_driver, result = scrape_function(
                self.driver, 
                url, 
                asin, 
                marketplace_code, 
                xpaths, 
                replacements, 
                bsr_search_text,
                expected_zip=expected_zip if validate_zip_this_time else None,
                marketplace_config=marketplace_config,
                validate_currency=validate_currency_this_time
            )
            
            # Se o driver mudou, significa que houve reinicialização (problema detectado)
            if new_driver != self.driver:
                print(f"   🔄 SessionManager: Driver reiniciado (problema detectado)")
                self.driver = new_driver
                
                # Reset das flags de validação
                self._zip_validated_this_session = False
                self._currency_validated_this_session = False
                
                # NOVO: Contabiliza falha na verificação aleatória
                if should_random_check and not is_first_product:
                    self._random_checks_failed += 1
                    print(f"   ⚠️  Verificação aleatória detectou problema!")
            
            self.product_count += 1
            
            # Log de progresso apenas a cada 10 produtos
            if self.product_count % 10 == 0 or self.product_count == 1:
                remaining = self.max_products - self.product_count
                print(f"📊 Sessão #{self.total_sessions}: {self.product_count}/{self.max_products} "
                      f"produtos ({remaining} restantes)")
            
            return result
            
        except Exception as e:
            print(f"❌ Erro no scraping do produto {asin}: {e}")
            raise e
    
    def _human_delay(self):
        """
        Delay humano otimizado com variação.
        """
        base_delay = random.uniform(0.4, 0.8)
        
        # Ocasionalmente delay maior (10% das vezes)
        if random.random() < 0.10:
            base_delay += random.uniform(0.5, 1.5)
            
        time.sleep(base_delay)
    
    def get_session_stats(self):
        """Retorna estatísticas da sessão atual (com dados de verificações aleatórias)"""
        if not self.session_start_time:
            return "Nenhuma sessão ativa"
            
        duration = datetime.now() - self.session_start_time
        
        # Calcula taxa de sucesso das verificações aleatórias
        random_check_success_rate = None
        if self._random_checks_performed > 0:
            random_check_success_rate = ((self._random_checks_performed - self._random_checks_failed) / 
                                         self._random_checks_performed * 100)
        
        return {
            'session_number': self.total_sessions,
            'products_scraped': self.product_count,
            'products_remaining': self.max_products - self.product_count,
            'session_duration': str(duration).split('.')[0],
            'driver_active': self.driver is not None,
            'random_checks_performed': self._random_checks_performed,
            'random_checks_failed': self._random_checks_failed,
            'random_check_success_rate': random_check_success_rate
        }
    
    def close_session(self):
        """Encerra sessão atual"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                print(f"⚠️  Aviso: Erro ao fechar driver: {e}")
            finally:
                self.driver = None
                self._zip_validated_this_session = False
                self._currency_validated_this_session = False
                
    def __del__(self):
        """Cleanup automático"""
        self.close_session()