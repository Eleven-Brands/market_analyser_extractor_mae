# mae_scraper/logging_handler.py - VERSÃO COM SLACK + CLICKUP
import os
import datetime
import json
import pandas as pd
import numpy as np
import re
import uuid
import requests
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Carrega variáveis do arquivo .env local (se existir) — não afeta vars já definidas no sistema
try:
    from dotenv import load_dotenv
    load_dotenv(override=False)
except ImportError:
    pass

# === CONFIGURAÇÃO DE NOTIFICAÇÕES ===
# Slack (mantido por compatibilidade)
SLACK_TOKEN = os.getenv('SLACK_TOKEN', '')
SLACK_CHANNEL = "#mae-log"

# ClickUp (nova integração)
CLICKUP_API_KEY = os.getenv('CLICKUP_API_KEY', '')
CLICKUP_WORKSPACE_ID = os.getenv('CLICKUP_WORKSPACE_ID', '')
CLICKUP_CHANNEL_ID = os.getenv('CLICKUP_CHANNEL_ID', '')

# Controla qual serviço usar (ambos por padrão)
SEND_TO_SLACK = os.getenv('SEND_TO_SLACK', 'true').lower() == 'true'
SEND_TO_CLICKUP = os.getenv('SEND_TO_CLICKUP', 'true').lower() == 'true'


def _format_timedelta(td):
    """Formata um objeto timedelta em uma string legível (ex: 1h 15m 30s)."""
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 or not parts:
        parts.append(f"{seconds}s")
        
    return " ".join(parts)


def _send_slack_notification(marketplace_code, status, processed_rows, total_requested, 
                             processing_time, total_errors, price_ped_errors):
    """
    Envia notificação Slack com resultados da execução.
    """
    if not SEND_TO_SLACK:
        return
    
    try:
        client = WebClient(token=SLACK_TOKEN)
        
        country_emojis = {
            "US": ":us:", "GB": ":gb:", "CA": ":flag-ca:", "MX": ":flag-mx:",
            "DE": ":de:", "FR": ":fr:", "IT": ":it:", "ES": ":es:"
        }
        
        # Calcula taxa de sucesso
        success_rate = (processed_rows / total_requested * 100) if total_requested > 0 else 0
        
        country_flag = country_emojis.get(marketplace_code, ":grey_question:")
        status_emoji = ":white_check_mark:" if status == 'success' else ":warning:"
        status_text = "ran successfully" if status == 'success' else "ran with errors"
        formatted_time = _format_timedelta(processing_time)
        
        # Emoji baseado na taxa de sucesso
        if success_rate >= 95:
            rate_emoji = "🟢"
        elif success_rate >= 85:
            rate_emoji = "🟡"
        else:
            rate_emoji = "🔴"
        
        message_lines = [
            f"{country_flag} *MAE {marketplace_code}:*",
            f"MAE {marketplace_code} {status_text} {status_emoji}",
            f"- Extracted: {processed_rows}/{total_requested} products ({rate_emoji} {success_rate:.1f}%)",
            f"- Processing time: {formatted_time}",
            f"- Scraping errors: {total_errors}"
        ]
        
        if price_ped_errors > 0:
            message_lines.append(f"   - Price/PED errors: {price_ped_errors}")
        
        slack_message = "\n".join(message_lines)
        client.chat_postMessage(channel=SLACK_CHANNEL, text=slack_message)
        print(f"✅ Slack notification sent for {marketplace_code}")
        
    except SlackApiError as e:
        print(f"❌ Slack API error: {e.response['error']}")
    except Exception as e:
        print(f"❌ Error sending Slack notification: {e}")


def _send_clickup_notification(marketplace_code, status, processed_rows, total_requested, 
                               processing_time, total_errors, price_ped_errors):
    """
    Envia notificação ClickUp Chat com resultados da execução.
    Usa formato Markdown para melhor visualização.
    """
    if not SEND_TO_CLICKUP:
        return
    
    try:
        # Calcula taxa de sucesso
        success_rate = (processed_rows / total_requested * 100) if total_requested > 0 else 0
        
        # Emojis baseados na taxa de sucesso
        if success_rate >= 95:
            rate_emoji = "🟢"
            status_emoji = "✅"
        elif success_rate >= 85:
            rate_emoji = "🟡"
            status_emoji = "⚠️"
        else:
            rate_emoji = "🔴"
            status_emoji = "❌"
        
        # Emojis de país
        country_emojis = {
            "US": "🇺🇸", "GB": "🇬🇧", "CA": "🇨🇦", "MX": "🇲🇽",
            "DE": "🇩🇪", "FR": "🇫🇷", "IT": "🇮🇹", "ES": "🇪🇸"
        }
        country_flag = country_emojis.get(marketplace_code, "🌍")
        
        formatted_time = _format_timedelta(processing_time)
        status_text = "Completed Successfully" if status == 'success' else "Completed with Errors"
        
        # Monta mensagem em Markdown
        message_content = f"""
{country_flag} **MAE {marketplace_code}** - {status_text} {status_emoji}

**📊 Results:**
• Extracted: **{processed_rows}/{total_requested}** products ({rate_emoji} **{success_rate:.1f}%**)
• Processing time: **{formatted_time}**
• Scraping errors: **{total_errors}**
"""
        
        if price_ped_errors > 0:
            message_content += f"• Price/PED errors: **{price_ped_errors}**\n"
        
        message_content = message_content.strip()
        
        # Configuração da API
        url = f"https://api.clickup.com/api/v3/workspaces/{CLICKUP_WORKSPACE_ID}/chat/channels/{CLICKUP_CHANNEL_ID}/messages"
        
        payload = {
            "type": "message",
            "content_format": "text/md",
            "content": message_content
        }
        
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": CLICKUP_API_KEY
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            print(f"✅ ClickUp notification sent for {marketplace_code}")
        else:
            print(f"⚠️ ClickUp notification failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except requests.exceptions.Timeout:
        print(f"⚠️ ClickUp notification timeout for {marketplace_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ ClickUp request error: {e}")
    except Exception as e:
        print(f"❌ Error sending ClickUp notification: {e}")


def save_execution_summary(config_data, stats):
    """Salva apenas um resumo de execução para dashboard (sem detalhes de ASINs)."""
    log_folder = config_data['paths']['log_folder']
    summary_file = os.path.join(log_folder, "execution_summary.csv")
    
    try:
        processing_time = stats.get('total_time_diff')
        total_time_seconds = processing_time.total_seconds() if processing_time else 0
        processed_rows = stats.get('total_new_rows', 0)
        total_requested = stats.get('total_requested_asins', processed_rows)
        avg_time_per_asin = total_time_seconds / max(processed_rows, 1) if processed_rows > 0 else 0
        success_rate = (processed_rows / total_requested * 100) if total_requested > 0 else 0
        
        execution_summary = {
            'Execution ID': str(uuid.uuid4())[:8],
            'Date': stats.get('end_datetime', datetime.datetime.now()).strftime('%Y-%m-%d'),
            'Time': stats.get('end_datetime', datetime.datetime.now()).strftime('%H:%M:%S'),
            'Country': stats.get('marketplace_code', 'N/A'),
            'Processed ASINs': processed_rows,
            'Total Requested': total_requested,
            'Success Rate (%)': round(success_rate, 1),
            'Processing Time (min)': round(total_time_seconds / 60, 1),
            'Avg Time per ASIN (s)': round(avg_time_per_asin, 2),
            'Price/PED Errors': len(stats.get('price_ped_errors', [])),
            'Scraping Errors': len(stats.get('error_asins_list', [])),
            'Redirected ASINs': stats.get('asins_corrected', 0),
            'Total Errors': len(stats.get('error_asins_list', [])) + len(stats.get('price_ped_errors', []))
        }
        
        if os.path.exists(summary_file):
            df_existing = pd.read_csv(summary_file)
            df_new = pd.DataFrame([execution_summary])
            df_final = pd.concat([df_existing, df_new], ignore_index=True)
        else:
            df_final = pd.DataFrame([execution_summary])
        
        df_final.to_csv(summary_file, index=False)
        print(f"Execution summary saved to: {summary_file}")
        
    except Exception as e:
        print(f"Error saving execution summary: {e}")


def save_error_sample(config_data, stats):
    """Salva apenas uma amostra dos erros mais críticos (não todos)."""
    log_folder = config_data['paths']['log_folder']
    error_sample_file = os.path.join(log_folder, "error_samples.csv")
    
    try:
        current_date = datetime.date.today().strftime('%Y-%m-%d')
        current_time = datetime.datetime.now().strftime('%H:%M:%S')
        marketplace_code = stats.get('marketplace_code', 'N/A')
        
        error_samples = []
        
        failed_asins = stats.get('error_asins_list', [])[:10]
        for asin in failed_asins:
            error_samples.append({
                'Date': current_date,
                'Time': current_time,
                'Country': marketplace_code,
                'ASIN': asin,
                'Error Type': 'Complete Scraping Failure',
                'Error Details': 'Failed after multiple retries'
            })
        
        price_ped_errors = stats.get('price_ped_errors', [])[:10]
        for asin in price_ped_errors:
            error_samples.append({
                'Date': current_date,
                'Time': current_time,
                'Country': marketplace_code,
                'ASIN': asin,
                'Error Type': 'Price/PED Error',
                'Error Details': 'Both Price and PED fields empty/not found'
            })
        
        if error_samples:
            if os.path.exists(error_sample_file):
                df_existing = pd.read_csv(error_sample_file)
                df_new = pd.DataFrame(error_samples)
                df_final = pd.concat([df_existing, df_new], ignore_index=True)
            else:
                df_final = pd.DataFrame(error_samples)
            
            df_final.to_csv(error_sample_file, index=False)
            print(f"Error samples saved to: {error_sample_file}")
    
    except Exception as e:
        print(f"Error saving error samples: {e}")


def _is_empty_or_not_found(value):
    """Verifica se um valor está vazio, é None, NaN ou 'Not Found'."""
    if pd.isna(value) or value is None:
        return True
    if isinstance(value, str):
        return value.strip() == '' or value.strip() == 'Not Found'
    return False


def detect_price_ped_errors(df):
    """Detecta ASINs onde tanto 'Price' quanto 'PED' estão vazias/problemáticas."""
    if df.empty or 'Price' not in df.columns or 'PED' not in df.columns:
        return []
    
    price_ped_errors = []
    
    for _, row in df.iterrows():
        price_empty = _is_empty_or_not_found(row.get('Price'))
        ped_empty = _is_empty_or_not_found(row.get('PED'))
        
        if price_empty and ped_empty:
            price_ped_errors.append(row.get('ASIN', 'Unknown'))
    
    return price_ped_errors


def write_final_log_file(config_data, stats, send_notifications=True):
    """
    Escreve log final com resumos ao invés de listas completas de ASINs.
    Envia notificações para Slack E ClickUp (se habilitados).
    """
    log_folder = config_data['paths']['log_folder']
    log_file_path = os.path.join(log_folder, f"{datetime.date.today().strftime('%Y-%m-%d')}.txt")
    
    marketplace_code = stats.get('marketplace_code', 'N/A')
    processed_rows = stats.get('total_new_rows', 0)
    total_requested = stats.get('total_requested_asins', processed_rows)
    processing_time = stats.get('total_time_diff')
    asins_corrected = stats.get('asins_corrected', 0)
    rows_removed = stats.get('rows_removed_no_asin', 0)
    
    error_asins = stats.get('error_asins_list', [])
    price_ped_errors = stats.get('price_ped_errors', [])
    
    num_scraping_errors = len(error_asins)
    num_price_ped_errors = len(price_ped_errors)
    total_errors = num_scraping_errors + num_price_ped_errors + asins_corrected + rows_removed
    
    # Calcula taxa de sucesso
    success_rate = (processed_rows / total_requested * 100) if total_requested > 0 else 0
    
    status = "Ran Successfully" if total_errors == 0 else "Ran with Errors"
    
    report_lines = [
        "=" * 60,
        f"MAE {marketplace_code} - {status}",
        f"Extracted: {processed_rows}/{total_requested} products ({success_rate:.1f}%)",
        "-" * 60,
        f"Finished at: {stats['end_datetime'].strftime('%Y-%m-%d %H:%M')}",
        f"Processing time: {_format_timedelta(processing_time)}",
        f"- Processed ASINs: {processed_rows}"
    ]
    
    if total_errors > 0:
        report_lines.append(f"- Scraping errors: {total_errors}")
        if num_price_ped_errors > 0:
            report_lines.append(f"   - Price/PED errors: {num_price_ped_errors}")
        if asins_corrected > 0:
            report_lines.append(f"   - Redirected ASINs: {asins_corrected}")
        if rows_removed > 0:
            report_lines.append(f"   - Rows removed (ASIN not found on page): {rows_removed}")
            
        if num_scraping_errors > 0:
            report_lines.append(f"- Sample failed ASINs (showing first 3): {', '.join(error_asins[:3])}")
        if num_price_ped_errors > 0:
            report_lines.append(f"- Sample Price/PED errors (showing first 3): {', '.join(price_ped_errors[:3])}")
    else:
        report_lines.append("- Scraping errors: 0")
    
    report_lines.append("=" * 60 + "\n")

    # Salva arquivo de log
    try:
        with open(log_file_path, 'a', encoding='utf-8') as f:
            f.write("\n".join(report_lines))
        print(f"Execution report saved to: {log_file_path}")
    except Exception as e:
        print(f"Error writing log file: {e}")
    
    # Salva resumos estruturados
    save_execution_summary(config_data, stats)
    save_error_sample(config_data, stats)
    
    # Envia notificações (ambos os serviços)
    if send_notifications:
        notification_status = 'success' if total_errors == 0 else 'error'
        
        # Slack
        if SEND_TO_SLACK:
            try:
                _send_slack_notification(
                    marketplace_code=marketplace_code,
                    status=notification_status,
                    processed_rows=processed_rows,
                    total_requested=total_requested,
                    processing_time=processing_time,
                    total_errors=total_errors,
                    price_ped_errors=num_price_ped_errors
                )
            except Exception as e:
                print(f"⚠️ Failed to send Slack notification: {e}")
        
        # ClickUp
        if SEND_TO_CLICKUP:
            try:
                _send_clickup_notification(
                    marketplace_code=marketplace_code,
                    status=notification_status,
                    processed_rows=processed_rows,
                    total_requested=total_requested,
                    processing_time=processing_time,
                    total_errors=total_errors,
                    price_ped_errors=num_price_ped_errors
                )
            except Exception as e:
                print(f"⚠️ Failed to send ClickUp notification: {e}")