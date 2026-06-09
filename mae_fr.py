# ============================================================================
# mae_fr.py - Wrapper simplificado para FR
# ============================================================================
from run_scraper import run_marketplace_scraper

if __name__ == "__main__":
    run_marketplace_scraper('FR', max_products_per_session=75)