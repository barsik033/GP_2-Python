import os, sys, time, random, logging
import pandas as pd
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

start_urls = [
    'https://www.cian.ru/cat.php?deal_type=sale&district%5B0%5D=325&engine_version=2&object_type%5B0%5D=1&offer_type=flat&p=54',
    'https://www.cian.ru/cat.php?deal_type=sale&district%5B0%5D=1&engine_version=2&object_type%5B0%5D=1&offer_type=flat&p=2&region=1',
    'https://www.cian.ru/cat.php?deal_type=sale&district%5B0%5D=5&engine_version=2&object_type%5B0%5D=1&offer_type=flat&p=54',
    'https://www.cian.ru/cat.php?deal_type=sale&district%5B0%5D=5&district%5B1%5D=6&engine_version=2&object_type%5B0%5D=1&offer_type=flat&p=54',
    'https://www.cian.ru/cat.php?deal_type=sale&engine_version=2&object_type%5B0%5D=1&offer_type=flat&p=54&region=1',
    'https://www.cian.ru/cat.php?deal_type=sale&district%5B0%5D=4&engine_version=2&object_type%5B0%5D=1&offer_type=flat&p=54',
    'https://www.cian.ru/cat.php?deal_type=sale&district%5B0%5D=4&district%5B1%5D=7&engine_version=2&object_type%5B0%5D=1&offer_type=flat&p=54',
    'https://www.cian.ru/cat.php?deal_type=sale&engine_version=2&object_type%5B0%5D=1&offer_type=flat&p=54&region=1',
    'https://www.cian.ru/cat.php?deal_type=sale&district%5B0%5D=9&engine_version=2&object_type%5B0%5D=1&offer_type=flat&p=54',
    'https://www.cian.ru/cat.php?deal_type=sale&district%5B0%5D=8&engine_version=2&object_type%5B0%5D=1&offer_type=flat&p=54',
]

pages_begin = 1
pages_end   = 54
out_all    = 'all_links.csv'
log_file   = '../cian_multi.log'

logger = logging.getLogger('cian_multi')
logger.setLevel(logging.INFO)
fmt = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', '%Y-%m-%d %H:%M:%S')
fh = logging.FileHandler(log_file, encoding='utf-8'); fh.setFormatter(fmt)
sh = logging.StreamHandler(sys.stdout);              sh.setFormatter(fmt)
logger.addHandler(fh); logger.addHandler(sh)


def init_driver(headless=False):
    opts = Options()
    if headless:
        opts.add_argument('--headless=new')

    opts.add_argument('--window-size=1920,1080')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    opts.add_argument('--disable-gpu')
    opts.add_argument('--lang=ru-RU')
    opts.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36')

    return webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=opts)


def set_query_param(url, key, value):
    u = urlparse(url)
    q = parse_qs(u.query, keep_blank_values=True)
    q[key] = [str(value)]
    new_q = urlencode(q, doseq=True)

    return urlunparse((u.scheme, u.netloc, u.path, u.params, new_q, u.fragment))


def close_banners(driver):
    for txt in ('Принять', 'Соглас', 'Ок', 'Хорошо'):
        try:
            driver.find_element(By.XPATH, f'//button[contains(translate(.,"ЁёЙй", "ЕеЙй"), "{txt}")]').click()
            time.sleep(0.2); break
        except:
            pass
    for sel in ('button[aria-label*="закрыть"]', 'button[data-name*="close"]'):
        try:
            driver.find_element(By.CSS_SELECTOR, sel).click(); time.sleep(0.2)
        except:
            pass


def soft_scroll(driver, steps=8, pause=0.35):
    for _ in range(steps):
        driver.execute_script('window.scrollBy(0, document.body.scrollHeight/6);')
        time.sleep(pause)


def parse_links_from_source(html):
    soup = BeautifulSoup(html, 'html.parser')
    links = [a.get('href') for a in soup.select('article[data-name="CardComponent" a[href*="/sale/flat/"]') if a.get('href')]
    if not links:
        links = [a.get('href') for a in soup.select('a[href^="https://www.cian.ru/sale/flat/"]')]

    seen, out = set(), []
    for u in links:
        if u and u not in seen:
            seen.add(u); out.append(u)

    return out


def save_csv(paths, fname, reason=""):
    try:
        pd.DataFrame({'url': list(paths)}).to_csv(fname, index=False, encoding='utf-8-sig')
        logger.info('💾 Сохранено %d ссылок → %s (%s)', len(paths), fname, reason)
    except Exception as e:
        logger.error('Ошибка сохранения %s: %s', fname, e)


def main():
    start_ts = time.time()
    driver = init_driver(headless=False)
    wait = WebDriverWait(driver, 20)

    all_links = set()
    if os.path.exists(out_all):
        try:
            df0 = pd.read_csv(out_all)
            for u in df0['url']:
                all_links.add(u)
            logger.info('🔁 Подгружено %d ссылок из %s', len(all_links), out_all)
        except Exception as e:
            logger.warning('Не удалось прочитать %s: %s', out_all, e)

    try:
        for idx, base_url in enumerate(start_urls, start=1):
            logger.info('=== Район %d/%d ===', idx, len(start_urls))
            district_links = set()

            for p in range(pages_begin, pages_end + 1):
                page_url = set_query_param(base_url, 'p', p)
                logger.info('[р-%d стр-%d] %s', idx, p, page_url)

                driver.get(page_url)
                close_banners(driver)

                try:
                    wait.until(EC.any_of(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'article[data-name="CardComponent"]')),
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="/sale/flat/"]'))
                    ))
                except Exception:
                    logger.warning('Карточки не появились по ожиданию — продолжаю')

                soft_scroll(driver, steps=10, pause=0.35)
                links = parse_links_from_source(driver.page_source)

                before_d = len(district_links)
                before_all = len(all_links)
                for u in links:
                    district_links.add(u)
                    all_links.add(u)

                logger.info('  +%d (район %d итого: %d) | +%d (всего: %d)',
                            len(district_links) - before_d, idx, len(district_links),
                            len(all_links) - before_all, len(all_links))

                time.sleep(0.7 + random.random()*0.6)

            fname = f'links_district_{idx}.csv'
            save_csv(district_links, fname, reason='по завершении района')
            save_csv(all_links, out_all, reason='обновлён общий')

        logger.info('✅ Готово. Всего уникальных ссылок: %d', len(all_links))

    except Exception as e:
        logger.exception('💥 Сбой в работе: %s', e)
        save_csv(all_links, out_all, reason='автосейв при ошибке')
    finally:
        driver.quit()
        logger.info('⏱️ Время: %.1f мин.', (time.time() - start_ts)/60)


if __name__ == '__main__':
    main()

