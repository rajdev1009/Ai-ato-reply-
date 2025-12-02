FROM python:3.10-slim

# 1. Logs ko turant dikhane ke liye ye zaroori hai
ENV PYTHONUNBUFFERED=1

# 2. FFmpeg install (Audio handling ke liye best hai)
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

# 3. Yahan dhyaan dena: Tumhari python file ka naam 'main.py' hona chahiye
CMD ["python", "main.py"]
