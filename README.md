# Market Analyser Extractor (MAE) — Scraper

Scraper diário de dados de produtos Amazon para o dashboard **OrganiHaus Market Research** (Power BI).

Coleta preço, rating, BSR, badges, merchant, cupons e outros campos de produto para ASINs próprios (OrganiHaus) e concorrentes, em múltiplos marketplaces.

---

## Marketplaces suportados

| Código | Marketplace       |
|--------|-------------------|
| US     | amazon.com        |
| CA     | amazon.ca         |
| GB     | amazon.co.uk      |
| DE     | amazon.de         |
| FR     | amazon.fr         |
| IT     | amazon.it         |
| ES     | amazon.es         |
| MX     | amazon.com.mx     |

---

## Fontes de ASINs

| Tipo        | Fonte                                                                 |
|-------------|-----------------------------------------------------------------------|
| Próprios    | BigQuery — `2_Silver_Aux.vw_all_listings_report_last_date` (`status = 'Active'`) |
| Concorrentes | Excel — `MAE Competitors - Editado v3.xlsx` (sheet por marketplace)  |

---

## Output

Arquivo CSV único, atualizado diariamente por append + deduplicação:

```
market_analyser_extractor_mae/OUTPUT/OUTPUT_FILE.csv
```

Deduplicação por `Country + ASIN + Date` (keep last). Colunas principais:

`Date`, `ASIN`, `Country`, `Brand`, `Name`, `Price`, `List Price`, `Rating Stars`, `Number of ratings`, `BSR 1`, `BSR 2`, `Merchant`, `Stock`, `Badge`, `Coupon`, `Deal`, `PED`, `Prev Month Qty`, `Features`, `Product Category`, `Root Category`, `Freq Badge`

---

## Estrutura do projeto

```
mae_scraper/
├── run_all.py              # Roda múltiplos marketplaces em sequência
├── run_scraper.py          # Roda um único marketplace
├── mae_config.json         # XPaths, configurações e paths por marketplace
├── .env                    # Credenciais locais (gitignored — não commitar)
└── scraper/
    ├── config_handler.py   # Carrega mae_config.json
    ├── utils.py            # load_input: combina ASINs próprios (BQ) + concorrentes (Excel)
    ├── data_scraper.py     # Extração de dados por página de produto
    ├── data_processor.py   # Limpeza, validação de ASIN e redirect detection
    ├── driver_handler.py   # Inicialização do Selenium/undetected-chromedriver
    ├── session_manager.py  # Rotação de sessões com delays e verificações aleatórias
    ├── currency_validator.py # Validação de moeda por marketplace
    ├── logging_handler.py  # Logs, notificações Slack e ClickUp
    └── retry_manager.py    # Lógica de retry
```

---

## Pré-requisitos

- Python 3.13 (único com `undetected-chromedriver` instalado)
- Google Chrome instalado
- Google Drive for Desktop autenticado (para paths `G:\Shared drives\...`)
- Credenciais Google ADC configuradas (`gcloud auth application-default login`) para acesso ao BigQuery

Instalar dependências:
```powershell
pip install -r requirements.txt
```

---

## Credenciais

Crie um arquivo `.env` na raiz do projeto (nunca commitar):

```env
SLACK_TOKEN=xoxb-...
CLICKUP_API_KEY=pk_...
CLICKUP_WORKSPACE_ID=...
CLICKUP_CHANNEL_ID=...
```

As credenciais são carregadas automaticamente via `python-dotenv`. Variáveis de ambiente do sistema têm prioridade sobre o `.env`.

---

## Como rodar

**Todos os marketplaces em sequência:**
```powershell
"C:\Users\User VivoBook\AppData\Local\Programs\Python\Python313\python.exe" run_all.py ES DE FR IT CA GB US --no-confirm
```

**Um marketplace específico:**
```powershell
"C:\Users\User VivoBook\AppData\Local\Programs\Python\Python313\python.exe" run_scraper.py US
```

---

## Logs

```
market_analyser_extractor_mae/LOGS/
├── YYYY-MM-DD.txt          # Resumo por dia (todos os marketplaces)
├── execution_summary.csv   # Histórico de execuções
└── error_samples.csv       # ASINs com erros (Price/PED ou falha completa)
```

Notificações automáticas enviadas para Slack (`#mae-log`) e ClickUp ao fim de cada marketplace.

---

## Notas técnicas

- **ASIN próprios:** Buscados via BigQuery em tempo real — refletem automaticamente novos lançamentos e listings desativados, sem necessidade de atualizar arquivos manualmente.
- **Redirect detection:** Se o ASIN da URL da página difere do ASIN de input, o registro é corrigido automaticamente (`data_processor.py`).
- **Sessões:** Cada sessão processa até 50 produtos e é reiniciada com nova instância do Chrome, delays aleatórios e validação de ZIP/moeda.
- **Moeda GB:** Cookie `i18n-prefs=GBP` forçado antes de navegar aos ASINs para evitar preços em BRL (IP brasileiro).
- **Price null esperado:** Produtos indisponíveis/OOS retornam `Not Found` no campo `Price` — comportamento correto, não erro do scraper.