"""
debug_deal_selectors.py
Ferramenta de diagnóstico para identificar seletores corretos de LTD/Coupon
em diferentes marketplaces Amazon.

USO:
  python debug_deal_selectors.py <URL_DO_PRODUTO>

Exemplos:
  python debug_deal_selectors.py https://www.amazon.fr/dp/B0XXXXXX
  python debug_deal_selectors.py https://www.amazon.it/dp/B0XXXXXX
  python debug_deal_selectors.py https://www.amazon.es/dp/B0XXXXXX

QUANDO USAR:
  Rode contra um produto que você sabe que tem um "Limited Time Deal"
  ou cupom ativo na Amazon FR/IT/ES. O script vai:
  1. Abrir a página no Chrome
  2. Testar todos os seletores candidatos
  3. Imprimir quais encontraram conteúdo
  4. Exportar o HTML relevante para inspecção manual
"""
import sys
import json
import time
from pathlib import Path
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

# Seletores candidatos para LTD
LTD_CANDIDATES = [
    ('ID',           'dealBadgeSupportingText'),             # atual (funciona no DE)
    ('ID',           'deal-badge-msg'),
    ('XPATH',        '//div[@id="dealBadgeDisplayFeature_feature_div"]//span[contains(@class,"a-color-price")]'),
    ('XPATH',        '//div[@id="dealBadgeDisplayFeature_feature_div"]//span[contains(@class,"a-text-bold")]'),
    ('XPATH',        '//div[@id="dealBadgeDisplayFeature_feature_div"]'),
    ('XPATH',        '//span[contains(@class,"deal-badge")]'),
    ('CSS_SELECTOR', '#dealBadgeDisplayFeature_feature_div'),
    ('CSS_SELECTOR', '.dealBadge'),
    ('CSS_SELECTOR', '[data-feature-name="dealBadge"]'),
    ('XPATH',        '//div[@id="limitedTimeDealLabel_feature_div"]'),
    ('XPATH',        '//span[@id="deal-badge-label"]'),
]

# Seletores candidatos para Coupon
COUPON_CANDIDATES = [
    ('CSS_SELECTOR', '.promoPriceBlockMessage'),              # atual
    ('ID',           'couponBadgeRegular'),
    ('CSS_SELECTOR', '#couponBadgeRegular'),
    ('CSS_SELECTOR', '.coupon-badge'),
    ('XPATH',        '//div[@id="couponBadgeDisplayFeature_feature_div"]'),
    ('XPATH',        '//span[contains(@class,"coupon")]'),
    ('CSS_SELECTOR', '[data-feature-name="couponBadge"]'),
    ('XPATH',        '//div[@id="promoPriceBlockMessage_feature_div"]'),
]

BY_MAP = {
    'ID': By.ID,
    'XPATH': By.XPATH,
    'CSS_SELECTOR': By.CSS_SELECTOR,
}


def test_selectors(driver, candidates, label):
    print(f'\n{"="*60}')
    print(f'  {label}')
    print(f'{"="*60}')
    found = []
    for by_str, value in candidates:
        try:
            el = driver.find_element(BY_MAP[by_str], value)
            text = el.text.strip()
            html = el.get_attribute('outerHTML')[:300]
            status = 'FOUND' if text else 'FOUND (empty text)'
            print(f'  ✅ {status}: ({by_str}) {value}')
            if text:
                print(f'     text: {repr(text)}')
            print(f'     html: {html[:200]}')
            found.append({'by': by_str, 'value': value, 'text': text, 'html': html})
        except NoSuchElementException:
            print(f'  ✗  not found: ({by_str}) {value}')
        except Exception as e:
            print(f'  ?  error: ({by_str}) {value} — {e}')
    return found


def dump_deal_area_html(driver, output_path):
    deal_container_ids = [
        'dealBadgeDisplayFeature_feature_div',
        'couponBadgeDisplayFeature_feature_div',
        'promoPriceBlockMessage_feature_div',
        'limitedTimeDealLabel_feature_div',
        'corePriceDisplay_desktop_feature_div',
    ]
    html_out = []
    for elem_id in deal_container_ids:
        try:
            el = driver.find_element(By.ID, elem_id)
            html_out.append(f'\n<!-- {elem_id} -->\n{el.get_attribute("outerHTML")}')
        except NoSuchElementException:
            html_out.append(f'\n<!-- {elem_id}: NOT FOUND -->')

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f'<!-- URL: {driver.current_url} -->\n')
        f.write('\n'.join(html_out))
    print(f'\n💾 HTML exportado para: {output_path}')


def main():
    if len(sys.argv) < 2:
        print('Uso: python debug_deal_selectors.py <URL>')
        print('Ex:  python debug_deal_selectors.py https://www.amazon.fr/dp/B0XXXXXX')
        sys.exit(1)

    url = sys.argv[1]
    print(f'\n🔍 Diagnosticando seletores para: {url}')

    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    driver = uc.Chrome(options=options)

    try:
        driver.get(url)
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        time.sleep(3)

        print(f'\n📌 URL final: {driver.current_url}')
        print(f'   Título: {driver.title[:80]}')

        ltd_found   = test_selectors(driver, LTD_CANDIDATES,    'LIMITED TIME DEAL — candidatos')
        coup_found  = test_selectors(driver, COUPON_CANDIDATES, 'COUPON — candidatos')

        # Exporta HTML para inspeção manual
        html_path = Path(__file__).parent / 'debug_deal_output.html'
        dump_deal_area_html(driver, html_path)

        print('\n' + '='*60)
        print('  RESUMO — adicionar ao mae_config.json:')
        print('='*60)
        if ltd_found:
            best = next((x for x in ltd_found if x['text']), ltd_found[0])
            print(f'  limited_time_deal: {{"by": "{best["by"]}", "value": "{best["value"]}"}}'
                  f'  →  "{best["text"]}"')
        else:
            print('  limited_time_deal: NENHUM SELETOR ENCONTROU — produto não tem LTD ativo?')
        if coup_found:
            best = next((x for x in coup_found if x['text']), coup_found[0])
            print(f'  coupon:            {{"by": "{best["by"]}", "value": "{best["value"]}"}}'
                  f'  →  "{best["text"]}"')
        else:
            print('  coupon:            NENHUM SELETOR ENCONTROU — produto não tem cupom ativo?')

    finally:
        input('\nPressione Enter para fechar o browser...')
        driver.quit()


if __name__ == '__main__':
    main()