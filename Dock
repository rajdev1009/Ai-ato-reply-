# Python 3.10 image use karenge (Stable)
FROM python:3.10-slim

# Work directory set karein
WORKDIR /app

# System tools install karein (Audio processing ke liye zaroori)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Requirements copy aur install karein
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Saara code copy karein
COPY . .

# Port expose karein
EXPOSE 8000

# Bot start karne ka command
CMD ["python", "main.py"]
