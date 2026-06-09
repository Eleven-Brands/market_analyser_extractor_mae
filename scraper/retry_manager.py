# mae_scraper/retry_manager.py
import time
from enum import Enum

class RetryStrategy(Enum):
    """Estratégias de retry com abordagens diferentes"""
    IMMEDIATE = 1          # Tenta novamente imediatamente
    DELAYED = 2            # Aguarda tempo maior antes de tentar
    NEW_SESSION = 3        # Cria nova sessão do driver
    SKIP = 4               # Pula o ASIN

class RetryableASIN:
    """Representa um ASIN que falhou e pode ser retentado"""
    def __init__(self, asin, reason, retry_count=0, max_retries=3):
        self.asin = asin
        self.reason = reason  # "zip_error", "scraping_error", "network_error"
        self.retry_count = retry_count
        self.max_retries = max_retries
        self.last_error = None
    
    def can_retry(self):
        """Verifica se ainda há tentativas disponíveis"""
        return self.retry_count < self.max_retries
    
    def increment_retry(self, error_msg):
        """Incrementa contador e registra erro"""
        self.retry_count += 1
        self.last_error = error_msg
    
    def __repr__(self):
        return f"RetryableASIN({self.asin}, tentativas={self.retry_count}/{self.max_retries}, motivo={self.reason})"


class RetryManager:
    """Gerencia ASINs que falharam e coordena estratégias de retry"""
    
    def __init__(self):
        self.failed_asins = {}  # {asin: RetryableASIN}
        self.successful_asins = []
        self.permanently_failed = []
    
    def add_failed_asin(self, asin, reason="scraping_error", max_retries=3):
        """Adiciona ASIN que falhou para retry posterior"""
        if asin not in self.failed_asins:
            self.failed_asins[asin] = RetryableASIN(asin, reason, max_retries=max_retries)
            print(f"📌 ASIN {asin} marcado para retry ({reason})")
        else:
            self.failed_asins[asin].increment_retry(reason)
    
    def mark_successful(self, asin):
        """Remove ASIN da lista de falhas se estava lá"""
        if asin in self.failed_asins:
            del self.failed_asins[asin]
        if asin not in self.successful_asins:
            self.successful_asins.append(asin)
    
    def get_retryable_asins(self):
        """Retorna lista de ASINs que ainda podem ser retentados"""
        retryable = [
            asin_obj for asin_obj in self.failed_asins.values() 
            if asin_obj.can_retry()
        ]
        return retryable
    
    def finalize_failures(self):
        """Move ASINs que esgotaram tentativas para lista permanente"""
        for asin, asin_obj in self.failed_asins.items():
            if not asin_obj.can_retry():
                self.permanently_failed.append({
                    'asin': asin,
                    'reason': asin_obj.reason,
                    'attempts': asin_obj.retry_count,
                    'last_error': asin_obj.last_error
                })
        
        # Remove da lista de falhas
        self.failed_asins = {
            asin: obj for asin, obj in self.failed_asins.items() 
            if obj.can_retry()
        }
    
    def get_strategy_for_asin(self, asin_obj):
        """Define estratégia de retry baseada no tipo de erro"""
        if asin_obj.reason == "zip_error":
            if asin_obj.retry_count == 0:
                return RetryStrategy.DELAYED  # Primeira falha: espera e tenta
            elif asin_obj.retry_count == 1:
                return RetryStrategy.NEW_SESSION  # Segunda falha: nova sessão
            else:
                return RetryStrategy.SKIP  # Terceira+ falha: desiste
        
        elif asin_obj.reason == "network_error":
            if asin_obj.retry_count < 2:
                return RetryStrategy.DELAYED  # Rede: tenta com espera
            else:
                return RetryStrategy.SKIP
        
        else:  # scraping_error
            if asin_obj.retry_count < 1:
                return RetryStrategy.IMMEDIATE  # Tenta novamente rápido
            else:
                return RetryStrategy.NEW_SESSION
    
    def print_summary(self):
        """Imprime resumo das tentativas de retry"""
        print("\n" + "="*70)
        print("📊 RESUMO DE RETRY")
        print("="*70)
        
        if self.successful_asins:
            print(f"✅ Recuperados: {len(self.successful_asins)} ASINs")
            if len(self.successful_asins) <= 10:
                print(f"   {', '.join(self.successful_asins[:10])}")
        
        if self.permanently_failed:
            print(f"\n❌ Falhas Permanentes: {len(self.permanently_failed)} ASINs")
            for item in self.permanently_failed[:5]:  # Mostra apenas primeiros 5
                print(f"   - {item['asin']}: {item['reason']} (tentativas: {item['attempts']})")
            if len(self.permanently_failed) > 5:
                print(f"   ... e mais {len(self.permanently_failed) - 5}")
        
        still_retrying = len(self.get_retryable_asins())
        if still_retrying > 0:
            print(f"\n⏳ Ainda com possibilidade de retry: {still_retrying} ASINs")
        
        print("="*70 + "\n")