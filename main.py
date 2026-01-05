import os
import time
import sys
import requests
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# ========= 1. Web 存活服务器 (用于欺骗 Koyeb 健康检查) =========
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Zampto Autorenew Bot is running...")

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"🟢 Web 存活服务已启动，监听端口: {port}")
    server.serve_forever()

# ========= 2. Telegram 通知函数 =========
def tg_send(text, photo=None):
    token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")
    if not token or not chat_id:
        print("⚠️ 未配置 TG 通知环境变量")
        return
    try:
        if photo:
            url = f"https://api.telegram.org/bot{token}/sendPhoto"
            with open(photo, "rb") as f:
                requests.post(url, data={"chat_id": chat_id, "caption": text, "parse_mode": "HTML"}, files={"photo": f}, timeout=20)
        else:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.post(url, data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        print(f"❌ TG 发送失败: {e}")

# ========= 3. 核心续期逻辑 =========
def mask(email):
    return email[:3] + "***" if email else "Unknown"

def run_renew_task():
    raw = os.getenv("ZAMPTO_ACCOUNTS")
    if not raw:
        print("❌ 错误: 未设置 ZAMPTO_ACCOUNTS 环境变量")
        return

    accounts = []
    try:
        for item in raw.split(";"):
            if "|" in item:
                email, pwd, sid = item.split("|")
                accounts.append((email.strip(), pwd.strip(), sid.strip()))
    except Exception as e:
        print(f"❌ 账号格式解析失败: {e}")
        return

    # Chrome 配置
    options = Options()
    options.binary_location = "/usr/bin/chromium"
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1200,800")
    service = Service("/usr/bin/chromedriver")

    print(f"🚀 启动续期任务，共 {len(accounts)} 个账号")

    for idx, (email, password, server_id) in enumerate(accounts, 1):
        print(f"👤 [{idx}/{len(accounts)}] 处理账号: {mask(email)}")
        driver = None
        success = False
        shot_path = None

        try:
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(30)

            # 登录
            driver.get("https://dash.zampto.net/login")
            time.sleep(5)
            driver.find_element("name", "email").send_keys(email)
            driver.find_element("name", "password").send_keys(password)
            driver.find_element("css selector", "button[type=submit]").click()
            time.sleep(8)

            if "login" in driver.current_url.lower():
                raise RuntimeError("登录验证失败，请检查账号密码")

            # 续期
            renew_url = f"https://dash.zampto.net/server?id={server_id}&renew=true"
            driver.get(renew_url)
            time.sleep(10)
            
            success = True
            ts = datetime.now().strftime("%H%M%S")
            shot_path = f"success_{idx}_{ts}.png"
            driver.save_screenshot(shot_path)

        except Exception as e:
            print(f"❌ 账号 {mask(email)} 续期异常: {e}")
            if driver:
                shot_path = f"error_{idx}.png"
                driver.save_screenshot(shot_path)
        finally:
            if driver:
                driver.quit()

        # 发送通知
        status_emoji = "✅" if success else "❌"
        msg = f"{status_emoji} <b>Zampto 续期结果</b>\n👤 账号：{mask(email)}\n⏰ 时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}"
        tg_send(msg, photo=shot_path if shot_path and os.path.exists(shot_path) else None)
        
        # 清理截图文件
        if shot_path and os.path.exists(shot_path):
            os.remove(shot_path)
        
        time.sleep(10) # 账号间间隔

# ========= 4. 程序入口 =========
if __name__ == "__main__":
    # 启动 Web 服务 (后台线程)
    t = threading.Thread(target=run_web_server, daemon=True)
    t.start()

    # 主循环
    while True:
        run_renew_task()
        # 修改为 40 小时执行一次 (40 * 3600 = 144000)
        print("💤 本轮任务结束，等待 40 小时后进行下一轮续期...")
        time.sleep(144000)
