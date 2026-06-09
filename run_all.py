# run_all.py - Executor para múltiplos marketplaces
import sys
import datetime
from run_scraper import run_marketplace_scraper


def run_multiple_marketplaces(marketplaces, max_products_per_session=75):
    """
    Executa scraping para múltiplos marketplaces em sequência.
    
    Args:
        marketplaces: Lista de códigos de marketplace (ex: ['US', 'GB', 'DE'])
        max_products_per_session: Limite de produtos por sessão
    
    Returns:
        dict: Resumo de execução para cada marketplace
    """
    
    print(f"\n{'='*80}")
    print(f"🚀 EXECUÇÃO EM LOTE - {len(marketplaces)} MARKETPLACE(S)")
    print(f"{'='*80}\n")
    
    results = {}
    start_time = datetime.datetime.now()
    
    for idx, marketplace in enumerate(marketplaces, 1):
        print(f"\n{'█'*80}")
        print(f"🌍 [{idx}/{len(marketplaces)}] INICIANDO: {marketplace}")
        print(f"{'█'*80}\n")
        
        marketplace_start = datetime.datetime.now()
        
        try:
            success = run_marketplace_scraper(marketplace, max_products_per_session)
            marketplace_end = datetime.datetime.now()
            duration = marketplace_end - marketplace_start
            
            results[marketplace] = {
                'success': success,
                'duration': duration,
                'status': '✅ Sucesso' if success else '❌ Falha'
            }
            
        except Exception as e:
            marketplace_end = datetime.datetime.now()
            duration = marketplace_end - marketplace_start
            
            results[marketplace] = {
                'success': False,
                'duration': duration,
                'status': f'❌ Erro: {str(e)[:50]}'
            }
            print(f"\n❌ ERRO CRÍTICO em {marketplace}: {e}\n")
        
        # Pausa entre marketplaces (evitar sobrecarga)
        if idx < len(marketplaces):
            print(f"\n⏸️  Pausa de 30s antes do próximo marketplace...")
            import time
            time.sleep(30)
    
    # === RESUMO FINAL ===
    total_time = datetime.datetime.now() - start_time
    
    print(f"\n{'='*80}")
    print("📊 RESUMO DA EXECUÇÃO EM LOTE")
    print(f"{'='*80}\n")
    
    for marketplace, result in results.items():
        print(f"{result['status']:20} | {marketplace:5} | Tempo: {result['duration']}")
    
    successful = sum(1 for r in results.values() if r['success'])
    failed = len(results) - successful
    
    print(f"\n{'─'*80}")
    print(f"✅ Sucessos: {successful}/{len(results)}")
    print(f"❌ Falhas:   {failed}/{len(results)}")
    print(f"⏱️  Tempo total: {total_time}")
    print(f"{'='*80}\n")
    
    return results


def main():
    """
    Ponto de entrada - define quais marketplaces executar.
    """
    
    # Verifica argumentos de linha de comando
    if len(sys.argv) > 1:
        # Se passou argumentos, usa eles
        # Exemplo: python run_all.py US GB DE
        marketplaces = [m.upper() for m in sys.argv[1:]]
    else:
        # Configuração padrão - escolha os marketplaces desejados
        print("\n🌍 CONFIGURAÇÃO DE MARKETPLACES")
        print("─" * 80)
        print("Edite este arquivo para definir os marketplaces padrão,")
        print("ou passe como argumentos: python run_all.py US GB DE\n")
        
        # ============================================================
        # 📝 EDITE AQUI: Defina os marketplaces que deseja executar
        # ============================================================
        marketplaces = [
            'US',  # Estados Unidos
            # 'GB',  # Reino Unido
            # 'DE',  # Alemanha
            # 'CA',  # Canadá
            # 'FR',  # França
            # 'IT',  # Itália
            # 'ES',  # Espanha
            # 'MX',  # México
        ]
        # ============================================================
        
        if not marketplaces:
            print("❌ ERRO: Nenhum marketplace definido!")
            print("\n💡 Opções:")
            print("   1. Edite run_all.py e descomente os marketplaces desejados")
            print("   2. Ou execute: python run_all.py US GB DE")
            sys.exit(1)
    
    print(f"\n📋 Marketplaces selecionados: {', '.join(marketplaces)}\n")
    
    # Confirmação antes de executar (pode comentar se quiser automático)
    if '--no-confirm' not in sys.argv:
        response = input("➡️  Continuar? (s/N): ").strip().lower()
        if response not in ['s', 'sim', 'y', 'yes']:
            print("❌ Execução cancelada pelo usuário")
            sys.exit(0)
    
    # Executa os marketplaces
    results = run_multiple_marketplaces(marketplaces, max_products_per_session=75)
    
    # Exit code baseado no sucesso
    all_successful = all(r['success'] for r in results.values())
    sys.exit(0 if all_successful else 1)


if __name__ == "__main__":
    main()


# ============================================================================
# EXEMPLOS DE USO:
# ============================================================================
#
# 1. Usar configuração padrão (definida no código):
#    python run_all.py
#
# 2. Especificar marketplaces via argumentos:
#    python run_all.py US GB DE
#
# 3. Executar todos os marketplaces principais:
#    python run_all.py US GB DE CA FR IT ES MX
#
# 4. Executar sem confirmação (útil para automação):
#    python run_all.py US GB --no-confirm
#
# 5. Via cron/scheduler:
#    0 2 * * * cd /path/to/project && python run_all.py --no-confirm
#
# ============================================================================