# ============================================================================
# mae_mx.py - Wrapper simplificado para MX
# ============================================================================
from run_scraper import run_marketplace_scraper

if __name__ == "__main__":
    run_marketplace_scraper('MX', max_products_per_session=100)