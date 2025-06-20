# Базовый образ Python
FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libssl-dev \
    pkg-config \
 && rm -rf /var/lib/apt/lists/*

# Установка Rust (используется для сборки некоторых Python-зависимостей)
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:$PATH"

# Создание рабочей директории
WORKDIR /app

# Копируем только зависимости сначала (для лучшего кэширования)
COPY requirements.txt .

# Установка Python-зависимостей
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Копируем остальной код
COPY . .

# Принудительный небуферизированный режим для логов
ENV PYTHONUNBUFFERED=1

# Запуск бота
CMD ["python", "-u", "bot2.py"]