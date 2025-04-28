import os
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError
from dotenv import load_dotenv
import requests
import asyncio
import logging

load_dotenv()
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, api_url: str):
        self.token = os.getenv('TELEGRAM_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.topic_id = int(os.getenv('TELEGRAM_TOPIC_ID', 0))
        self.api_url = api_url
        self.application = None
        
        logger.info(f"Инициализация бота с параметрами:")
        logger.info(f"TELEGRAM_TOKEN установлен: {'Да' if self.token else 'Нет'}")
        logger.info(f"TELEGRAM_CHAT_ID установлен: {'Да' if self.chat_id else 'Нет'}")
        logger.info(f"TELEGRAM_TOPIC_ID: {self.topic_id}")
        logger.info(f"API_URL: {self.api_url}")
        
        if not all([self.token, self.chat_id]):
            logger.error("Не установлены TELEGRAM_TOKEN или TELEGRAM_CHAT_ID")
            return
            
        try:
            self.application = Application.builder().token(self.token).build()
            self._setup_handlers()
            logger.info(f"Бот инициализирован с chat_id={self.chat_id} и topic_id={self.topic_id}")
        except TelegramError as e:
            logger.error(f"Ошибка инициализации Telegram бота: {e}")

    def _setup_handlers(self):
        """Настройка обработчиков команд"""
        self.application.add_handler(CommandHandler("price", self._handle_price_command))
        logger.info("Обработчики команд настроены")

    async def _handle_price_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /price"""
        logger.info(f"Получена команда /price от пользователя {update.effective_user.id}")
        logger.info(f"Сообщение отправлено в теме: {update.effective_message.is_topic_message}")
        if update.effective_message.is_topic_message:
            logger.info(f"ID темы: {update.effective_message.message_thread_id}")
        
        try:
            response = requests.get(f"{self.api_url}/current_price")
            logger.info(f"Ответ API: статус={response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                message = (
                    f"💰 <b>Текущая цена PLEX</b>\n"
                    f"┣ Цена: {data['price']:,.2f} {data['currency']}\n"
                    f"┣ Локация: {data['location']}\n"
                    f"┗ Обновлено: {data['timestamp']}"
                )
            else:
                message = "⚠️ Не удалось получить текущую цену"
                logger.warning(f"Не удалось получить цену: {response.text}")
            
            await self._reply_to(update, message)
        except Exception as e:
            logger.error(f"Ошибка при обработке команды /price: {e}", exc_info=True)
            await self._reply_to(update, f"❌ Ошибка: {str(e)}")

    async def _reply_to(self, update: Update, text: str):
        """Отправка ответа на сообщение"""
        try:
            params = {
                'chat_id': update.effective_chat.id,
                'text': text,
                'parse_mode': 'HTML'
            }
            
            if update.effective_message.is_topic_message:
                thread_id = update.effective_message.message_thread_id
                params['message_thread_id'] = thread_id
                logger.info(f"Отправляю ответ в тему {thread_id}")
            
            await self.application.bot.send_message(**params)
            logger.info("Сообщение успешно отправлено")
        except Exception as e:
            logger.error(f"Ошибка при отправке ответа: {e}", exc_info=True)

    def is_connected(self):
        return self.application is not None

    async def send_message(self, text: str):
        if not self.is_connected():
            return False
            
        try:
            params = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': 'HTML'
            }
            
            if self.topic_id:
                params['message_thread_id'] = self.topic_id
                logger.info(f"Отправляю сообщение в тему {self.topic_id}")
                
            await self.application.bot.send_message(**params)
            logger.info("Сообщение успешно отправлено")
            return True
        except TelegramError as e:
            logger.error(f"Ошибка отправки сообщения в Telegram: {e}", exc_info=True)
            return False

    async def start(self):
        """Запуск бота"""
        if not self.application:
            return
            
        try:
            # Отправляем приветственное сообщение
            await self.send_message("🚀 Мониторинг PLEX запущен!\n"
                                  "Используйте /price для текущей цены")
            # Запускаем поллинг без блокировки
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            logger.info("Бот успешно запущен")
        except Exception as e:
            logger.error(f"Ошибка при запуске бота: {e}", exc_info=True)

    async def stop(self):
        """Остановка бота"""
        if self.application:
            try:
                await self.application.stop()
                await self.application.shutdown()
                logger.info("Бот успешно остановлен")
            except Exception as e:
                logger.error(f"Ошибка при остановке бота: {e}", exc_info=True)