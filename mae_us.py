# ============================================================================
# mae_us.py - Wrapper simplificado para US
# ============================================================================
from run_scraper import run_marketplace_scraper

if __name__ == "__main__":
    run_marketplace_scraper('US', max_products_per_session=100)
