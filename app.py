from flask import Flask, render_template_string, jsonify
import os
import time
import threading
from binance.client import Client
from datetime import datetime

app = Flask(__name__)

API_KEY = os.environ.get('BINANCE_API_KEY')
API_SECRET = os.environ.get('BINANCE_SECRET')
SYMBOL = "BTCUSDT"

client = Client(API_KEY, API_SECRET, testnet=True)

class BotState:
    def __init__(self):
        self.is_running = False
        self.logs = []
        self.trades = []
        self.balance = 0.0
        self.live_price = 0.0

bot_state = BotState()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>AURUM PRO — Auto Trading</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
<script src="https://unpkg.com/lucide@latest"></script>
<style>
  body { background:#050505; color:#E0E0E0; font-family: sans-serif; }
  .card { background:#111; border:1px solid #222; border-radius:12px; }
  .log-box { height: 250px; overflow-y: auto; font-family: monospace; font-size: 11px; background: #000; padding: 10px; border-radius: 8px; }
  .switch { position: relative; display: inline-block; width: 50px; height: 26px; }
  .switch input { opacity: 0; width: 0; height: 0; }
  .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #333; transition: .4s; border-radius: 26px; }
  .slider:before { position: absolute; content: ""; height: 20px; width: 20px; left: 3px; bottom: 3px; background-color: white; transition: .4s; border-radius: 50%; }
  input:checked + .slider { background-color: #00C853; }
  input:checked + .slider:before { transform: translateX(24px); }
  #chart { width: 100%; height: 300px; }
</style>
</head>
<body class="p-4 md:p-8">
  <div class="max-w-4xl mx-auto space-y-6">
    
    <div class="flex justify-between items-center bg-[#111] p-4 rounded-xl border border-gray-800">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 bg-yellow-500 rounded-lg flex items-center justify-center text-black font-bold">A</div>
        <div><h1 class="text-xl font-bold text-white">AURUM AUTO</h1></div>
      </div>
      <div class="text-right">
        <p class="text-xs text-gray-400">Balance</p>
        <p class="text-lg font-bold text-green-400" id="balance">$0.00</p>
      </div>
    </div>

    <div class="grid grid-cols-2 gap-4">
      <div class="card p-4">
        <p class="text-xs text-gray-400">Live Price</p>
        <p class="text-xl font-bold text-white" id="live-price">$0.00</p>
      </div>
      <div class="card p-4">
        <p class="text-xs text-gray-400">Bot Status</p>
        <div class="flex items-center justify-between mt-1">
          <span class="text-sm font-bold" id="status-text">STOPPED</span>
          <label class="switch"><input type="checkbox" id="bot-toggle" onchange="toggleBot()"><span class="slider"></span></label>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div class="card p-4">
        <h2 class="text-sm font-bold text-white mb-2">Live Chart</h2>
        <div id="chart"></div>
      </div>
      <div class="card p-4">
        <h2 class="text-sm font-bold text-white mb-2">Bot Logs</h2>
        <div class="log-box" id="log-container"></div>
      </div>
    </div>

    <div class="card p-4">
      <h2 class="text-sm font-bold text-white mb-2">Open Positions</h2>
      <div id="trades-table" class="text-sm text-gray-400">No open positions</div>
    </div>

  </div>

<script>
  const chart = LightweightCharts.createChart(document.getElementById('chart'), {
    layout: { background: { color: '#111' }, textColor: '#888' },
    grid: { vertLines: { color: '#222' }, horzLines: { color: '#222' } },
    autoSize: true
  });
  const series = chart.addCandlestickSeries({ upColor: '#00C853', downColor: '#FF3D00', borderVisible: false });

  async function updateUI() {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();

      document.getElementById('balance').innerText = `$${data.balance.toFixed(2)}`;
      if(data.live_price) document.getElementById('live-price').innerText = `$${data.live_price.toLocaleString()}`;
      
      const toggle = document.getElementById('bot-toggle');
      const statusText = document.getElementById('status-text');
      if(data.is_running) {
        toggle.checked = true; statusText.innerText = "ACTIVE"; statusText.className = "text-sm font-bold text-green-500";
      } else {
        toggle.checked = false; statusText.innerText = "STOPPED"; statusText.className = "text-sm font-bold text-gray-500";
      }

      document.getElementById('log-container').innerHTML = data.logs.map(l => `<div class="mb-1">${l}</div>`).join('');

      const openTrades = data.trades.filter(t => t.status === 'OPEN');
      if(openTrades.length > 0) {
        document.getElementById('trades-table').innerHTML = openTrades.map(t => `
          <div class="p-2 bg-gray-900 rounded mb-2 flex justify-between">
            <span class="${t.side === 'BUY' ? 'text-green-500' : 'text-red-500'} font-bold">${t.side}</span>
            <span>Entry: ${t.entry.toFixed(2)}</span>
            <span class="${t.pnl >= 0 ? 'text-green-500' : 'text-red-500'}">P&L: $${t.pnl.toFixed(2)}</span>
          </div>
        `).join('');
      } else {
        document.getElementById('trades-table').innerHTML = 'No open positions';
      }

      // Fetch Klines for Chart
      const klineRes = await fetch('/api/klines');
      const klines = await klineRes.json();
      if(klines.length > 0) {
        series.setData(klines);
      }

    } catch (e) { console.error(e); }
  }

  async function toggleBot() {
    await fetch('/api/toggle', { method: 'POST' });
    updateUI();
  }

  setInterval(updateUI, 2000);
  updateUI();
</script>
</body>
</html>
"""

def add_log(msg):
    time_str = datetime.now().strftime("%H:%M:%S")
    bot_state.logs.insert(0, f"[{time_str}] {msg}")
    if len(bot_state.logs) > 50: bot_state.logs.pop()

def get_ema(prices, period):
    if len(prices) < period: return prices[-1]
    multiplier = 2 / (period + 1)
    ema = prices[0]
    for price in prices:
        ema = (price - ema) * multiplier + ema
    return ema

def get_rsi(prices, period=14):
    if len(prices) < period: return 50.0
    gains = 0; losses = 0
    for i in range(1, period + 1):
        diff = prices[i] - prices[i-1]
        if diff > 0: gains += diff
        else: losses -= diff
    avg_gain = gains / period; avg_loss = losses / period
    if avg_loss == 0: return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def trading_bot():
    add_log("Engine Started. Scanning Markets...")
    while bot_state.is_running:
        try:
            klines = client.get_klines(symbol=SYMBOL, interval='1m', limit=50)
            closes = [float(k[4]) for k in klines]
            
            ema9 = get_ema(closes, 9)
            ema21 = get_ema(closes, 21)
            rsi = get_rsi(closes)
            current_price = closes[-1]
            
            for t in bot_state.trades:
                if t["status"] == "OPEN":
                    if t["side"] == "BUY": t["pnl"] = (current_price - t["entry"]) * t["qty"]
                    else: t["pnl"] = (t["entry"] - current_price) * t["qty"]
                    
                    if not t.get("be_moved"):
                        if (t["side"] == "BUY" and current_price > t["entry"] + 10) or \
                           (t["side"] == "SELL" and current_price < t["entry"] - 10):
                            t["sl"] = t["entry"]; t["be_moved"] = True
                            add_log(f"Breakeven active for {t['side']}")

                    hit_sl = (t["side"] == "BUY" and current_price <= t["sl"]) or (t["side"] == "SELL" and current_price >= t["sl"])
                    hit_tp = (t["side"] == "BUY" and current_price >= t["tp"]) or (t["side"] == "SELL" and current_price <= t["tp"])
                    
                    if hit_sl or hit_tp:
                        t["status"] = "CLOSED"
                        reason = "TP" if hit_tp else "SL"
                        add_log(f"{reason} HIT! P&L: ${t['pnl']:.4f}")
            
            has_open = any(t["status"] == "OPEN" for t in bot_state.trades)
            if not has_open:
                if ema9 > ema21 and rsi < 70:
                    add_log(f"BUY Signal! Price: {current_price}")
                    client.create_order(symbol=SYMBOL, side='BUY', type='MARKET', quantity=0.001)
                    bot_state.trades.insert(0, {
                        "id": int(time.time()), "side": "BUY", "entry": current_price, "qty": 0.001, 
                        "tp": current_price * 1.005, "sl": current_price * 0.995, 
                        "status": "OPEN", "pnl": 0.0, "be_moved": False
                    })
                elif ema9 < ema21 and rsi > 30:
                    add_log(f"SELL Signal! Price: {current_price}")
                    client.create_order(symbol=SYMBOL, side='SELL', type='MARKET', quantity=0.001)
                    bot_state.trades.insert(0, {
                        "id": int(time.time()), "side": "SELL", "entry": current_price, "qty": 0.001, 
                        "tp": current_price * 0.995, "sl": current_price * 1.005, 
                        "status": "OPEN", "pnl": 0.0, "be_moved": False
                    })
            
            account = client.get_account()
            usdt_bal = next((b for b in account['balances'] if b['asset'] == 'USDT'), {'free': '0'})
            bot_state.balance = float(usdt_bal['free'])

        except Exception as e:
            add_log(f"API Error: {str(e)}")
        
        time.sleep(10)

@app.route('/')
def home(): return render_template_string(HTML_TEMPLATE)

@app.route('/api/status')
def status():
    try:
        ticker = client.get_symbol_ticker(symbol=SYMBOL)
        bot_state.live_price = float(ticker['price'])
    except: pass
    return jsonify(bot_state.__dict__)

@app.route('/api/klines')
def get_klines():
    try:
        klines = client.get_klines(symbol=SYMBOL, interval='1m', limit=50)
        data = [{"time": k[0]//1000, "open": float(k[1]), "high": float(k[2]), "low": float(k[3]), "close": float(k[4])} for k in klines]
        return jsonify(data)
    except: return jsonify([])

@app.route('/api/toggle', methods=['POST'])
def toggle_bot():
    if not bot_state.is_running:
        bot_state.is_running = True
        threading.Thread(target=trading_bot, daemon=True).start()
    else:
        bot_state.is_running = False
        add_log("Bot Stopped by User.")
    return jsonify({"status": "success"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
