FROM python:3.10-slim

# 安装浏览器和驱动
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# 设置环境变量
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROME_PATH=/usr/lib/chromium/

WORKDIR /app
COPY . .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 启动脚本
CMD ["python", "main.py"]
