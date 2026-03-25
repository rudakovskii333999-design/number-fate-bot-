FROM python:3.11-slim

WORKDIR /app

# Копируем файлы с зависимостями
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь остальной код
COPY . .

# Запускаем бота
CMD ["python", "bot.py"]
