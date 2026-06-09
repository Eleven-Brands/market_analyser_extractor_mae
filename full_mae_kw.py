# full_mae_kw.py
import os
import datetime
import time
import pandas as pd
import urllib.parse

from scraper.config_handler import load_config
from scraper.driver_handler import initialize_driver, set_delivery_location
from scraper.utils import load_input
from scraper.data_scraper import scrape_keyword_page
from scraper.kw_processor import assign_new_rank, pivot_ranks_to_columns

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

def main():
    """
    Orquestra o scraping de palavras-chave para todos os marketplaces usando BeautifulSoup.
    """
    config_data = load_config('kw_config.json')
    if not config_data:
        return

    paths = config_data['paths']
    settings = config_data['settings']
    
    keyword_input_path = os.path.join(paths['input_folder'], settings['keyword_input_file'])
    output_path = os.path.join(paths['output_folder'], settings['keyword_output_file'])
    
    all_results = []

    for code, marketplace_config in config_data['marketplaces'].items():
        print("\n" + "="*80)
        print(f"Starting {marketplace_config['name']} KW Tracker")
        
        # Carrega as keywords para a região
        df_keywords = pd.read_csv(keyword_input_path)
        keywords_to_track = df_keywords[df_keywords['Sales Region'] == marketplace_config['sales_region_code']]['Keywords'].tolist()

        if not keywords_to_track:
            print(f"Nenhuma palavra-chave encontrada para a região '{marketplace_config['sales_region_code']}'. Pulando.")
            continue

        driver = None
        try:
            driver = initialize_driver(marketplace_config['language_code'])
            if not driver: continue
            
            set_delivery_location(driver, code, marketplace_config['domain'], marketplace_config.get('zip_code'))

            for keyword in keywords_to_track:
                # Monta a URL de busca
                search_url = f"https://{marketplace_config['domain']}/s?k={urllib.parse.quote_plus(keyword)}"
                print(f"\nBuscando pela keyword: '{keyword}' - {search_url}")
                
                driver.get(search_url)
                try:
                    # Espera o primeiro resultado aparecer para garantir que a página carregou
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-component-type='s-search-result']"))
                    )
                    time.sleep(2) # Pausa extra para renderização completa
                    
                    # Passa o HTML para a função de scraping com BeautifulSoup
                    page_results = scrape_keyword_page(driver.page_source, keyword, marketplace_config)
                    all_results.extend(page_results)
                    
                except Exception as e:
                    print(f"  - ERRO ao carregar ou processar a página para '{keyword}': {e}")

        except Exception as e:
            print(f"ERRO CRÍTICO no marketplace '{code}': {e}")
        finally:
            if driver:
                driver.quit()
                print(f"\nDriver para {code} fechado.")

    # --- Consolidação e Salvamento Final ---
    print("\n" + "="*80)
    print("Processamento concluído. Consolidando e salvando resultados...")
    
    if not all_results:
        print("Nenhum dado de ranking foi coletado.")
        return

    df_new = pd.DataFrame(all_results)
        
    # --- LÓGICA DE PROCESSAMENTO ATUALIZADA ---
    # 1. Primeiro, calcula os ranks separados para orgânico e patrocinado
    print("Calculando ranks orgânicos e patrocinados...")
    df_ranked = assign_new_rank(df_new)
    
    # 2. Em seguida, pivota os dados para as novas colunas
    print("Reformatando a saída para as colunas 'Organic Rank' e 'Sponsored Rank'...")
    df_pivoted = pivot_ranks_to_columns(df_ranked)
    
    try:
        df_existing = pd.read_csv(output_path)
    except FileNotFoundError:
        df_existing = pd.DataFrame()

    df_final = pd.concat([df_existing, df_pivoted], ignore_index=True)
    
    # A desduplicação agora é mais simples
    df_final.sort_values(by=['Date', 'Keyword'], ascending=True, inplace=True)
    df_final.drop_duplicates(subset=['Date', 'Country', 'Keyword', 'ASIN'], keep='last', inplace=True)
    
    df_final.to_csv(output_path, index=False)
    print(f"Arquivo de ranking final salvo com {len(df_final)} linhas em {output_path}")
    
if __name__ == "__main__":
    main()