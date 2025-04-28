from fastapi import FastAPI, HTTPException
import asyncio
import uvicorn
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from bot import TelegramBot
from eve import PLEXMonitor
from contextlib import asynccontextmanager
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

API_URL = "http://0.0.0.0:8000"
telegram_bot = None
monitor = None
monitoring_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global telegram_bot, monitor, monitoring_task
    
    # Инициализируем сервисы
    telegram_bot = TelegramBot(API_URL)
    monitor = PLEXMonitor(telegram_bot)
    
    # Запускаем сервисы
    await telegram_bot.start()
    monitoring_task = await asyncio.create_task(monitor.run_monitoring())
    logger.info("Задача мониторинга запущена")
    
    logger.info("Приложение запущено")
    yield
    
    # Очистка при завершении
    if monitoring_task:
        monitoring_task.cancel()
        try:
            await monitoring_task
        except asyncio.CancelledError:
            pass
    if telegram_bot:
        await telegram_bot.stop()
    logger.info("Приложение остановлено")

app = FastAPI(lifespan=lifespan)

class IntervalUpdate(BaseModel):
    interval: int
    unit: Optional[str] = "seconds"

@app.get("/")
async def read_root():
    return {
        "status": "running",
        "current_interval_seconds": monitor.interval if monitor else None,
        "last_price": monitor.last_price if monitor else None,
        "telegram_connected": telegram_bot.is_connected() if telegram_bot else False
    }
  
@app.get("/current_price")
async def get_current_price():
    try:
        # Получаем свежую цену (не кэшированную)
        current_price = await monitor.get_plex_price()
        
        if current_price is None:
            raise HTTPException(
                status_code=503,
                detail="Не удалось получить текущую цену PLEX"
            )
            
        return {
            "price": current_price,
            "currency": "ISK",
            "timestamp": datetime.now().isoformat(),
            "location": "Jita",
            "source": "EVE ESI API"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при запросе цены: {str(e)}"
        )

@app.post("/set_interval/")
async def set_interval(update: IntervalUpdate):
    if update.interval <= 0:
        raise HTTPException(status_code=400, detail="Интервал должен быть положительным числом")
    
    # Конвертация единиц измерения
    multiplier = 1
    if update.unit == "minutes":
        multiplier = 60
    elif update.unit == "hours":
        multiplier = 3600
    
    new_interval = update.interval * multiplier
    
    try:
        await monitor.set_interval(new_interval)
        return {"message": f"Интервал обновления изменён на {new_interval} секунд"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)