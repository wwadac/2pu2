import os
from dotenv import load_dotenv

# Загружаем переменные окружения один раз
load_dotenv()

# Токен бота от @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Папка для хранения датасетов
DATASETS_FOLDER = "datasets"

# Создаём папку если не существует
os.makedirs(DATASETS_FOLDER, exist_ok=True)
