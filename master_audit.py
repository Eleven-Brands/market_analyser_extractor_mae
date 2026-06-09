# master_audit.py
"""
Auditoria Completa: integridade + análises
- Primeiro roda validações estruturais/integração (existência, leitura, escapes, datas, duplicatas, tamanho, etc.)
- Se o CSV não tiver problemas críticos, continua para auditoria analítica (outliers, variação histórica, regras de negócio)
Saída: terminal (prints coloridos e seções claras)
"""
import os
import sys
from datetime import datetime
import re
import pandas as pd

# Importa a função de carregar configurações do seu projeto scraper
from scraper.config_handler import load_config

# ---------------------------
# Helpers de cores e prints
# ---------------------------
class Color:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(title):
    print(f"\n{Color.HEADER}{Color.BOLD}{'='*12} {title.upper()} {'='*12}{Color.END}")

def print_subheader(title):
    print(f"\n{Color.BLUE}--- {title} ---{Color.END}")

def print_ok(message):
    print(f"  {Color.GREEN}✅ {Color.END} {message}")

def print_warn(message):
    print(f"  {Color.YELLOW}⚠️ {Color.END} {message}")

def print_err(message):
    print(f"  {Color.RED}❌ {Color.END} {message}")

# ---------------------------
# Checagem de integridade
# ---------------------------
def check_csv_integrity(file_path):
    results = {
        'file_exists': False,
        'readable': False,
        'has_rows': False,
        'has_columns': False,
        'no_escape_corruption': True,
        'date_range_valid': True,
        'issues': [],       # crítico -> aborta
        'warnings': [],     # avisos
        'valid': True
    }

    # 1. existe?
    if not os.path.exists(file_path):
        results['issues'].append(f"Arquivo não encontrado: {file_path}")
        results['valid'] = False
        return results

    results['file_exists'] = True
    file_size_mb = os.path.getsize(file_path) / (1024*1024)
    print_ok(f"Arquivo encontrado: {file_path} ({file_size_mb:.2f} MB)")

    # 2. tentar ler
    try:
        df = pd.read_csv(file_path, low_memory=False)
        results['readable'] = True
        print_ok(f"Arquivo lido: {len(df)} linhas, {len(df.columns)} colunas")
    except Exception as e:
        results['issues'].append(f"Erro ao ler CSV: {e}")
        results['valid'] = False
        return results

    # 3. linhas/colunas
    if len(df) == 0:
        results['issues'].append("Arquivo vazio (0 linhas)")
        results['valid'] = False
        return results
    results['has_rows'] = True

    if len(df.columns) == 0:
        results['issues'].append("Nenhuma coluna encontrada")
        results['valid'] = False
        return results
    results['has_columns'] = True

    # 4. corrupção de escapes (4+ barras invertidas)
    print_subheader("Verificação de escapes")
    cols_with_escapes = []
    for col in df.select_dtypes(include=['object']).columns:
        try:
            mask = df[col].astype(str).str.contains(r'\\{4,}', regex=True, na=False)
        except Exception:
            mask = pd.Series(False, index=df.index)
        if mask.sum() > 0:
            cols_with_escapes.append({'column': col, 'count': int(mask.sum()), 'examples': df.loc[mask, col].astype(str).head(2).tolist()})

    if cols_with_escapes:
        results['no_escape_corruption'] = False
        results['warnings'].append(f"Detectadas possíveis corrupções de escape em {len(cols_with_escapes)} coluna(s).")
        for c in cols_with_escapes:
            results['warnings'].append(f" - {c['column']}: {c['count']} linha(s). Exemplos: {c['examples']}")
        print_warn(f"{len(cols_with_escapes)} coluna(s) com padrões suspeitos de escape")
    else:
        print_ok("Nenhuma corrupção de escape detectada")

    # 5. valida datas
    print_subheader("Validação de datas")
    if 'Date' in df.columns:
        df['Date_parsed'] = pd.to_datetime(df['Date'], format='%m/%d/%Y', errors='coerce')
        invalid_dates = df[df['Date_parsed'].isna()]
        if len(invalid_dates) > 0:
            results['warnings'].append(f"{len(invalid_dates)} data(s) inválida(s) ou mal formatadas")
            results['date_range_valid'] = False
            print_warn(f"{len(invalid_dates)} data(s) inválida(s) detectada(s)")
        else:
            print_ok("Todas as datas parsearam corretamente")
        # resumo do range de datas (se houver válidas)
        valid_dates = df[df['Date_parsed'].notna()]
        if len(valid_dates) > 0:
            min_date = valid_dates['Date_parsed'].min()
            max_date = valid_dates['Date_parsed'].max()
            date_range_days = (max_date - min_date).days
            unique_dates = valid_dates['Date_parsed'].dt.date.nunique()
            print_ok(f"Período: {min_date.strftime('%d/%m/%Y')} -> {max_date.strftime('%d/%m/%Y')} ({date_range_days} dias), {unique_dates} datas únicas")
    else:
        results['warnings'].append("Coluna 'Date' não encontrada")
        print_warn("Coluna 'Date' não encontrada")

    # 6. duplicatas (Country, ASIN, Date)
    print_subheader("Verificação de duplicatas")
    if set(['Country', 'ASIN', 'Date']).issubset(df.columns):
        duplicates_mask = df.duplicated(subset=['Country', 'ASIN', 'Date'], keep=False)
        dup_count = int(duplicates_mask.sum())
        if dup_count > 0:
            results['warnings'].append(f"{dup_count} linha(s) potencialmente duplicada(s) por (Country, ASIN, Date)")
            print_warn(f"{dup_count} duplicata(s) detectada(s)")
        else:
            print_ok("Nenhuma duplicata encontrada")
    else:
        print_warn("Colunas para verificação de duplicatas ausentes (Country/ASIN/Date)")

    # 7. 'Not Found' ratio
    print_subheader("Verificação de 'Not Found'")
    try:
        not_found_ratio = (df == 'Not Found').sum().sum() / (len(df) * max(1, len(df.columns)))
    except Exception:
        not_found_ratio = 0.0
    if not_found_ratio > 0.3:
        results['warnings'].append(f"{not_found_ratio*100:.1f}% dos valores são 'Not Found' (alto)")
        print_warn(f"Taxa de 'Not Found': {not_found_ratio*100:.1f}% (ALTO)")
    else:
        print_ok(f"Taxa de 'Not Found': {not_found_ratio*100:.2f}% (normal)")

    # 8. tamanho médio por linha
    print_subheader("Tamanho do arquivo")
    avg_row_size_kb = (file_size_mb * 1024) / len(df)
    if avg_row_size_kb > 500:
        results['warnings'].append(f"Tamanho médio por linha {avg_row_size_kb:.1f} KB (suspeito)")
        print_warn(f"Tamanho médio por linha: {avg_row_size_kb:.1f} KB (muito alto)")
    else:
        print_ok(f"Tamanho médio por linha: {avg_row_size_kb:.2f} KB")

    # resumo final da integridade
    print_header("Resumo da Validação de Integridade")
    if results['issues']:
        results['valid'] = False
        for issue in results['issues']:
            print_err(issue)
    if results['warnings']:
        for w in results['warnings']:
            print_warn(w)
    if results['valid']:
        print_ok("Validação de integridade concluída sem problemas críticos")
    else:
        print_err("Validação de integridade falhou — corrija problemas críticos antes de prosseguir")

    # devolve df para uso posterior e results
    results['dataframe'] = df
    return results

# ---------------------------
# Funções analíticas (da outra parte)
# ---------------------------
def check_statistical_outliers(df):
    results = {}
    numerical_cols = ['Price', 'List Price', 'Number of ratings', 'PED']
    for col in numerical_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    for col in numerical_cols:
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
            outlier_details = []
            for country, group in df.groupby('Country'):
                clean_group = group[col].dropna()
                if len(clean_group) < 20:
                    continue
                Q1 = clean_group.quantile(0.25)
                Q3 = clean_group.quantile(0.75)
                IQR = Q3 - Q1
                lower = Q1 - 1.5 * IQR
                upper = Q3 + 1.5 * IQR
                outliers = clean_group[(clean_group < lower) | (clean_group > upper)]
                if not outliers.empty:
                    outlier_details.append(
                        f"{country}: {len(outliers)} outlier(s) ({outliers.min():.2f} - {outliers.max():.2f}); esperado ({lower:.2f}-{upper:.2f})"
                    )
            if outlier_details:
                results[col] = " | ".join(outlier_details)
    return results

def check_historical_changes(df):
    results = {}
    if 'Date' not in df.columns:
        return {"Erro": "Coluna 'Date' ausente para análise histórica."}

    df['Date'] = pd.to_datetime(df['Date'], format='%m/%d/%Y', errors='coerce')
    latest_date = df['Date'].max()
    if pd.isna(latest_date):
        return {"Erro": "Não foi possível determinar a data mais recente."}

    recent = df[df['Date'] == latest_date].copy()
    historical = df[df['Date'] < latest_date].copy()
    if historical.empty:
        return {"Aviso": "Sem histórico suficiente para comparar."}

    cols_to_analyze = ['Price', 'Number of ratings', 'PED']
    for col in cols_to_analyze:
        if col in historical.columns:
            historical[col] = pd.to_numeric(historical[col], errors='coerce')
            recent[col] = pd.to_numeric(recent[col], errors='coerce')

    hist_avg = historical.groupby(['Country', 'ASIN'])[cols_to_analyze].mean().reset_index()
    hist_avg.rename(columns={'Price': 'Avg_Price', 'Number of ratings': 'Avg_Num_Ratings'}, inplace=True)
    comp = pd.merge(recent, hist_avg, on=['Country', 'ASIN'], how='inner')

    # quedas de avaliações
    rating_drops = comp[comp['Number of ratings'] < comp['Avg_Num_Ratings']]
    if not rating_drops.empty:
        example = rating_drops.iloc[0]
        results['Queda de avaliações'] = f"{len(rating_drops)} produto(s) com queda no número de avaliações. Ex: ASIN {example.get('ASIN')} em {example.get('Country')}."

    # variações de preço >50%
    price_jumps = comp[
        (comp['Price'] > comp['Avg_Price'] * 1.5) |
        (comp['Price'] < comp['Avg_Price'] * 0.5)
    ]
    if not price_jumps.empty:
        example = price_jumps.iloc[0]
        results['Variação de preço >50%'] = f"{len(price_jumps)} produto(s) com variação de preço >50%. Ex: ASIN {example.get('ASIN')}."

    return results

# ---------------------------
# Auditoria full (chama checagem e depois análises)
# ---------------------------
def run_master_audit(file_path):
    print_header("Iniciando Auditoria Mestre")
    print(f"Analisando: {Color.BOLD}{file_path}{Color.END}")

    integrity = check_csv_integrity(file_path)
    if not integrity.get('valid', False):
        print_err("Auditoria interrompida devido a problemas críticos de integridade.")
        return integrity  # retorna relatório parcial

    df = integrity.get('dataframe')
    if df is None:
        print_err("Erro interno: dataframe ausente após validação.")
        return integrity

    # ===== Verificações analíticas e regras de negócio =====
    print_header("Auditoria Analítica e Regras de Negócio")

    issues = {
        'Valores Ausentes': {},
        'Valores "Not Found"': {},
        'Erros de Formato': {},
        'Inconsistências Lógicas': {},
        'Análise Estatística (Outliers)': {},
        'Análise Histórica de Variações': {}
    }

    # 1) Ausentes e "Not Found"
    essential_columns = ['Date', 'ASIN', 'Link', 'Country', 'Name', 'Brand', 'Price', 'Product Category', 'PED']
    for col in essential_columns:
        if col in df.columns:
            null_count = int(df[col].isnull().sum() + df[col].astype(str).str.strip().eq('').sum())
            if null_count > 0:
                issues['Valores Ausentes'][col] = f"{null_count} linhas com valores nulos ou em branco."
            not_found_count = int(df[col].astype(str).str.strip().eq('Not Found').sum())
            if not_found_count > 0:
                issues['Valores \"Not Found\"'][col] = f"{not_found_count} ocorrências."

    # 2) Regras de negócio e formatos
    if 'Rating Stars' in df.columns:
        ratings_numeric = pd.to_numeric(df['Rating Stars'], errors='coerce')
        invalid_ratings = df[(ratings_numeric < 0) | (ratings_numeric > 5)]
        if not invalid_ratings.empty:
            issues['Inconsistências Lógicas']['Rating Stars'] = f"{len(invalid_ratings)} linhas com Rating fora do intervalo 0-5."

    if 'Number of ratings' in df.columns:
        ratings_count_numeric = pd.to_numeric(df['Number of ratings'], errors='coerce')
        negative_counts = df[ratings_count_numeric < 0]
        if not negative_counts.empty:
            issues['Inconsistências Lógicas']['Number of ratings'] = f"{len(negative_counts)} linhas com contagem negativa."

    if 'Size Name' in df.columns:
        escape_char_rows = df[df['Size Name'].astype(str).str.contains(r'\\\\', na=False)]
        if not escape_char_rows.empty:
            ex = escape_char_rows.iloc[0]
            issues['Erros de Formato']['Size Name (Escape)'] = f"{len(escape_char_rows)} linhas com excesso de '\\\\'. Ex: ASIN {ex.get('ASIN')} - {ex.get('Country')}."

    # 3) Outliers estatísticos
    issues['Análise Estatística (Outliers)'] = check_statistical_outliers(df.copy())

    # 4) Análise histórica
    issues['Análise Histórica de Variações'] = check_historical_changes(df.copy())

    # --- Relatório resumido ---
    print_header("Relatório da Auditoria Analítica")
    total_issues = 0
    for category, details in issues.items():
        if details:
            print_subheader(category)
            if isinstance(details, dict):
                for k, v in details.items():
                    print_warn(f"{k}: {v}")
                    total_issues += 1
            else:
                print_warn(str(details))
                total_issues += 1

    print_header("Resumo Final")
    if total_issues == 0:
        print_ok("Nenhuma inconsistência crítica encontrada. Arquivo em bom estado.")
    else:
        print_warn(f"A auditoria encontrou {total_issues} tipo(s) de problema(s). Revise os pontos acima.")
    print("="*60)

    # remove df antes de retornar para evitar payload grande (mantém metrics)
    integrity.pop('dataframe', None)
    integrity['audit_issues'] = issues
    return integrity

# ---------------------------
# Main
# ---------------------------
if __name__ == "__main__":
    config_data = load_config()
    if not config_data:
        print_err("Erro ao carregar configuração. Verifique scraper.config_handler.load_config().")
        sys.exit(1)

    paths = config_data.get('paths', {})
    output_folder = paths.get('output_folder')
    output_filename = config_data.get('output_file_name')
    if not output_folder or not output_filename:
        print_err("Paths não configurados no arquivo de configuração (output_folder/output_file_name).")
        sys.exit(1)

    full_output_path = os.path.join(output_folder, output_filename)
    report = run_master_audit(full_output_path)
    # Se quiser, aqui poderia salvar report em JSON/arquivo — por enquanto apenas informa no terminal.
