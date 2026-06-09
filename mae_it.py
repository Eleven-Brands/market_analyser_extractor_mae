# ============================================================================
# mae_it.py - Wrapper simplificado para IT
# ============================================================================
from run_scraper import run_marketplace_scraper

if __name__ == "__main__":
    run_marketplace_scraper('IT', max_products_per_session=75)