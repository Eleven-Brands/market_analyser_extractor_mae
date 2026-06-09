# run_scraper.py - COM VERIFICAÇÕES ALEATÓRIAS CONFIGURÁVEIS
import os
import sys
import datetime
import time
import pandas as pd
import csv

from scraper.session_manager import SessionManager
from scraper.config_handler import load_config
from scraper.utils import load_input, split_into_batches
from scraper.data_scraper import scrape_single_product
from scraper.data_processor import process_data_frame
from scraper.logging_handler import write_final_log_file, detect_price_ped_errors


def run_marketplace_scraper(target_marketplace, max_products_per_session=50):
    """
    Função centralizada para executar scraping de qualquer marketplace.
    NOVO: Verificações aleatórias configuráveis por marketplace
    """
    
    config_data = load_config()
    if not config_data:
        return False
        
    script_start_time = datetime.datetime.now()
    
    if target_marketplace not in config_data['marketplaces']:
        print(f"❌ ERRO: Marketplace '{target_marketplace}' não encontrado no config.")
        print(f"   Marketplaces disponíveis: {', '.join(config_data['marketplaces'].keys())}")
        return False
    
    marketplace_config = config_data['marketplaces'][target_marketplace]
    
    paths_config = config_data['paths']
    output_filename = config_data['output_file_name']
    full_output_path = os.path.join(paths_config['output_folder'], output_filename)
    
    print(f"\n{'='*80}")
    print(f"🎯 INICIANDO SCRAPER: {marketplace_config['name']} ({target_marketplace})")
    print(f"{'='*80}\n")
    
    # === CONFIGURAÇÃO DE VERIFICAÇÕES ALEATÓRIAS POR MARKETPLACE ===
    check_probability_map = {
        'DE': 0.40,  # Alemanha: mais agressivo (problema conhecido com €)
        'FR': 0.20,  # França: médio-alto
        'IT': 0.20,  # Itália: médio-alto
        'ES': 0.20,  # Espanha: médio-alto
        'US': 0.15,  # EUA: padrão
        'GB': 0.15,  # Reino Unido: padrão
        'CA': 0.15,  # Canadá: padrão
        'MX': 0.15,  # México: padrão
    }
    
    check_probability = check_probability_map.get(target_marketplace, 0.15)
    print(f"🎲 Verificações aleatórias configuradas: {int(check_probability * 100)}% por produto")
    print(f"   (Média esperada: ~{int(max_products_per_session * check_probability)} verificações por sessão)")
    
    default_xpaths = config_data.get('default_xpaths', {})
    final_xpaths = default_xpaths.copy()
    final_xpaths.update(marketplace_config.get('xpaths', {}))
    
    asins_to_scrape = load_input(config_data, target_marketplace)
    if not asins_to_scrape:
        print(f"❌ Nenhum ASIN encontrado para {target_marketplace}")
        return False

    total_requested_asins = len(asins_to_scrape)
    print(f"📋 Total de ASINs a processar: {total_requested_asins}\n")
    
    login_email = os.getenv('AMAZON_EMAIL')
    login_password = os.getenv('AMAZON_PASSWORD')
    
    if not login_email or not login_password:
        print("ℹ️  Scraping será executado SEM login (credenciais não encontradas)")
        print("   Para usar login, defina: AMAZON_EMAIL e AMAZON_PASSWORD\n")
        login_email = None
        login_password = None
    else:
        print(f"🔐 Login configurado para: {login_email[:3]}***@{login_email.split('@')[1]}\n")

    # === INICIALIZAÇÃO DO SESSION MANAGER COM VERIFICAÇÕES ALEATÓRIAS ===
    session_manager = SessionManager(
        max_products_per_session=max_products_per_session,
        min_session_break=15,
        max_session_break=25,
        login_email=login_email,
        login_password=login_password,
        random_check_probability=check_probability  # NOVO PARÂMETRO
    )
    
    num_batches = 1
    asin_batches = split_into_batches(asins_to_scrape, num_batches)
    print(f"📦 ASINs organizados em {len(asin_batches)} lote(s)")

    all_data_for_marketplace = []
    current_error_asins = []
    
    base_url = marketplace_config['base_url']
    bsr_text = marketplace_config['bsr_search_text']
    replacements = marketplace_config.get('text_replacements')
    expected_zip = marketplace_config.get('zip_code')
    
    # === LOOP PRINCIPAL DE SCRAPING ===
    for batch_num, asin_batch in enumerate(asin_batches, 1):
        if not asin_batch.size > 0:
            continue
            
        print(f"\n{'─'*80}")
        print(f"📂 LOTE {batch_num}/{len(asin_batches)} - {len(asin_batch)} ASINs")
        print(f"{'─'*80}\n")
        
        for i, asin in enumerate(asin_batch):
            
            if session_manager.needs_new_session():
                success = session_manager.start_new_session(
                    marketplace_config['language_code'], 
                    marketplace_config
                )
                if not success:
                    print(f"❌ Falha ao criar sessão. Pulando ASIN {asin}")
                    current_error_asins.append(asin)
                    continue
            
            retry_count = 0
            max_retries = 2
            scrape_success = False
            
            while retry_count < max_retries and not scrape_success:
                try:
                    product_data = session_manager.scrape_product(
                        scrape_single_product,
                        url=base_url + asin + "?th=1",
                        asin=asin,
                        marketplace_code=target_marketplace,
                        xpaths=final_xpaths,
                        replacements=replacements,
                        bsr_search_text=bsr_text,
                        expected_zip=expected_zip,
                        marketplace_config=marketplace_config
                    )
                    
                    if product_data:
                        all_data_for_marketplace.append(product_data)
                        
                        # Progress tracking - apenas a cada 25 produtos
                        if (i + 1) % 25 == 0 or i == 0:
                            batch_progress = ((i + 1) / len(asin_batch)) * 100
                            total_progress = (len(all_data_for_marketplace) / total_requested_asins) * 100
                            
                            print(f"✅ [{i+1}/{len(asin_batch)}] ASIN {asin}")
                            print(f"   📊 Progresso: Lote {batch_progress:.1f}% | Total {total_progress:.1f}%")
                            
                            # Exibe estatísticas da sessão (incluindo verificações aleatórias)
                            stats = session_manager.get_session_stats()
                            if isinstance(stats, dict):
                                total_in_session = stats['products_scraped'] + stats['products_remaining']
                                print(f"   🔄 Sessão #{stats['session_number']}: "
                                      f"{stats['products_scraped']}/{total_in_session} produtos")
                                
                                # NOVO: Exibe estatísticas de verificações aleatórias
                                if stats.get('random_checks_performed', 0) > 0:
                                    success_rate = stats.get('random_check_success_rate', 0)
                                    print(f"   🎲 Verificações aleatórias: "
                                          f"{stats['random_checks_performed']} "
                                          f"(Sucesso: {success_rate:.1f}%)")
                                print("")
                            
                        scrape_success = True
                    else:
                        raise Exception("Session manager retornou None")
                        
                except Exception as e:
                    retry_count += 1
                    print(f"❌ Erro ASIN {asin} (tentativa {retry_count}/{max_retries}): {e}")
                    if retry_count < max_retries:
                        print(f"   🔄 Aguardando 1s antes de tentar novamente...")
                        time.sleep(1)
                        
            if not scrape_success:
                print(f"💥 FALHA FINAL: ASIN {asin} após {max_retries} tentativas\n")
                current_error_asins.append(asin)

    session_manager.close_session()
    
    # === PROCESSAMENTO E SALVAMENTO ===
    print(f"\n{'='*80}")
    print("📊 CONSOLIDANDO RESULTADOS...")
    print(f"{'='*80}\n")
    
    try:
        df_existing = pd.read_csv(full_output_path)
        print(f"✅ Arquivo existente carregado: {len(df_existing)} linhas")
    except FileNotFoundError:
        df_existing = pd.DataFrame()
        print("ℹ️  Criando novo arquivo de output")

    total_new_rows = 0
    price_ped_error_asins = []
    processing_stats = {}
    
    if all_data_for_marketplace:
        df_new = pd.DataFrame(all_data_for_marketplace)
        print(f"📋 Dados coletados: {len(df_new)} linhas")
        
        df_new, processing_stats = process_data_frame(df_new, marketplace_config['base_url'])
        
        price_ped_error_asins = detect_price_ped_errors(df_new)
        if price_ped_error_asins:
            print(f"⚠️  {len(price_ped_error_asins)} ASINs com problemas em Price/PED")
        
        total_new_rows = len(df_new)
        df_final_consolidated = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        print("⚠️  Nenhum dado novo coletado")
        df_final_consolidated = df_existing

    if not df_final_consolidated.empty:
        df_final_consolidated['Date'] = pd.to_datetime(
            df_final_consolidated['Date'], 
            format='%m/%d/%Y', 
            errors='coerce'
        )
        df_final_consolidated.sort_values(by='Date', ascending=True, inplace=True)
        df_final_consolidated.drop_duplicates(
            subset=['Country', 'ASIN', 'Date'], 
            keep='last', 
            inplace=True
        )
        df_final_consolidated['Date'] = df_final_consolidated['Date'].dt.strftime('%m/%d/%Y')
        
        df_final_consolidated.to_csv(
            full_output_path, 
            index=False,
            encoding='utf-8-sig',
            quoting=csv.QUOTE_ALL,
            doublequote=True
        )
        print(f"💾 Arquivo salvo: {len(df_final_consolidated)} linhas únicas")
        print(f"   📁 Localização: {full_output_path}")

    # === LOG FINAL ===
    script_end_time = datetime.datetime.now()
    final_log_stats = {
        'marketplace_name': marketplace_config['name'],
        'marketplace_code': target_marketplace,
        'end_datetime': script_end_time,
        'total_time_diff': script_end_time - script_start_time,
        'total_new_rows': total_new_rows,
        'total_requested_asins': total_requested_asins,
        'error_asins_list': current_error_asins,
        'price_ped_errors': price_ped_error_asins
    }
    final_log_stats.update(processing_stats)
    write_final_log_file(config_data, final_log_stats)
    
    success_rate = (total_new_rows / total_requested_asins * 100) if total_requested_asins > 0 else 0
    
    print(f"\n{'='*80}")
    print("✅ PROCESSO FINALIZADO")
    print(f"{'='*80}")
    print(f"⏱️  Tempo total: {final_log_stats['total_time_diff']}")
    print(f"✅ Sucessos: {total_new_rows}/{total_requested_asins} ASINs ({success_rate:.1f}%)")
    print(f"❌ Erros: {len(current_error_asins)} ASINs")
    if price_ped_error_asins:
        print(f"⚠️  Price/PED: {len(price_ped_error_asins)} ASINs")
    print(f"{'='*80}\n")
    
    return True


def main():
    """Ponto de entrada principal - aceita argumentos de linha de comando."""
    
    if len(sys.argv) > 1:
        target_marketplace = sys.argv[1].upper()
    else:
        print("\n🌍 MARKETPLACES DISPONÍVEIS:")
        print("   - US (Estados Unidos)")
        print("   - GB (Reino Unido)")
        print("   - DE (Alemanha) - 25% verificações")
        print("   - CA (Canadá)")
        print("   - FR (França) - 20% verificações")
        print("   - IT (Itália) - 20% verificações")
        print("   - ES (Espanha) - 20% verificações")
        print("   - MX (México)")
        
        target_marketplace = input("\n➡️  Digite o código do marketplace: ").strip().upper()
    
    if not target_marketplace:
        print("❌ ERRO: Marketplace não especificado")
        print("\n💡 Uso:")
        print("   python run_scraper.py US")
        print("   python run_scraper.py DE")
        print("   ou execute sem argumentos para modo interativo")
        sys.exit(1)
    
    success = run_marketplace_scraper(target_marketplace)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()