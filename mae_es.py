# ============================================================================
# mae_es.py - Wrapper simplificado para ES
# ============================================================================
from run_scraper import run_marketplace_scraper

if __name__ == "__main__":
    run_marketplace_scraper('ES', max_products_per_session=75)