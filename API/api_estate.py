import requests
import base64
import time
from datetime import datetime
import pandas as pd
import logging
import traceback

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('parser.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

try:
    logger.info('Начало парсинга')

    token = 'p-C8r_zsBqBv8jR8R_yI24SNWs6pESLo'
    key = base64.b64encode(f'{token}:'.encode()).decode()

    headers = {
        'Accept': 'application/json',
        'Authorization': f'Basic {key}'
    }

    url_category = 'https://inpars.ru/api/v2/estate/section'
    logger.info(f'Запрос категорий: {url_category}')
    response_category = requests.get(url_category, headers=headers, timeout=30)
    response_category.raise_for_status()
    data_category = response_category.json()
    real_data_category = data_category.get('data', [])
    categroy = pd.DataFrame(real_data_category)
    logger.info(f'Получено категорий: {len(categroy)}')

    url_city = 'https://inpars.ru/api/v2/region'
    logger.info(f'Запрос регионов: {url_city}')
    response_city = requests.get(url_city, headers=headers, timeout=30)
    response_city.raise_for_status()
    data_city = response_city.json()
    real_data_city = data_city.get('data', [])
    city = pd.DataFrame(real_data_city)
    logger.info(f'Получено регионов: {len(city)}')

    url = 'https://inpars.ru/api/v2/estate'
    params = {
        'expand': 'region,city,type,section,category,metro,material,rentTime,isNew,rooms,history,phoneProtected,parseId',
        'limit': 1000,
        'regionId': 77,
        'sectionId': 1,
        'sortBy': 'updated_asc'
    }

    all_estates = []
    cycle = 0

    while True:
        cycle += 1
        logger.info(f'Цикл #{cycle} | Параметры: {params}')
        response = requests.get(url, headers=headers, params=params)
        logger.info(f'Статус: {response.status_code}')

        if response.status_code != 200:
            logger.error(f'Ошибка запроса: {response.status_code}')
            break

        data = response.json()
        estates = data.get('data', [])

        if not estates:
            logger.info('Нет данных, завершение парсинга.')
            break

        all_estates.extend(estates)
        logger.info(f'Получено: {len(estates)} | Всего: {len(all_estates)}')

        last_estate = estates[-1]
        updated_str = last_estate.get('updated')

        try:
            dt = datetime.fromisoformat(updated_str)
            timestamp = int(dt.timestamp())
            params['timeStart'] = timestamp + 1
            logger.info(f'Следующий timeStart: {params['timeStart']}')
        except Exception as e:
            logger.warning(f'Ошибка обработки даты: {updated_str} ({e})')
            break

        time.sleep(6)

    df = pd.DataFrame(all_estates)
    df = df[['title', 'address', 'floor', 'floors', 'sq', 'sqLand', 'sqKitchen', 'cost',
             'lat', 'lng', 'name', 'source', 'created', 'region', 'city', 'type',
             'section', 'category', 'metro', 'material', 'rooms', 'sqLiving']]
    df.to_excel('final.xlsx', index=False)
    logger.info(f'Сохранено {len(df)} объявлений → final.xlsx')

except Exception as e:
    logger.error(f'Ошибка: {e}')
    logger.error(traceback.format_exc())

finally:
    logger.info('Парсинг завершён')
