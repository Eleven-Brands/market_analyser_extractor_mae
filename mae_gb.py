# ============================================================================
# mae_gb.py - Wrapper simplificado para GB
# ============================================================================
from run_scraper import run_marketplace_scraper

if __name__ == "__main__":
    run_marketplace_scraper('GB', max_products_per_session=75)