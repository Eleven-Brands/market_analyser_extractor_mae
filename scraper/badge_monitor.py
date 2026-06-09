# scraper/badge_monitor.py
import os
import csv
import re
import warnings
import pandas as pd

_BQ_PROJECT = 'amazon-sp-api-openbridge'
_BQ_VIEW = 'amazon-sp-api-openbridge.2_Silver_Aux.vw_all_listings_report_last_date'

MONITORED_FIELDS = ['Badge', 'Limited Time Deal', 'Deal', 'Coupon', 'Stock']

_EVENTS_FILENAME = 'badge_events.csv'
_EVENTS_FIELDNAMES = ['Date', 'ASIN', 'Country', 'SKU', 'Field', 'Value_before', 'Value_after', 'Change_type']

# Stock normalization rules: (category, list_of_regex_patterns)
_STOCK_RULES = [
    ('in_stock',      [r'^in stock$', r'^en stock$', r'^auf lager$', r'^disponibilità immediata$',
                       r'^in stock\b']),
    ('low_stock',     [r'^only \d+', r'^nur noch \d+', r'^il ne reste plus que \d+',
                       r'^solo \d+ rim', r'left in stock', r'auf lager\b']),
    ('unavailable',   [r'unavailable', r'indisponible', r'non disponibile',
                       r'no disponible', r'nicht verf']),
    ('ships_delayed', [r'ships within', r'usually ship', r'habituellement exp',
                       r'expédié sous', r'within \d+ to \d+ day']),
]


def _normalize_stock(raw):
    if pd.isna(raw) or str(raw).strip() in ('', 'Not Found', 'nan'):
        return 'null'
    v = str(raw).strip().lower()
    for category, patterns in _STOCK_RULES:
        if any(re.search(p, v) for p in patterns):
            return category
    return 'null'


def _normalize_badge(raw):
    if pd.isna(raw) or str(raw).strip() in ('', 'Not Found', 'nan'):
        return 'null'
    return str(raw).strip()


def _load_own_asins_bq(marketplace_code):
    """Returns {asin: sku} for active own listings in this marketplace."""
    import google.auth
    from google.cloud import bigquery
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        credentials, _ = google.auth.default()
    client = bigquery.Client(project=_BQ_PROJECT, credentials=credentials)
    query = f"""
        SELECT DISTINCT asin, sku
        FROM `{_BQ_VIEW}`
        WHERE sales_country = @marketplace_code
          AND status = 'Active'
          AND asin IS NOT NULL
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter('marketplace_code', 'STRING', marketplace_code)]
    )
    result = client.query(query, job_config=job_config).result()
    return {row.asin: row.sku for row in result}


def _read_output_file(output_path, marketplace_code, own_asins):
    """Read OUTPUT_FILE.csv filtered to own ASINs in this marketplace."""
    needed_cols = ['Date', 'ASIN', 'Country'] + MONITORED_FIELDS
    df = pd.read_csv(output_path, low_memory=False, usecols=lambda c: c in needed_cols)

    # Ensure all monitored fields are present (older CSV may be missing some)
    for col in MONITORED_FIELDS:
        if col not in df.columns:
            df[col] = 'Not Found'

    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df[
        (df['Country'] == marketplace_code) &
        (df['ASIN'].isin(own_asins))
    ]
    # Keep last record per ASIN+Date in case of duplicates
    df = df.sort_values('Date').drop_duplicates(subset=['ASIN', 'Date'], keep='last')
    return df


def _detect_changes(today_df, prev_df, asin_sku_map):
    """Compare two day DataFrames (indexed by ASIN) and return change events."""
    events = []
    common = today_df.index.intersection(prev_df.index)

    for asin in common:
        today_row = today_df.loc[asin]
        prev_row = prev_df.loc[asin]
        sku = asin_sku_map.get(asin, '')

        for field in MONITORED_FIELDS:
            raw_before = prev_row.get(field, 'Not Found')
            raw_after  = today_row.get(field, 'Not Found')

            if field == 'Stock':
                val_before = _normalize_stock(raw_before)
                val_after  = _normalize_stock(raw_after)
            else:
                val_before = _normalize_badge(raw_before)
                val_after  = _normalize_badge(raw_after)

            if val_before == val_after:
                continue

            if val_before == 'null' and val_after != 'null':
                change_type = 'gained'
            elif val_before != 'null' and val_after == 'null':
                change_type = 'lost'
            else:
                change_type = 'changed'

            events.append({
                'Date':         today_row.name if hasattr(today_row, 'name') else '',
                'ASIN':         asin,
                'Country':      today_row.get('Country', ''),
                'SKU':          sku,
                'Field':        field,
                'Value_before': val_before,
                'Value_after':  val_after,
                'Change_type':  change_type,
            })

    return events


def _write_events(events_file, events, run_date):
    """Append events to badge_events.csv, adding header if file is new."""
    file_exists = os.path.exists(events_file)
    with open(events_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=_EVENTS_FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        for ev in events:
            ev['Date'] = run_date
        writer.writerows(events)


def run(config_data, marketplace_code):
    """
    Detect badge and stock changes for own ASINs after a scraper run.
    Appends events to badge_events.csv in the log folder.
    Returns list of event dicts (empty if no changes or on error).
    """
    output_path = os.path.join(
        config_data['paths']['output_folder'],
        config_data.get('output_file_name', 'OUTPUT_FILE.csv')
    )
    events_file = os.path.join(config_data['paths']['log_folder'], _EVENTS_FILENAME)

    # 1. Load own ASINs + SKU mapping from BigQuery
    try:
        asin_sku = _load_own_asins_bq(marketplace_code)
    except Exception as e:
        print(f'[badge_monitor] BQ load failed: {e}')
        return []

    if not asin_sku:
        print(f'[badge_monitor] No active own ASINs for {marketplace_code}.')
        return []

    print(f'[badge_monitor] {len(asin_sku)} own ASINs for {marketplace_code}.')

    # 2. Read relevant rows from OUTPUT_FILE.csv
    try:
        df = _read_output_file(output_path, marketplace_code, set(asin_sku.keys()))
    except Exception as e:
        print(f'[badge_monitor] Failed to read output file: {e}')
        return []

    if df.empty:
        print(f'[badge_monitor] No own ASIN data in output file for {marketplace_code}.')
        return []

    # 3. Find two most recent scrape dates
    dates = sorted(df['Date'].dropna().unique(), reverse=True)
    if len(dates) < 2:
        print(f'[badge_monitor] Need >=2 dates to compare for {marketplace_code}, found {len(dates)}.')
        return []

    date_today = dates[0]
    date_prev  = dates[1]
    print(f'[badge_monitor] Comparing {date_prev.date()} vs {date_today.date()}.')

    today_df = df[df['Date'] == date_today].set_index('ASIN')
    prev_df  = df[df['Date'] == date_prev].set_index('ASIN')

    # 4. Detect changes
    events = _detect_changes(today_df, prev_df, asin_sku)

    # 5. Write to badge_events.csv
    if events:
        try:
            _write_events(events_file, events, date_today.strftime('%Y-%m-%d'))
            print(f'[badge_monitor] {len(events)} change(s) recorded to badge_events.csv.')
        except Exception as e:
            print(f'[badge_monitor] Failed to write events: {e}')
    else:
        print(f'[badge_monitor] No badge/stock changes detected for {marketplace_code}.')

    return events
