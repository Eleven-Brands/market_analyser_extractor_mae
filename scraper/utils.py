# mae_scraper/utils.py
import warnings
import pandas as pd
import numpy as np

_BQ_PROJECT = 'amazon-sp-api-openbridge'
_BQ_VIEW = 'amazon-sp-api-openbridge.2_Silver_Aux.vw_all_listings_report_last_date'


def split_into_batches(data_list, num_batches):
    """Divide uma lista em um número específico de lotes (batches) o mais iguais possível."""
    if not data_list:
        return []
    return np.array_split(np.array(data_list), num_batches)


def _load_own_asins_from_bq(marketplace_code):
    """Busca ASINs próprios com status Active no BigQuery."""
    import google.auth
    from google.cloud import bigquery

    # ADC sem quota project gera um UserWarning não-fatal; suprimimos aqui.
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        credentials, project = google.auth.default()

    client = bigquery.Client(project=_BQ_PROJECT, credentials=credentials)

    query = f"""
        SELECT DISTINCT asin
        FROM `{_BQ_VIEW}`
        WHERE sales_country = @marketplace_code
          AND status = 'Active'
          AND asin IS NOT NULL
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter('marketplace_code', 'STRING', marketplace_code)
        ]
    )
    result = client.query(query, job_config=job_config).result()
    return [row.asin for row in result]


def load_input(config_data, marketplace_code):
    """
    Carrega e combina ASINs de concorrentes e produtos próprios.
    - Próprios: BigQuery (listings ativos, status = 'Active')
    - Concorrentes: MAE Competitors Excel (inalterado)
    """
    print(f"Carregando e combinando ASINs para o marketplace: '{marketplace_code}'")

    competitors_file = config_data['paths']['competitors_file']

    # --- ASINs próprios via BigQuery ---
    try:
        product_asins = _load_own_asins_from_bq(marketplace_code)
        print(f"   - Total de {len(product_asins)} ASINs próprios ativos (BigQuery).")
    except Exception as e:
        print(f"   [ERRO] Falha ao carregar ASINs próprios do BigQuery: {e}")
        product_asins = []

    # --- ASINs de concorrentes via Excel ---
    try:
        competitor_df = pd.read_excel(competitors_file, sheet_name=marketplace_code)
        competitor_asins = competitor_df['ASIN'].dropna().astype(str).tolist()
    except Exception:
        competitor_asins = []

    print(f"   - Total de {len(competitor_asins)} ASINs concorrentes a serem processados.")

    # --- Combinar e remover duplicados ---
    return list(set(competitor_asins + product_asins))