# 🅿 SmartPark — AI-Powered Smart Parking System

A full-stack parking management system with **YOLOv8 AI Vision** and **LSTM demand prediction**.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🤖 **YOLOv8 AI Vision** | Upload parking lot images → detects cars/bikes/trucks, marks slots free/occupied |
| 📈 **LSTM Predictions** | Forecasts booking demand for the next 6 hours |
| 🗺 **Live Slot Map** | Real-time dashboard showing all parking slots (A/B/C zones) |
| 🚗 **Vehicle Management** | Register multiple vehicles per user |
| 💳 **Wallet System** | Pre-paid parking credits |
| 📱 **QR Codes** | Auto-generated QR per booking |
| 🔐 **JWT Auth** | Secure cookie-based login |

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.11+
- PostgreSQL (create a database named `smart_parking`)

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
Edit `.env`:
```
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/smart_parking
SECRET_KEY=generate-a-strong-secret-key
DISPLAY_TIMEZONE=Asia/Kolkata
```

### 4. Run the server
```bash
uvicorn app.main:app --reload --port 8000
```

Open: **http://localhost:8000**

---

## 📁 Project Structure

```
├── app/
│   ├── main.py                  # FastAPI app factory
│   ├── models.py                # SQLAlchemy models
│   ├── ml_models/
│   │   ├── best.pt              # YOLOv8 trained weights  ← YOUR MODEL
│   │   ├── lstm_model.h5        # LSTM demand model
│   │   ├── scaler_X.pkl
│   │   └── scaler_y.pkl
│   ├── routers/
│   │   ├── auth.py              # Login / Register / Logout
│   │   ├── user_features.py     # Dashboard, Vehicles, Wallet
│   │   ├── bookings.py          # Book slot, Exit
│   │   ├── predictions.py       # LSTM forecast API + page
│   │   ├── yolo_detect.py       # 🤖 YOLOv8 detection API  ← NEW
│   │   └── extra_pages.py       # AI Vision page, History   ← NEW
│   └── services/
│       ├── prediction_service.py
│       ├── booking_logic.py
│       └── qr_service.py
├── templates/                   # Jinja2 HTML templates    ← NEW
│   ├── base.html
│   ├── dashboard.html           # Main dashboard with AI prediction widget
│   ├── ai_vision.html           # YOLOv8 live detection page
│   ├── predictions.html         # LSTM charts
│   └── ...
├── static/                      # CSS + JS                  ← NEW
│   ├── css/style.css
│   └── js/app.js
└── requirements.txt
```

---

## 🤖 AI Vision — How It Works

1. Navigate to **AI Vision** in the sidebar
2. Upload any parking lot photograph
3. The backend runs `best.pt` (your trained YOLOv8 weights)
4. Detected vehicles: **car**, **motorcycle**, **truck**, **bus**
5. 8 predefined slot regions are checked for IoU overlap → **Free** / **Occupied**
6. Results shown as annotated image + slot grid + detection list

> **Note:** If `ultralytics` is not installed or `best.pt` is missing, the API falls back to realistic mock detections so the UI still works.

---

## 📊 Dashboard AI Widget

The dashboard shows a live **6-hour demand forecast** card that:
- Calls `/predictions` API (LSTM + regression blend)
- Renders bar chart + colour-coded demand rows (High / Low)
- Updates every page load (cached 5 min server-side)

---

## 🔑 Default Pricing (configurable in `.env`)
- ₹50 / hour base rate
- ₹2 / minute overrun charge
- Warning notification 10 min before expiry
