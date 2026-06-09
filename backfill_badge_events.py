"""
backfill_badge_events.py
Regenera badge_events.csv a partir do OUTPUT_FILE.csv para um período histórico.

USO:
  python backfill_badge_events.py [START_DATE]

  START_DATE (opcional): formato YYYY-MM-DD, default = 2026-05-16

QUANDO USAR:
  - Após mudança no schema do badge_monitor
  - Para popular o histórico inicial
  - Para regenerar eventos corrompidos

ATENÇÃO: sobrescreve o badge_events.csv existente.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from scraper.badge_monitor import (
    _load_own_asins_bq, _detect_changes,
    _EVENTS_FIELDNAMES, MONITORED_FIELDS,
)
from scraper.config_handler import load_config

COUNTRIES = ['US', 'CA', 'GB', 'DE', 'FR', 'IT', 'ES']


def main():
    start_date = sys.argv[1] if len(sys.argv) > 1 else '2026-05-16'
    print(f'Backfill de badge events a partir de {start_date}')

    config = load_config()
    output_path = os.path.join(
        config['paths']['output_folder'],
        config.get('output_file_name', 'OUTPUT_FILE.csv')
    )
    events_file = os.path.join(config['paths']['log_folder'], 'badge_events.xlsx')

    # Carrega OUTPUT_FILE.csv uma vez (apenas colunas necessárias)
    print('Carregando OUTPUT_FILE.csv...')
    needed_cols = ['Date', 'ASIN', 'Country'] + MONITORED_FIELDS
    df_full = pd.read_csv(output_path, low_memory=False, usecols=lambda c: c in needed_cols)
    df_full['Date'] = pd.to_datetime(df_full['Date'], errors='coerce')
    df_full = df_full[df_full['Date'] >= start_date]
    print(f'  {len(df_full):,} linhas carregadas (>= {start_date})')

    all_events = []

    for country in COUNTRIES:
        print(f'\n[{country}]')
        try:
            asin_sku = _load_own_asins_bq(country)
        except Exception as e:
            print(f'  Erro BQ: {e}')
            continue

        if not asin_sku:
            print(f'  Nenhum ASIN próprio ativo.')
            continue

        print(f'  {len(asin_sku)} ASINs próprios')

        country_df = df_full[
            (df_full['Country'] == country) &
            (df_full['ASIN'].isin(asin_sku.keys()))
        ].copy()

        for col in MONITORED_FIELDS:
            if col not in country_df.columns:
                country_df[col] = 'Not Found'

        country_df = (country_df
                      .sort_values('Date')
                      .drop_duplicates(subset=['ASIN', 'Date'], keep='last'))

        dates = sorted(country_df['Date'].dropna().unique())
        if len(dates) < 2:
            print(f'  Datas insuficientes ({len(dates)}), pulando.')
            continue

        print(f'  {len(dates)} datas: {dates[0].date()} -> {dates[-1].date()}')

        count = 0
        for i in range(1, len(dates)):
            date_prev  = dates[i - 1]
            date_today = dates[i]
            prev_df  = country_df[country_df['Date'] == date_prev].set_index('ASIN')
            today_df = country_df[country_df['Date'] == date_today].set_index('ASIN')

            events = _detect_changes(today_df, prev_df, asin_sku)
            for ev in events:
                ev['Date'] = date_today.strftime('%Y-%m-%d')
            all_events.extend(events)
            count += len(events)

        print(f'  {count} eventos')

    # Sobrescreve badge_events.xlsx
    ev_df = pd.DataFrame(all_events, columns=_EVENTS_FIELDNAMES) if all_events else pd.DataFrame(columns=_EVENTS_FIELDNAMES)
    ev_df.to_excel(events_file, index=False, engine='openpyxl')

    print(f'\nTotal: {len(all_events)} eventos gravados em badge_events.xlsx')

    if all_events:
        ev_df = pd.DataFrame(all_events)
        print('\nResumo por Country / Field / Change_type:')
        print(ev_df.groupby(['Country', 'Field', 'Change_type']).size().to_string())


if __name__ == '__main__':
    main()