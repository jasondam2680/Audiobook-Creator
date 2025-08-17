# Audiobook-Creator
Tool bán thủ công chuyển wattpad thành audiobook 0ffline
# 🌐 Web App Quick Start Guide

## 📥 Bước 1: Download và Setup

```bash
# Tạo thư mục và cd vào
mkdir wattpad-audiobook-webapp && cd wattpad-audiobook-webapp

# Copy các file code từ artifacts:
# 1. web_app.py (Flask Backend Server)
# 2. index.html vào thư mục templates/
# 3. thêm cookies.json

# Cài đặt dependencies
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install flask flask-socketio selenium beautifulsoup4 webdriver-manager edge-tts eventlet
```

## 🚀 Bước 2: Chạy ứng dụng

```bash
python web_app.py
```

**Truy cập:** http://localhost:5006
