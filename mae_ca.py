# ============================================================================
# mae_ca.py - Wrapper simplificado para CA
# ============================================================================
from run_scraper import run_marketplace_scraper

if __name__ == "__main__":
    run_marketplace_scraper('CA', max_products_per_session=100)