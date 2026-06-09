# ============================================================================
# mae_de.py - Wrapper simplificado para DE
# ============================================================================
from run_scraper import run_marketplace_scraper

if __name__ == "__main__":
    run_marketplace_scraper('DE', max_products_per_session=75)