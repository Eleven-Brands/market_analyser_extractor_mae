# Exemplo de como modificar mae_us.py (ou qualquer outro)

import os
import datetime
import time
import pandas as pd
import numpy as np
import csv

# Adicione esta importação
from scraper.session_manager import SessionManager
from scraper.config_handler import load_config
from scraper.utils import load_input, split_into_batches
from scraper.data_scraper import scrape_single_product
from scraper.data_processor import process_data_frame
from scraper.logging_handler import write_final_log_file, detect_price_ped_errors

# TARGET_MARKETPLACE = 'US'  # ou GB, DE, etc.

def main(TARGET_MARKETPLACE):
    config_data = load_config()
    if not config_data:
        return
        
    
    # Configuração do marketplace
    if TARGET_MARKETPLACE not in config_data['marketplaces']:
        print(f"ERRO: Marketplace '{TARGET_MARKETPLACE}' não encontrado.")
        return
    marketplace_config = config_data['marketplaces'][TARGET_MARKETPLACE]
    
    # Setup de paths
    paths_config = config_data['paths']
    
    print(f"\n🎯 INICIANDO: {marketplace_config['name']} ({TARGET_MARKETPLACE})")
    
    # Carregar ASINs
    asins_to_scrape = load_input(config_data, TARGET_MARKETPLACE)
    
    base_url = "https://www.amazon.com/dp/"
    suffix = "?th=1"
    
    df = pd.DataFrame(asins_to_scrape, columns=['coluna'])
    
    # Concatena o texto fixo com o conteúdo da coluna
    df['coluna'] = base_url + df['coluna'] + suffix
    
    df.to_csv(
        f"G:/Shared drives/OrganiHaus/3.1 - OH Data & Reports/z_personal_folders/lucca_lanzellotti/Projetos/MAE/Octoparse/input{TARGET_MARKETPLACE}.csv",
        index=False,
        header=False,
        encoding='utf-8'
    )

 
if __name__ == "__main__":
    main('US')
    # main('DE')
    # main('CA')
    # main('GB')