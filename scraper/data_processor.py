# mae_scraper/data_processor.py - VERSÃO CORRIGIDA
import pandas as pd
import re

# ASIN válido: exatamente 10 caracteres alfanuméricos maiúsculos
_ASIN_PATTERN = re.compile(r'^[A-Z0-9]{10}$')

def _is_valid_asin(value):
    """Verifica se o valor é um ASIN válido da Amazon (10 chars alfanuméricos)."""
    if not isinstance(value, str):
        return False
    return bool(_ASIN_PATTERN.match(value.strip()))


def clean_text_field(text):
    """Remove caracteres que podem quebrar o formato CSV."""
    if not isinstance(text, str):
        return text

    # Remove quebras de linha e tabs
    text = text.replace('\n', ' ').replace('\r', '').replace('\t', ' ')

    # Remove espaços múltiplos
    text = ' '.join(text.split())

    # Substitui aspas duplas por simples (aspas duplas quebram CSV)
    text = text.replace('"', "'")

    return text.strip()


def _sanitize_escapes(value):
    """
    Remove barras invertidas duplicadas que podem ter vindo da Amazon ou do escapechar.
    Exemplo: "Wide (20\'x13,3\')" permanece intacto
    Mas "Wide (20\\\\'x13,3\\\\')" vira "Wide (20\'x13,3\')"
    """
    if not isinstance(value, str):
        return value

    # Se houver 4+ barras seguidas, reduz para 1 (padrão CSV)
    # Isso evita corrupção de escape sequences
    value = re.sub(r'\\{4,}', r'\\', value)

    # Se houver 2-3 barras seguidas (comuns em corrupção), reduz para 1
    value = re.sub(r'\\{2,3}', r'\\', value)

    return value


def process_data_frame(df, base_url):
    """Aplica regras de negócio para limpar, validar e corrigir o DataFrame."""
    print("Processando e limpando os dados coletados...")
    if df.empty:
        return df, {}

    # Lista de colunas que podem ter texto problemático
    text_columns = ['Features', 'Name', 'Brand', 'Product Category', 'Stock',
                    'Badge', 'Merchant', 'Coupon', 'Date Created', 'Size Name']

    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].apply(clean_text_field)

    if 'Date Created' in df.columns:
        df['Date Created'] = pd.to_datetime(df['Date Created'], errors='coerce').dt.strftime('%m/%d/%Y')
        df['Date Created'] = df['Date Created'].fillna('Not Found')

    if 'ASIN Product Page' not in df.columns:
        df['ASIN Product Page'] = "Not Found"

    # =====================================================================
    # FIX: Validação de ASIN com formato correto antes de aplicar redirect
    #
    # Bug original: o seletor XPath de `asin_product_page` retornava string
    # vazia "" (não "Not Found") em páginas Amazon que mudaram layout.
    # String vazia passava pelo filtro de remoção mas sobrescrevia o ASIN
    # com "", que o pandas salvava e lia de volta como NaN — zerando todos
    # os dados de abril/maio 2026.
    #
    # Fix: só aceitar como ASIN de página um valor que seja ASIN válido
    # (10 chars alfanuméricos). Qualquer outra coisa → manter ASIN de input.
    # =====================================================================
    df['ASIN Page Valid'] = df['ASIN Product Page'].apply(_is_valid_asin)

    # Registra ASINs onde a página não retornou ASIN válido (para log)
    asins_not_found_df = df[~df['ASIN Page Valid']]
    asins_not_found_list = asins_not_found_df['ASIN'].tolist()
    num_rows_not_found_asin = len(asins_not_found_list)

    if num_rows_not_found_asin > 0:
        print(f"Info: {num_rows_not_found_asin} linha(s) sem ASIN válido na página — mantendo ASIN de input.")
        # NÃO remove as linhas — o input ASIN ainda é válido e os dados da
        # página (preço, rating, etc.) foram coletados corretamente.

    # Detecta e corrige redirects: ASIN da página é válido mas diferente do input
    redirect_mask = df['ASIN Page Valid'] & (df['ASIN'] != df['ASIN Product Page'])
    mismatch_df = df[redirect_mask]
    asins_mismatch_list = mismatch_df['ASIN'].tolist()
    mismatch_count = len(asins_mismatch_list)

    if mismatch_count > 0:
        print(f"Info: {mismatch_count} ASIN(s) foram corrigidos devido a redirecionamento.")
        df.loc[redirect_mask, 'ASIN'] = df.loc[redirect_mask, 'ASIN Product Page']

    df['Link'] = base_url + df['ASIN']
    df.drop(columns=['ASIN Product Page', 'ASIN Page Valid'], inplace=True, errors='ignore')
    # =====================================================================

    if 'Is Match ASIN' in df.columns:
        df.drop(columns=['Is Match ASIN'], inplace=True, errors='ignore')

    if 'Product Category' in df.columns:
        df['Root Category'] = df['Product Category'].str.split('â€º', n=1).str[0].str.strip()

    if 'pgid' in df.columns:
        df['DOW Name'] = df['pgid'].str.replace('_display_on_website', '', regex=False) \
                                   .str.replace('_', ' ').str.title()
        df['DOW Name'].fillna('Not Found', inplace=True)

    if 'BSR 1' in df.columns:
        df['BSR 1'] = df['BSR 1'].str.split(' (', n=1, regex=False).str[0].str.strip()

    if 'Coupon' in df.columns:
        df['Coupon'] = df['Coupon'].str.split('|').str[0].str.split(':').str[-1].str.strip()
        df['Coupon'] = df['Coupon'].fillna('')
        df['Coupon'] = df['Coupon'].str.replace(r'[\r\n]+', ' ', regex=True).str.strip()
        df.loc[df['Coupon'].str.strip() == '', 'Coupon'] = 'Not Found'

    if 'Product Category' in df.columns:
        df['Product Category'] = df['Product Category'].str.replace('â€º', ' â€º ')
    if 'Product Category Nodes' in df.columns:
        df['Product Category Nodes'] = df['Product Category Nodes'].astype(str).str.replace('â€º', ' â€º ')

    if 'PED' in df.columns and 'Price' in df.columns and 'List Price' in df.columns :
        df['PED'] = df['PED'].astype(str)
        df['Price'] = df['Price'].astype(str)
        df['List Price'] = df['Price'].astype(str)

        df.loc[df['PED'].str.contains('Join Prime to buy this item at', na=False), 'List Price'] = df['Price']
        df.loc[df['PED'].str.contains('Join Prime to buy this item at', na=False), 'Price'] = df['PED']

        df['PED'] = df['PED'].str.replace(r'Join Prime to buy this item at [^\d]*', '', regex=True)
        df['Price'] = df['Price'].str.replace(r'Join Prime to buy this item at [^\d]*', '', regex=True)

        df.loc[df['PED'] == 'This price is exclusively for Amazon Prime members.', 'PED'] = df['Price']
        df.loc[df['PED'] == 'Exclusive Prime price', 'PED'] = df['Price']

    def extract_numeric(text, pattern=r'\d+\.?\d*'):
        if not isinstance(text, str): return "Not Found"
        match = re.search(pattern, text.replace(",", ""))
        return match.group() if match else "Not Found"

    if 'Rating Stars' in df.columns:
        df["Rating Stars"] = df["Rating Stars"].apply(extract_numeric)
    if 'Number of ratings' in df.columns:
        def clean_int_text(text):
            if not isinstance(text, str): return "Not Found"
            # Remove ambos os separadores de milhares
            cleaned_text = text.replace(",", "").replace(".", "")
            match = re.search(r'\d+', cleaned_text)
            return match.group() if match else "Not Found"

        df["Number of ratings"] = df["Number of ratings"].apply(clean_int_text)
    if 'List Price' in df.columns:
        df["List Price"] = df["List Price"].apply(extract_numeric)

    # Truncamento de Size Name (máximo 100 caracteres)
    if 'Size Name' in df.columns:
        df['Size Name'] = df['Size Name'].astype(str).str.slice(0, 100)

    stats = {
        'rows_removed_no_asin': num_rows_not_found_asin,
        'asins_corrected': mismatch_count,
        'asins_not_found_list': asins_not_found_list,
        'asins_mismatch_list': asins_mismatch_list
    }

    # === LIMPEZA FINAL ===
    # Apenas remove caracteres perigosos, NÃO adiciona escapes
    for col in df.select_dtypes(include=['object']).columns:
        # Remove barras invertidas duplicadas ANTES de qualquer outra operação
        df[col] = df[col].astype(str).apply(_sanitize_escapes)

        # Remove quebras de linha e carriage returns
        df[col] = df[col].str.replace('\r', ' ', regex=False)
        df[col] = df[col].str.replace('\n', ' ', regex=False)

        # Remove espaços extras
        df[col] = df[col].str.strip()

    return df, stats
