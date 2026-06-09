# mae_testing.py
import os
import datetime
import time
import pandas as pd
import numpy as np
import csv

from scraper.session_manager import SessionManager
from scraper.config_handler import load_config
from scraper.utils import load_input, split_into_batches
from scraper.data_scraper import scrape_single_product
from scraper.data_processor import process_data_frame
from scraper.logging_handler import write_final_log_file, detect_price_ped_errors
from scraper.retry_manager import RetryManager, RetryStrategy  # NOVO

TARGET_MARKETPLACE = 'DE'

def scrape_with_retry(session_manager, retry_manager, asin, marketplace_config, final_xpaths, bsr_text, replacements, expected_zip, base_url, retry_attempt=1):
    """
    Wrapper para scraping com gerenciamento de retry.
    Retorna (success: bool, product_data: dict or None)
    """
    try:
        if session_manager.needs_new_session():
            success = session_manager.start_new_session(
                marketplace_config['language_code'], 
                marketplace_config
            )
            if not success:
                raise Exception("Falha ao criar nova sessão")
        
        product_data = session_manager.scrape_product(
            scrape_single_product,
            url=base_url + asin + "?th=1",
            asin=asin,
            marketplace_code=TARGET_MARKETPLACE,
            xpaths=final_xpaths,
            replacements=replacements,
            bsr_search_text=bsr_text,
            expected_zip=expected_zip,
            marketplace_config=marketplace_config # <<< CORREÇÃO: Passa o config
        )
        
        if product_data:
            retry_manager.mark_successful(asin)
            return (True, product_data)
        else:
            raise Exception("Session manager retornou None")
    
    except Exception as e:
        error_msg = str(e)
        
        # Classifica o tipo de erro
        if "ZIP" in error_msg or "zip" in error_msg.lower():
            error_type = "zip_error"
        elif "network" in error_msg.lower() or "timeout" in error_msg.lower():
            error_type = "network_error"
        else:
            error_type = "scraping_error"
        
        retry_manager.add_failed_asin(asin, reason=error_type)
        print(f"❌ Erro ASIN {asin} (tentativa {retry_attempt}): {error_msg}")
        
        return (False, None)


def main():
    config_data = load_config()
    if not config_data:
        return
    
    script_start_time = datetime.datetime.now()
    
    # Marketplace setup
    if TARGET_MARKETPLACE not in config_data['marketplaces']:
        print(f"ERRO: Marketplace '{TARGET_MARKETPLACE}' não encontrado.")
        return
    marketplace_config = config_data['marketplaces'][TARGET_MARKETPLACE]
    
    paths_config = config_data['paths']
    output_filename = config_data['output_file_name']
    full_output_path = os.path.join(paths_config['output_folder'], output_filename)
    
    print(f"\n🎯 INICIANDO: {marketplace_config['name']} ({TARGET_MARKETPLACE})")
    
    # XPath setup
    default_xpaths = config_data.get('default_xpaths', {})
    final_xpaths = default_xpaths.copy()
    final_xpaths.update(marketplace_config.get('xpaths', {}))
    
    # Load ASINs
    asins_to_scrape = load_input(config_data, TARGET_MARKETPLACE)
    asins_to_scrape = asins_to_scrape[:1]
    asins_to_scrape.append("B0B61V8KNW")
    
    
    if not asins_to_scrape:
        print(f"❌ Nenhum ASIN encontrado para {TARGET_MARKETPLACE}")
        return

    # NOVO: Inicializar RetryManager
    retry_manager = RetryManager()
    
    session_manager = SessionManager(
        max_products_per_session=100,
        min_session_break=15,
        max_session_break=25
    )
    
    num_batches = 1
    asin_batches = split_into_batches(asins_to_scrape, num_batches)
    print(f"📦 {len(asins_to_scrape)} ASINs divididos em {len(asin_batches)} lotes")

    all_data_for_marketplace = []
    
    # Scraping configs
    base_url = marketplace_config['base_url']
    bsr_text = marketplace_config['bsr_search_text']
    replacements = marketplace_config.get('text_replacements')
    expected_zip = marketplace_config.get('zip_code')
    
    # === FASE 1: SCRAPING INICIAL ===
    print("\n" + "="*70)
    print("🚀 FASE 1: SCRAPING INICIAL")
    print("="*70)
    
    for batch_num, asin_batch in enumerate(asin_batches, 1):
        if not asin_batch.size > 0:
            continue
        
        print(f"\n📂 === LOTE {batch_num}/{len(asin_batches)} ({len(asin_batch)} ASINs) ===")
        
        for i, asin in enumerate(asin_batch):
            success, product_data = scrape_with_retry(
                session_manager, retry_manager, asin, 
                marketplace_config, final_xpaths, bsr_text, 
                replacements, expected_zip, base_url
            )
            
            if success:
                all_data_for_marketplace.append(product_data)
                batch_progress = ((i + 1) / len(asin_batch)) * 100
                total_progress = ((len(all_data_for_marketplace)) / len(asins_to_scrape)) * 100
                print(f"✅ ASIN {asin} | Lote: {batch_progress:.1f}% | Total: {total_progress:.1f}%")
                
                stats = session_manager.get_session_stats()
                if isinstance(stats, dict):
                    print(f"   🔄 Sessão {stats['session_number']}: {stats['products_scraped']}/{stats['products_scraped'] + stats['products_remaining']} produtos")
    
    # === FASE 2: RETRY DE ASINS FALHADOS ===
    print("\n" + "="*70)
    print("🔄 FASE 2: RETRY DE ASINS FALHADOS")
    print("="*70)
    
    retry_iterations = 0
    max_retry_iterations = 3
    
    while retry_iterations < max_retry_iterations:
        retry_iterations += 1
        retryable_asins = retry_manager.get_retryable_asins()
        
        if not retryable_asins:
            print("✅ Nenhum ASIN pendente de retry")
            break
        
        print(f"\n📥 TENTATIVA DE RETRY {retry_iterations}/{max_retry_iterations}")
        print(f"   ASINs a retentear: {len(retryable_asins)}")
        
        for asin_obj in retryable_asins:
            strategy = retry_manager.get_strategy_for_asin(asin_obj)
            
            # Aplica estratégia
            if strategy == RetryStrategy.DELAYED:
                wait_time = 5 + (asin_obj.retry_count * 3)  # Aumenta com cada tentativa
                print(f"⏱️  {asin_obj.asin}: Aguardando {wait_time}s antes de retry...")
                time.sleep(wait_time)
            
            elif strategy == RetryStrategy.NEW_SESSION:
                print(f"🔌 {asin_obj.asin}: Criando nova sessão para retry...")
                session_manager.close_session()
                time.sleep(3)
            
            elif strategy == RetryStrategy.SKIP:
                print(f"⏭️  {asin_obj.asin}: Esgotadas tentativas. Pulando...")
                retry_manager.finalize_failures()
                continue
            
            # Tenta novamente
            success, product_data = scrape_with_retry(
                session_manager, retry_manager, asin_obj.asin, 
                marketplace_config, final_xpaths, bsr_text, 
                replacements, expected_zip, base_url,
                retry_attempt=asin_obj.retry_count + 1
            )
            
            if success:
                all_data_for_marketplace.append(product_data)
                print(f"✅ RECUPERADO: {asin_obj.asin}")
            else:
                asin_obj.increment_retry(f"Tentativa {asin_obj.retry_count} falhou")
        
        time.sleep(2)
    
    # Finaliza falhas permanentes
    retry_manager.finalize_failures()
    retry_manager.print_summary()
    
    # === CONSOLIDAÇÃO E SALVAMENTO ===
    print("\n" + "="*80)
    print("Processamento concluído. Consolidando resultados...")
    
    session_manager.close_session()
    
    # try:
    #     df_existing = pd.read_csv(full_output_path)
    # except FileNotFoundError:
    #     df_existing = pd.DataFrame()

    total_new_rows = 0
    price_ped_error_asins = []
    processing_stats = {}
    
    if all_data_for_marketplace:
        df_new = pd.DataFrame(all_data_for_marketplace)
        df_new, processing_stats = process_data_frame(df_new, marketplace_config['base_url'])
        
        price_ped_error_asins = detect_price_ped_errors(df_new)
        if price_ped_error_asins:
            print(f"Detectados {len(price_ped_error_asins)} ASINs com problemas em Price e PED.")
        
        total_new_rows = len(df_new)
        # df_final_consolidated = pd.concat([df_existing, df_new], ignore_index=True)
        df_final_consolidated = df_new
    else:
        # df_final_consolidated = df_existing
        df_final_consolidated = pd.DataFrame() # Corrigido de df_new
        
    print("Printando resultados")
    print(df_new['Number of ratings'])

    # if not df_final_consolidated.empty:
    #     df_final_consolidated['Date'] = pd.to_datetime(df_final_consolidated['Date'], format='%m/%d/%Y', errors='coerce')
    #     df_final_consolidated.sort_values(by='Date', ascending=True, inplace=True)
    #     df_final_consolidated.drop_duplicates(subset=['Country', 'ASIN','Date'], keep='last', inplace=True)
    #     df_final_consolidated['Date'] = df_final_consolidated['Date'].dt.strftime('%m/%d/%Y')
    #     df_final_consolidated.to_csv(
    #         # full_output_path,
    #         r"G:\Shared drives\OrganiHaus\3.1 - OH Data & Reports\z_personal_folders\lucca_lanzellotti\Projetos\MAE\Projeto MAE\Output\check_listings.csv" ,
    #         index=False,
    #         encoding='utf-8-sig',
    #         quoting=csv.QUOTE_MINIMAL,
    #         escapechar='\\'
    #     )
    #     print(f"Arquivo final salvo com {len(df_final_consolidated)} linhas únicas em {full_output_path}")

    # === LOG FINAL ===
    script_end_time = datetime.datetime.now()
    # final_log_stats = {
    #     'marketplace_name': marketplace_config['name'],
    #     'marketplace_code': TARGET_MARKETPLACE,
    #     'end_datetime': script_end_time,
    #     'total_time_diff': script_end_time - script_start_time,
    #     'total_new_rows': total_new_rows,
    #     'error_asins_list': retry_manager.permanently_failed,  # Mostra apenas os permanentemente falhados
    #     'price_ped_errors': price_ped_error_asins,
    #     'recovered_asins': len(retry_manager.successful_asins)
    # }
    # final_log_stats.update(processing_stats)
    # write_final_log_file(config_data, final_log_stats)
    
    print("\nProcesso finalizado.")

if __name__ == "__main__":
    main()