# Используем официальный Python с поддержкой Rust
FROM python:3.11-slim

# Установим зависимости для сборки
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    libssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Установка Rust
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:$PATH"

# Копируем проект
WORKDIR /app
COPY . .

# Установка зависимостей
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Запуск бота
CMD ["python", "bot2.py"]
