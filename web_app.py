#!/usr/bin/env python3
# web_app.py: Phiên bản nâng cấp, xử lý trang Mature của Wattpad.

import os
import sys
import time
import re
import json
import asyncio
import threading
from urllib.parse import urlparse, urljoin

from flask import Flask, render_template, request, jsonify, send_from_directory
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager
import edge_tts

# --- CẤU HÌNH FLASK ---
app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'audio_outputs')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
COOKIE_FILE = "cookies.json"

task_status = {
    "status": "Sẵn sàng",
    "progress": 0,
    "is_done": False,
    "file_url": None,
    "error": None
}

# --- LOGIC CỐT LÕI ---

def _load_cookies_from_file(driver, cookie_file, base_url):
    global task_status
    try:
        with open(cookie_file, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        driver.get(base_url)
        for c in cookies:
            if "name" in c and "value" in c:
                driver.add_cookie(c)
        task_status["status"] = f"Đã load cookie. Thực hiện với phiên đăng nhập..."
    except FileNotFoundError:
        task_status["status"] = f"Không tìm thấy file '{cookie_file}'. Chạy ở chế độ khách."
    except Exception as e:
        task_status["status"] = f"Lỗi khi load cookie: {e}"

def _create_driver(headless=True):
    opts = Options()
    if headless: opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu"); opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage"); opts.add_argument("window-size=1200x900")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=opts)

def _scrape_text_from_url(url):
    global task_status
    base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    driver = _create_driver(headless=True)
    all_texts = []
    
    is_wattpad = "wattpad.com" in base_url
    
    try:
        _load_cookies_from_file(driver, COOKIE_FILE, base_url)
        driver.get(url)
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # --- NÂNG CẤP: XỬ LÝ TRANG NỘI DUNG NGƯỜI LỚN ---
        if is_wattpad:
            try:
                # Chờ nút đồng ý xuất hiện và nhấn vào nó
                agree_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.css-1aa7g42")))
                agree_button.click()
                task_status["status"] = "Đã xác nhận nội dung người lớn. Đang chờ tải trang..."
                time.sleep(3) # Chờ trang tải lại nội dung
            except Exception:
                # Bỏ qua nếu không tìm thấy nút, có thể đây là truyện thông thường
                pass
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        chapter_urls = [url]
        if is_wattpad and soup.select_one("ul.story-parts"):
            links = [urljoin(base_url, a["href"]) for a in soup.find_all("a", href=True) if re.search(r'/\d+-[a-zA-Z0-9-]+', a["href"]) and '/story/' in a["href"]]
            chapter_urls = sorted(list(set(links)))
            task_status["status"] = f"Tìm thấy {len(chapter_urls)} chương. Bắt đầu tải..."

        for idx, ch_url in enumerate(chapter_urls, start=1):
            if len(chapter_urls) > 1:
                task_status["status"] = f"[1/2] Đang tải chương {idx}/{len(chapter_urls)}..."
            else:
                task_status["status"] = "[1/2] Đang tải nội dung trang..."
            
            driver.get(ch_url)
            last_height = driver.execute_script("return document.body.scrollHeight")
            while True:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height: break
                last_height = new_height
            
            soup_ch = BeautifulSoup(driver.page_source, "html.parser")
            
            # --- NÂNG CẤP: LOGIC TÌM NỘI DUNG LINH HOẠT HƠN ---
            text_content_el = None
            selectors_to_try = [
                "div[data-test='story-text']", # Wattpad
                "#content",                  # tt1069 và các trang tương tự
                ".chapter-content",          # Các trang khác
                "article",                   # Fallback
            ]
            for selector in selectors_to_try:
                text_content_el = soup_ch.select_one(selector)
                if text_content_el:
                    break # Dừng lại khi tìm thấy selector đầu tiên hoạt động

            if text_content_el:
                title = soup_ch.find(["h1", "h2", "h3"])
                header = f"\n\n----- CHƯƠNG {idx}: {title.get_text(strip=True) if title else ''} -----\n"
                all_texts.append(header + text_content_el.get_text("\n", strip=True))
            else:
                # --- NÂNG CẤP: LƯU FILE DEBUG KHI THẤT BẠI ---
                with open("debug_page.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                raise ValueError("Không tìm thấy nội dung truyện với các selector đã thử. Vui lòng kiểm tra file debug_page.html")
    finally:
        driver.quit()
    return "\n".join(all_texts)

async def _convert_text_to_audio(text, voice_id, output_path):
    global task_status
    task_status["status"] = "[2/2] Đang chuyển đổi văn bản thành audio..."
    communicate = edge_tts.Communicate(text, voice_id)
    with open(output_path, "wb") as file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                task_status["progress"] = (chunk["offset"] / len(text)) * 100

def background_task(url, voice_id, filename):
    global task_status
    try:
        story_text = _scrape_text_from_url(url)
        if not story_text or len(story_text) < 50:
            raise ValueError("Không tải được nội dung truyện hoặc nội dung quá ngắn.")
        
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        asyncio.run(_convert_text_to_audio(story_text, voice_id, output_path))

        task_status["status"] = "Hoàn thành!"
        task_status["file_url"] = f"/download/{filename}"
    except Exception as e:
        task_status["status"] = f"Lỗi: {e}"
        task_status["error"] = str(e)
    finally:
        task_status["is_done"] = True

# --- CÁC ROUTE CỦA FLASK (Không thay đổi) ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_task', methods=['POST'])
def start_task():
    global task_status
    task_status = {"status": "Đang khởi tạo...", "progress": 0, "is_done": False, "file_url": None, "error": None}
    url = request.form['url']
    voice_id = request.form['voice']
    safe_name = re.sub(r'[^a-zA-Z0-9\-_]', '', url.split('/')[-1])[:50]
    filename = f"{safe_name or 'audiobook'}.mp3"
    thread = threading.Thread(target=background_task, args=(url, voice_id, filename))
    thread.daemon = True
    thread.start()
    return jsonify({"status": "started"})

@app.route('/task_status')
def task_status_route():
    return jsonify(task_status)

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    print(">>> Mở trình duyệt và truy cập vào http://127.0.0.1:5006 <<<")
    app.run(host='0.0.0.0', port=5006)