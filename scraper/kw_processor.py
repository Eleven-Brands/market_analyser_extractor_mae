# scraper/kw_processor.py
import pandas as pd

def assign_new_rank(df):
    """
    Calcula o rank separado para itens orgânicos e patrocinados.
    Este é um passo intermediário.
    """
    if df.empty or 'Sponsored' not in df.columns:
        return df

    df = df.sort_values(by=['Date', 'Country', 'Keyword', 'Sponsored', 'Rank'])
    df['Rank'] = df.groupby(['Date', 'Country', 'Keyword', 'Sponsored']).cumcount() + 1
    
    return df

def pivot_ranks_to_columns(df):
    """
    Transforma o DataFrame para ter as colunas 'Organic Rank' e 'Sponsored Rank',
    preservando todas as outras colunas de dados.
    """
    if df.empty or 'Sponsored' not in df.columns:
        return df

    # --- LÓGICA CORRIGIDA ---
    # 1. Define dinamicamente as colunas-chave (todas exceto 'Rank' e 'Sponsored')
    key_columns = [col for col in df.columns if col not in ['Rank', 'Sponsored']]

    # 2. Separa os dados em orgânicos e patrocinados
    df_organic = df[df['Sponsored'] == 'No'].copy()
    df_sponsored = df[df['Sponsored'] == 'Yes'].copy()

    # 3. Renomeia a coluna 'Rank' em cada sub-tabela
    df_organic.rename(columns={'Rank': 'Organic Rank'}, inplace=True)
    df_sponsored.rename(columns={'Rank': 'Sponsored Rank'}, inplace=True)
    
    # 4. Faz um merge (junção) das duas tabelas usando todas as colunas-chave
    if not df_sponsored.empty and not df_organic.empty:
        df_final = pd.merge(
            df_organic,
            df_sponsored,
            on=key_columns,
            how='outer'
        )
    elif not df_organic.empty:
        df_final = df_organic
        df_final['Sponsored Rank'] = pd.NA
    elif not df_sponsored.empty:
        df_final = df_sponsored
        df_final['Organic Rank'] = pd.NA
    else:
        df_final = pd.DataFrame() # Retorna um DF vazio se não houver dados

    # Garante que as colunas desejadas existam no final
    final_columns = key_columns + ['Organic Rank', 'Sponsored Rank']
    for col in final_columns:
        if col not in df_final.columns:
            df_final[col] = pd.NA

    # Retorna o DataFrame com todas as colunas preservadas
    return df_final[final_columns]