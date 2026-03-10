FROM python:3.10-slim

WORKDIR /app

# Sistemaga kerakli paketlarni o'rnatish
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt ni nusxalash va o'rnatish
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Barcha fayllarni nusxalash
COPY . .

# Telethon session fayli uchun papka yaratish
RUN mkdir -p sessions

# Botni ishga tushirish
CMD ["python", "bot.py"]