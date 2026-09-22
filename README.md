# Ichimoku Multi-Market Auto Trader

Full-stack paper-first Ichimoku trading platform for US/Nasdaq stocks and an extensible NSE adapter.

## Safety defaults
- PAPER_TRADING=true
- AUTO_TRADING=false
- EMERGENCY_STOP=true
- API credentials are server-side only.

## Components
FastAPI backend, React/Vite dashboard, PostgreSQL persistence, Alpaca paper trading adapter, Ichimoku signal engine, risk/order engine, backtesting and monitoring.

## Run
Backend: `pip install -r backend/requirements.txt && uvicorn backend.main:app --host 0.0.0.0 --port 8000`
Frontend: `cd frontend && npm install && npm run dev`
