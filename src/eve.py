import aiohttp
import asyncio
from datetime import datetime
from bot import TelegramBot
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PLEXMonitor:
  def __init__(self, telegram_bot: TelegramBot):
    self.interval = 900
    self.active = True
    self.last_price = None
    self.bot = telegram_bot
    self.session = None
    logger.info(f"Инициализация PLEXMonitor с интервалом {self.interval} секунд")

  async def get_plex_order(self):
    """Получить текущую цену PLEX в Jita"""
    logger.info("Начало запроса цены PLEX")
    if not self.session:
      logger.info("Создание новой сессии aiohttp")
      self.session = aiohttp.ClientSession()
      
    url = "https://esi.evetech.net/latest/markets/10000002/orders/"
    params = {
      'type_id': 44992,
      'order_type': 'sell',
      'region_id': 10000002
    }
    
    try:
      logger.info(f"Отправка запроса к EVE API: {url}")
      async with self.session.get(url, params=params, timeout=10) as response:
        logger.info(f"Получен ответ от API. Статус: {response.status}")
        response.raise_for_status()
        orders = await response.json()
        logger.info(f"Получено {len(orders)} ордеров")
        if orders:
          min_order = min(orders, key=lambda x: x['price'])
          logger.info(f"Найден ордер с минимальной ценой: {min_order['price']}")
          
          location_id = min_order['location_id']
          location_url = f"https://esi.evetech.net/latest/universe/stations/{location_id}/"
          try:
            async with self.session.get(location_url, timeout=10) as location_response:
              location_response.raise_for_status()
              location_data = await location_response.json()
              min_order['location_name'] = location_data['name']
          except Exception as e:
            logger.warning(f"Не удалось получить название локации: {e}")
            min_order['location_name'] = f"Unknown Location ({location_id})"
          
          return min_order
        else:
          logger.warning("Не получено ни одного ордера")
          return None
    except aiohttp.ClientError as e:
      error_msg = f"Ошибка сети при запросе цены PLEX: {e}"
      logger.error(error_msg, exc_info=True)
      await self.bot.send_message(f"⚠️ {error_msg}")
      return None
    except Exception as e:
      error_msg = f"Неожиданная ошибка при запросе цены PLEX: {e}"
      logger.error(error_msg, exc_info=True)
      await self.bot.send_message(f"⚠️ {error_msg}")
      return None

  async def run_monitoring(self):
    """Запуск цикла мониторинга"""
    logger.info("Запуск цикла мониторинга")
    while self.active:
      logger.info("Начало нового цикла мониторинга")
      order = await self.get_plex_order()
      timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
      
      if order is not None:
        self.last_price = order['price']
        message = (
          f"💰 <b>Текущая цена PLEX</b>\n"
          f"┣ Цена: {order['price']:,.2f} ISK\n"
          f"┣ Локация: {order['location_name']}\n"
          f"┗ Обновлено: {timestamp}"
        )
        logger.info(f"Отправка сообщения в Telegram: {message}")
        await self.bot.send_message(message)
      else:
        error_msg = f"[{timestamp}] Не удалось получить цену PLEX"
        logger.warning(error_msg)
        
      logger.info(f"Ожидание {self.interval} секунд до следующего цикла")
      await asyncio.sleep(self.interval)
    
    # Закрываем сессию при остановке мониторинга
    if self.session:
      logger.info("Закрытие сессии aiohttp")
      await self.session.close()

  async def set_interval(self, seconds: int):
    """Установка нового интервала проверки"""
    if seconds < 300:  # Минимум 5 минут
      error_msg = "Слишком частые запросы. Минимальный интервал: 5 минут"
      logger.warning(error_msg)
      raise ValueError(error_msg)
    self.interval = seconds
    logger.info(f"Установлен новый интервал: {seconds} секунд")
    await self.bot.send_message(f"🛠 Интервал обновления изменён на {seconds} секунд")