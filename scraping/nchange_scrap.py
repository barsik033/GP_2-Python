from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import re
import json
import pandas as pd
import time

def fetch_html(url):
    options = Options()
    options.add_argument('--headless')
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)
    driver = webdriver.Chrome(options=options)
    driver.get(url)
    time.sleep(2)
    html = driver.page_source
    driver.quit()
    return html

def parse_cian_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    data = {}
    price_elem = soup.find('div', {'data-testid': 'price-amount'})
    data['price'] = re.sub(r'[^\d]', '', price_elem.get_text(strip=True)) if price_elem else None
    metro_match = re.search(r'"undergrounds":\[\{.*?\}\]', html)
    if metro_match:
        metro_json_str = '{' + metro_match.group() + '}'
        metro_json = json.loads(metro_json_str)
        stations = []
        min_time = float('inf')
        closest_station = closest_time = ''
        for s in metro_json.get('undergrounds', []):
            name = s.get('name')
            travel_time = s.get('travelTime')
            if name and travel_time is not None:
                stations.append(f"{name}: {travel_time} мин")
                if travel_time < min_time:
                    min_time = travel_time
                    closest_station = name
                    closest_time = f"{travel_time} мин"
        data['metro_stations_list'] = ', '.join(stations) if stations else None
        data['metro_station'] = closest_station
        data['walk_time'] = closest_time
    else:
        data['metro_stations_list'] = data['metro_station'] = data['walk_time'] = None
    if not data.get('metro_station'):
        meta_desc = soup.find('meta', {'name': 'description'})
        if meta_desc:
            metro_match = re.search(r'м\.\s*([А-Яа-яёЁ\-\s]+?)[\,\.]', meta_desc['content'])
            data['metro_station'] = metro_match.group(1).strip() if metro_match else None
    if not data.get('walk_time'):
        time_match = re.search(r'(\d+)\s*мин\.?\s*(?:пешком)?', soup.get_text())
        data['walk_time'] = time_match.group(0).strip() if time_match else None
    meta_title = soup.find('meta', {'property': 'og:title'})
    if meta_title:
        content = meta_title['content']
        rooms_match = re.search(r'(\d+)-комнатная', content)
        data['rooms'] = int(rooms_match.group(1)) if rooms_match else None
        floor_match = re.search(r'этаж\s*(\d+)/(\d+)', content)
        if floor_match:
            data['floor'] = int(floor_match.group(1))
            data['floors_total'] = int(floor_match.group(2))
    patterns = {
        'square_total': r'\{"value":"([^"]+)","label":"Общая площадь"\}',
        'square_living': r'\{"value":"([^"]+)","label":"Жилая площадь"\}',
        'square_kitchen': r'\{"value":"([^"]+)","label":"Площадь кухни"\}',
        'ceiling_height': r'\{"value":"([^"]+)","label":"Высота потолков"\}',
        'wall_material': r'\{"value":"([^"]+)","label":"Тип дома"\}',
    }
    for key, pat in patterns.items():
        match = re.search(pat, html)
        if match:
            value = match.group(1).replace('\xa0', ' ').replace(',', '.')
            if key in ['square_total', 'square_living', 'square_kitchen', 'ceiling_height']:
                num_match = re.search(r'(\d+\.?\d*)', value)
                data[key] = float(num_match.group(1)) if num_match else None
            else:
                data[key] = value.strip()
    data['renovation'] = None
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        try:
            json_obj = json.loads(script.string)
            if json_obj.get('@type') == 'Product':
                desc = json_obj.get('description', '').lower()
                if 'новым ремонтом' in desc or 'новый ремонт' in desc:
                    data['renovation'] = 'Новый ремонт'
                elif 'дизайнерский ремонт' in desc:
                    data['renovation'] = 'Дизайнерский ремонт'
                elif 'евроремонт' in desc:
                    data['renovation'] = 'Евроремонт'
                elif 'ремонт' in desc:
                    data['renovation'] = 'Есть ремонт'
                break
        except:
            pass
    year_match = re.search(r'"year":(\d{4})|Год постройки[:\s]*(\d{4})', html)
    data['year_built'] = int(year_match.group(1) or year_match.group(2)) if year_match else None
    owners_match = re.search(r'Количество собственников[:\s]+(\d+)|Собственников[:\s]+(\d+)|(\d+)\s+собственник', html, re.I)
    data['owners_count'] = int(owners_match.group(1) or owners_match.group(2) or owners_match.group(3)) if owners_match else None
    infra_keywords = {'школ': 'Школы', 'детск сад': 'Детские сады', 'магазин': 'Магазины', 'торгов': 'Торговые центры'}
    infra = set()
    for kw, val in infra_keywords.items():
        if kw in html.lower():
            infra.add(val)
    data['infrastructure'] = ', '.join(infra) if infra else None
    yard_keywords = ['парковка', 'охрана', 'видеонаблюдение']
    yard = set(kw.capitalize() for kw in yard_keywords if kw in html.lower())
    data['yard_improvement'] = ', '.join(yard) if yard else None
    pub_match = re.search(r'Опубликовано[:\s]+(\d{1,2}\s+\w+\s+\d{4})|Размещено[:\s]+(\d{1,2}\s+\w+\s+\d{4})', html, re.I)
    data['publication_date'] = pub_match.group(1) or pub_match.group(2) if pub_match else None
    edit_match = re.search(r'Обновлено[:\s]+(\d{1,2}\s+\w+\s+\d{4})|Изменено[:\s]+(\d{1,2}\s+\w+\s+\d{4})', html, re.I)
    data['edit_date'] = edit_match.group(1) or edit_match.group(2) if edit_match else None
    desc_div = soup.find('div', id='description') or soup.find('div', attrs={'data-name': 'Description'})
    if desc_div:
        desc_text = ' '.join(desc_div.get_text(strip=True).split())
        data['description'] = desc_text
    else:
        data['description'] = None
    return data

urls = pd.read_csv('unique_links.csv')['url'].dropna().tolist()
data_list = []
for i, url in enumerate(urls):
    print(f"Обработка {i+1} из {len(urls)}: {url}")
    try:
        html = fetch_html(url)
        parsed_data = parse_cian_html(html)
        parsed_data['ad_id'] = int(re.search(r'/(\d+)/$', url).group(1)) if re.search(r'/(\d+)/$', url) else None
        parsed_data['url'] = url
        data_list.append(parsed_data)
        print(f"Готово: {url}")
    except Exception as e:
        print(f"Ошибка: {url} - {e}")
df = pd.DataFrame(data_list)
df.to_csv('parsed_alllinks.csv', index=False, encoding='utf-8-sig')
print("Готово и сохранено в parsed_alllinks.csv")
print(df)



#https://habr.com/ru/companies/otus/articles/596071/
#https://habr.com/ru/articles/656609/
