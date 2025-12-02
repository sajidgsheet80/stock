from fyers_apiv3 import fyersModel
from flask import Flask, request, render_template_string, jsonify, redirect
import webbrowser
import os
import time
import json
import re
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "sajid_secret"

# ---- Credentials ----
client_id = "VMS68P9EK0-100"
secret_key = "ZJ0CFWZEL1"
redirect_uri = "http://127.0.0.1:5000/callback"
grant_type = "authorization_code"
response_type = "code"
state = "sample"

# ---- Auto-Order Configuration ----
# !!! WARNING: AUTO-TRADING IS RISKY. ENABLE WITH CAUTION. !!!
# Set to 'True' to enable automatic order placement based on the conditions below.
AUTO_TRADE_ENABLED = False

# The minimum positive change % required to trigger an auto-order.
# Example: 1.5 means the stock must be up by at least 1.5%.
AUTO_TRADE_CHANGE_PCT_THRESHOLD = 1.5

# The minimum volume required to trigger an auto-order.
# Example: 5000000 means the stock must have a volume of at least 50 Lakhs.
AUTO_TRADE_VOLUME_THRESHOLD = 5000000

# The quantity to use for auto-placed orders.
AUTO_TRADE_QUANTITY = 1

# ---- Nifty 50 Stocks ----
NIFTY_50_STOCKS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "HINDUNILVR",
    "ICICIBANK", "KOTAKBANK", "SBIN", "BHARTIARTL", "ITC",
    "AXISBANK", "LT", "ASIANPAINT", "MARUTI", "BAJFINANCE",
    "HCLTECH", "SUNPHARMA", "TITAN", "ULTRACEMCO", "WIPRO",
    "NESTLEIND", "ONGC", "NTPC", "TECHM", "POWERGRID",
    "BAJAJFINSV", "TATAMOTORS", "ADANIPORTS", "COALINDIA", "TATASTEEL",
    "M&M", "INDUSINDBK", "DIVISLAB", "DRREDDY", "EICHERMOT",
    "CIPLA", "APOLLOHOSP", "BAJAJ-AUTO", "HDFCLIFE", "HINDALCO",
    "HEROMOTOCO", "BRITANNIA", "GRASIM", "SBILIFE", "JSWSTEEL",
    "SHREECEM", "UPL", "TATACONSUM", "LTIM", "ADANIENT"
]

# ---- Session ----
appSession = fyersModel.SessionModel(
    client_id=client_id,
    secret_key=secret_key,
    redirect_uri=redirect_uri,
    response_type=response_type,
    grant_type=grant_type,
    state=state
)

# ---- Globals ----
access_token_global = None
fyers = None
last_fetch_time = None
token_expiry_time = None
connection_status = {"connected": False, "last_check": None, "error": None}

# Paper trading storage
paper_trades = []
trade_id_counter = 1

# To store the last fetched data for comparison
previous_data_for_comparison = {}

# To keep track of symbols for which an auto-order has been placed
auto_traded_symbols = set()

# Helper function to create valid CSS IDs from stock symbols
def sanitize_id(symbol):
    """Convert a stock symbol to a valid CSS ID."""
    return re.sub(r'[^a-zA-Z0-9-]', '_', symbol)

def place_auto_order(symbol, ltp, quantity):
    """Places a market buy order for a given symbol."""
    global fyers
    if fyers is None:
        print("Auto-Order Failed: Not authenticated with Fyers.")
        return

    print(f"--- Auto-Order Triggered for {symbol} @ {ltp} ---")
    order_data = {
        "symbol": f"NSE:{symbol}-EQ",
        "qty": quantity,
        "type": 2,  # 1 for MARKET order
        "side": 1,  # 1 for BUY
        "productType": "INTRADAY",
        "limitPrice": 0,
        "stopPrice": 0,
        "validity": "DAY",
        "disclosedQty": 0,
        "offlineOrder": False,
        "orderTag": "AutoOrder"
    }
    try:
        response = fyers.place_order(data=order_data)
        if response.get("s") == "ok":
            print(f"✅ Auto-Order SUCCESS for {symbol}. Order ID: {response.get('id')}")
        else:
            error_message = response.get("message", "Unknown error from Fyers")
            print(f"❌ Auto-Order FAILED for {symbol}. Reason: {error_message}")
    except Exception as e:
        print(f"❌ Auto-Order FAILED for {symbol}. Exception: {str(e)}")


# ---- HTML Template ----
TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Sajid Shaikh Algo Software - Nifty 50 Stocks</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .header h1 { margin: 0; font-size: 28px; }
        .header p { margin: 5px 0 0 0; opacity: 0.9; }
        .connection-status { background: white; padding: 15px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); display: flex; justify-content: space-between; align-items: center; }
        .status-badge { padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; text-transform: uppercase; }
        .status-connected { background: #d4edda; color: #155724; }
        .status-disconnected { background: #f8d7da; color: #721c24; }
        .controls { background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; }
        .button-group { display: flex; gap: 10px; flex-wrap: wrap; }
        button { padding: 12px 24px; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 500; transition: all 0.3s ease; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        button:hover { transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.15); }
        button:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
        .btn-primary { background: #4CAF50; color: white; }
        .btn-primary:hover { background: #45a049; }
        .btn-secondary { background: #2196F3; color: white; }
        .btn-secondary:hover { background: #0b7dda; }
        .btn-danger { background: #f44336; color: white; }
        .btn-danger:hover { background: #d32f2f; }
        .status-info { display: flex; align-items: center; gap: 10px; font-size: 14px; color: #666; }
        .status-indicator { width: 12px; height: 12px; border-radius: 50%; background: #ccc; }
        .status-indicator.active { background: #4CAF50; animation: pulse 1.5s infinite; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .stat-card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; transition: transform 0.3s ease; }
        .stat-card:hover { transform: translateY(-2px); }
        .stat-value { font-size: 32px; font-weight: bold; margin-bottom: 5px; }
        .stat-label { color: #666; font-size: 14px; }
        .stat-card.gainers .stat-value { color: #4CAF50; }
        .stat-card.losers .stat-value { color: #f44336; }
        .stat-card.total .stat-value { color: #2196F3; }
        .table-container { background: white; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); overflow: hidden; margin-bottom: 20px; }
        .table-header { background: #4CAF50; color: white; padding: 15px 20px; font-size: 18px; font-weight: bold; display: flex; justify-content: space-between; align-items: center; }
        .last-update { font-size: 12px; opacity: 0.9; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
        th { background: #f8f9fa; font-weight: 600; color: #333; position: sticky; top: 0; z-index: 10; }
        tr:hover { background: #f8f9fa; }
        .symbol { font-weight: bold; color: #333; }
        .price { font-weight: 600; font-size: 16px; }
        .positive { color: #4CAF50; font-weight: 600; }
        .negative { color: #f44336; font-weight: 600; }
        .neutral { color: #666; }
        .change-arrow { margin-right: 4px; }
        .loading { text-align: center; padding: 40px; color: #666; }
        .error { text-align: center; padding: 40px; color: #f44336; }
        .loading-spinner { display: inline-block; width: 20px; height: 20px; border: 3px solid #f3f3f3; border-top: 3px solid #4CAF50; border-radius: 50%; animation: spin 1s linear infinite; margin-right: 10px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .cell-updated { animation: highlight 1s ease; }
        @keyframes highlight { 0% { background-color: #fff59d; } 100% { background-color: transparent; } }
        .volume { font-size: 12px; color: #666; }
        .refresh-controls { display: flex; align-items: center; gap: 10px; }
        .refresh-interval { display: flex; align-items: center; gap: 5px; font-size: 14px; }
        .refresh-interval input { width: 60px; padding: 5px; border: 1px solid #ddd; border-radius: 4px; }
        .tabs { display: flex; margin-bottom: 20px; background: white; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); overflow: hidden; }
        .tab { flex: 1; padding: 15px; text-align: center; cursor: pointer; transition: background-color 0.3s; font-weight: 500; }
        .tab:hover { background-color: #f8f9fa; }
        .tab.active { background-color: #4CAF50; color: white; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .order-form { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; font-weight: 500; }
        .form-group select, .form-group input { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; box-sizing: border-box; }
        .form-row { display: flex; gap: 15px; }
        .form-row .form-group { flex: 1; }
        .paper-trade-card { background: white; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); padding: 15px; margin-bottom: 15px; border-left: 4px solid #4CAF50; }
        .paper-trade-card.sell { border-left-color: #f44336; }
        .paper-trade-header { display: flex; justify-content: space-between; margin-bottom: 10px; }
        .paper-trade-title { font-weight: bold; font-size: 16px; }
        .paper-trade-close { background: #f44336; color: white; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; }
        .paper-trade-details { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
        .paper-trade-detail { display: flex; justify-content: space-between; }
        .paper-trade-detail-label { color: #666; font-size: 14px; }
        .paper-trade-detail-value { font-weight: 500; }
        .paper-trade-profit { font-weight: bold; font-size: 16px; }
        .paper-trade-profit.positive { color: #4CAF50; }
        .paper-trade-profit.negative { color: #f44336; }
        a.btn-secondary { text-decoration: none; display: inline-block; }
        .error-details { background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 10px 0; font-size: 14px; }
        .error-details h4 { margin: 0 0 10px 0; color: #856404; }
        .error-details pre { background: #f8f9fa; padding: 10px; border-radius: 3px; overflow-x: auto; font-size: 12px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Sajid Shaikh Algo Software</h1>
        <p>+91 9834370368 | Nifty 50 Live Stock Monitor</p>
    </div>

    <div class="connection-status">
        <div>
            <strong>Connection Status:</strong>
            <span id="connectionBadge" class="status-badge status-disconnected">Disconnected</span>
            <span id="connectionMessage">Not connected to Fyers API</span>
        </div>
        <div>
            <a href="/login" target="_blank" class="btn-secondary">🔑 Fyers Login</a>
        </div>
    </div>

    <div class="tabs">
        <div class="tab active" onclick="showTab('stocks')">Stock Market</div>
        <div class="tab" onclick="showTab('real-order')">Real Order</div>
        <div class="tab" onclick="showTab('paper-trade')">Paper Trading</div>
    </div>

    <div id="stocks-tab" class="tab-content active">
        <div class="controls">
            <div class="button-group">
                <button id="fetchBtn" class="btn-primary" onclick="fetchData()">🔄 Fetch Stock Data</button>
                <button id="autoRefreshBtn" class="btn-secondary" onclick="toggleAutoRefresh()">▶️ Start Auto Refresh</button>
            </div>
            <div class="refresh-controls">
                <div class="refresh-interval">
                    <label>Interval:</label>
                    <input type="number" id="intervalInput" value="30" min="5" max="300">
                    <span>sec</span>
                </div>
                <div class="status-info">
                    <div id="statusIndicator" class="status-indicator"></div>
                    <span id="statusText">Ready</span>
                </div>
            </div>
        </div>
        <div class="stats" id="statsContainer" style="display: none;">
            <div class="stat-card total"><div class="stat-value" id="totalStocks">0</div><div class="stat-label">Total Stocks</div></div>
            <div class="stat-card gainers"><div class="stat-value" id="gainers">0</div><div class="stat-label">Gainers</div></div>
            <div class="stat-card losers"><div class="stat-value" id="losers">0</div><div class="stat-label">Losers</div></div>
        </div>
        <div class="table-container">
            <div class="table-header"><span>Nifty 50 Stocks - Live Data</span><span class="last-update" id="lastUpdate">Last Update: --</span></div>
            <table><thead><tr><th>#</th><th>Symbol</th><th>LTP</th><th>Change (Points)</th><th>Change %</th><th>Prev Change (Points)</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Volume</th><th>Prev Volume</th></tr></thead>
                <tbody id="stockData"><tr><td colspan="12" class="loading"><div class="loading-spinner"></div>Click "Fetch Stock Data" to load Nifty 50 stocks</td></tr></tbody>
            </table>
        </div>
    </div>

    <div id="real-order-tab" class="tab-content">
        <div class="order-form">
            <h2>Place Real Order</h2>
            <form id="realOrderForm">
                <div class="form-row">
                    <div class="form-group"><label for="realSymbol">Symbol</label><select id="realSymbol" name="symbol" required><option value="">Select Symbol</option></select></div>
                    <div class="form-group"><label for="realOrderType">Order Type</label><select id="realOrderType" name="orderType" required><option value="LIMIT">Limit</option><option value="MARKET">Market</option><option value="SL">Stop Loss</option><option value="SL-M">Stop Loss Market</option></select></div>
                </div>
                <div class="form-row">
                    <div class="form-group"><label for="realTransactionType">Transaction Type</label><select id="realTransactionType" name="transactionType" required><option value="BUY">Buy</option><option value="SELL">Sell</option></select></div>
                    <div class="form-group"><label for="realQuantity">Quantity</label><input type="number" id="realQuantity" name="quantity" min="1" value="1" required></div>
                </div>
                <div class="form-row">
                    <div class="form-group"><label for="realPrice">Price</label><input type="number" id="realPrice" name="price" step="0.05" min="0" required></div>
                    <div class="form-group"><label for="realStopLoss">Stop Loss</label><input type="number" id="realStopLoss" name="stopLoss" step="0.05" min="0"></div>
                </div>
                <div class="form-group">
                    <label for="realValidity">Validity</label>
                    <select id="realValidity" name="validity" required>
                        <option value="DAY">Day</option>
                        <option value="IOC">Immediate or Cancel</option>
                    </select>
                </div>
                <div class="form-group"><button type="submit" class="btn-primary">Place Order</button></div>
            </form>
            <div id="realOrderResult"></div>
        </div>
    </div>

    <div id="paper-trade-tab" class="tab-content">
        <div class="order-form">
            <h2>Place Paper Trade</h2>
            <form id="paperTradeForm">
                <div class="form-row">
                    <div class="form-group"><label for="paperSymbol">Symbol</label><select id="paperSymbol" name="symbol" required><option value="">Select Symbol</option></select></div>
                    <div class="form-group"><label for="paperTransactionType">Transaction Type</label><select id="paperTransactionType" name="transactionType" required><option value="BUY">Buy</option><option value="SELL">Sell</option></select></div>
                </div>
                <div class="form-row">
                    <div class="form-group"><label for="paperQuantity">Quantity</label><input type="number" id="paperQuantity" name="quantity" min="1" value="1" required></div>
                    <div class="form-group"><label for="paperPrice">Price</label><input type="number" id="paperPrice" name="price" step="0.05" min="0" required></div>
                </div>
                <div class="form-group"><button type="submit" class="btn-primary">Place Paper Trade</button></div>
            </form>
            <div id="paperTradeResult"></div>
        </div>
        <div class="table-container">
            <div class="table-header"><span>Paper Trading Positions</span><button class="btn-secondary" onclick="fetchPaperTrades()">🔄 Refresh</button></div>
            <div id="paperTradesContainer"><div class="loading"><div class="loading-spinner"></div>Loading paper trades...</div></div>
        </div>
    </div>

    <script>
        let autoRefreshInterval = null; let isAutoRefreshOn = false; let previousData = null; let refreshIntervalSeconds = 30; let stockPrices = {};
        function sanitizeId(symbol) { return symbol.replace(/[^a-zA-Z0-9-]/g, '_'); }
        function showTab(tabName) { document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active')); document.querySelectorAll('.tab').forEach(tabButton => tabButton.classList.remove('active')); document.getElementById(tabName + '-tab').classList.add('active'); event.target.classList.add('active'); if (tabName === 'paper-trade') { fetchPaperTrades(); } }
        function updateConnectionStatus(connected, message = '') { const badge = document.getElementById('connectionBadge'); const messageEl = document.getElementById('connectionMessage'); if (connected) { badge.className = 'status-badge status-connected'; badge.textContent = 'Connected'; messageEl.textContent = message || 'Successfully connected to Fyers API'; } else { badge.className = 'status-badge status-disconnected'; badge.textContent = 'Disconnected'; messageEl.textContent = message || 'Not connected to Fyers API'; } }
        function updateStatus(text, isActive = false) { const statusText = document.getElementById('statusText'); const statusIndicator = document.getElementById('statusIndicator'); statusText.textContent = text; if (isActive) { statusIndicator.classList.add('active'); } else { statusIndicator.classList.remove('active'); } }
        async function fetchData(showStatus = true) { const fetchBtn = document.getElementById('fetchBtn'); fetchBtn.disabled = true; fetchBtn.innerHTML = '<div class="loading-spinner"></div>Loading...'; if (showStatus) updateStatus('Fetching data...', true); if (!previousData) { document.getElementById('stockData').innerHTML = `<tr><td colspan="12" class="loading"><div class="loading-spinner"></div>Loading stock data...</td></tr>`; } try { const response = await fetch('/fetch', { method: 'GET', headers: { 'Content-Type': 'application/json', }, signal: AbortSignal.timeout(30000) }); if (!response.ok) { throw new Error(`HTTP error! status: ${response.status}`); } const data = await response.json(); if (data.error) { document.getElementById('stockData').innerHTML = `<tr><td colspan="12" class="error"><h4>❌ Error Fetching Data</h4><p>${data.error}</p></td></tr>`; updateConnectionStatus(false, data.error); if (showStatus) updateStatus('Error: ' + data.error, false); return; } if (previousData) { updateStocksIncremental(data); } else { displayStocks(data); } updateStats(data); updateLastRefreshTime(); previousData = data; updateConnectionStatus(true, 'Data fetched successfully'); if (showStatus) updateStatus('Data updated successfully', false); updateStockPrices(data.stocks); if (document.getElementById('paper-trade-tab').classList.contains('active')) { fetchPaperTrades(); } } catch (error) { console.error('Error:', error); let errorMessage = 'Failed to fetch data. Please check your connection.'; if (error.name === 'AbortError') { errorMessage = 'Request timed out. Please try again.'; } document.getElementById('stockData').innerHTML = `<tr><td colspan="12" class="error"><h4>❌ ${errorMessage}</h4><p>${error.message}</p></td></tr>`; updateConnectionStatus(false, errorMessage); if (showStatus) updateStatus(errorMessage, false); } finally { fetchBtn.disabled = false; fetchBtn.innerHTML = '🔄 Fetch Stock Data'; } }
        function displayStocks(data) { const tbody = document.getElementById('stockData'); tbody.innerHTML = ''; if (!data.stocks || data.stocks.length === 0) { tbody.innerHTML = `<tr><td colspan="12" class="loading">No stock data available</td></tr>`; return; } populateSymbolDropdowns(data.stocks); data.stocks.forEach((stock, index) => { const row = createStockRow(stock, index); tbody.appendChild(row); }); }
        function populateSymbolDropdowns(stocks) { const realSymbolSelect = document.getElementById('realSymbol'); const paperSymbolSelect = document.getElementById('paperSymbol'); while (realSymbolSelect.options.length > 1) { realSymbolSelect.remove(1); } while (paperSymbolSelect.options.length > 1) { paperSymbolSelect.remove(1); } stocks.forEach(stock => { const option1 = new Option(stock.symbol, stock.symbol); const option2 = new Option(stock.symbol, stock.symbol); realSymbolSelect.add(option1); paperSymbolSelect.add(option2); }); }
        function createStockRow(stock, index) { const changeClass = stock.change > 0 ? 'positive' : stock.change < 0 ? 'negative' : 'neutral'; const prevChangeClass = stock.prev_change > 0 ? 'positive' : stock.prev_change < 0 ? 'negative' : 'neutral'; const changeSymbol = stock.change > 0 ? '▲' : stock.change < 0 ? '▼' : '•'; const prevChangeSymbol = stock.prev_change > 0 ? '▲' : stock.prev_change < 0 ? '▼' : '•'; const safeSymbol = sanitizeId(stock.symbol); const tr = document.createElement('tr'); tr.id = `stock-${safeSymbol}`; tr.innerHTML = `<td>${index + 1}</td><td class="symbol">${stock.symbol}</td><td class="price" id="ltp-${safeSymbol}">₹${stock.ltp.toFixed(2)}</td><td class="${changeClass}" id="change-${safeSymbol}"><span class="change-arrow">${changeSymbol}</span>${stock.change.toFixed(2)}</td><td class="${changeClass}" id="change-pct-${safeSymbol}">${stock.change_pct.toFixed(2)}%</td><td class="${prevChangeClass}" id="prev-change-${safeSymbol}"><span class="change-arrow">${prevChangeSymbol}</span>${stock.prev_change.toFixed(2)}</td><td id="open-${safeSymbol}">₹${stock.open.toFixed(2)}</td><td id="high-${safeSymbol}">₹${stock.high.toFixed(2)}</td><td id="low-${safeSymbol}">₹${stock.low.toFixed(2)}</td><td id="prev-close-${safeSymbol}">₹${stock.prev_close.toFixed(2)}</td><td class="volume" id="volume-${safeSymbol}">${formatVolume(stock.volume)}</td><td class="volume" id="prev-volume-${safeSymbol}">${formatVolume(stock.prev_volume)}</td>`; return tr; }
        function updateStocksIncremental(data) { if (!previousData || !data.stocks) return; const prevDataMap = {}; previousData.stocks.forEach(stock => { const safeSymbol = sanitizeId(stock.symbol); prevDataMap[safeSymbol] = stock; }); data.stocks.forEach((stock, index) => { const safeSymbol = sanitizeId(stock.symbol); const prevStock = prevDataMap[safeSymbol]; if (!prevStock) { const tbody = document.getElementById('stockData'); const row = createStockRow(stock, index); tbody.appendChild(row); return; } const changeClass = stock.change > 0 ? 'positive' : stock.change < 0 ? 'negative' : 'neutral'; const prevChangeClass = stock.prev_change > 0 ? 'positive' : stock.prev_change < 0 ? 'negative' : 'neutral'; const changeSymbol = stock.change > 0 ? '▲' : stock.change < 0 ? '▼' : '•'; const prevChangeSymbol = stock.prev_change > 0 ? '▲' : stock.prev_change < 0 ? '▼' : '•'; updateCellWithAnimation(`ltp-${safeSymbol}`, `₹${stock.ltp.toFixed(2)}`, stock.ltp !== prevStock.ltp); updateCellWithAnimation(`change-${safeSymbol}`, `<span class="change-arrow">${changeSymbol}</span>${stock.change.toFixed(2)}`, stock.change !== prevStock.change); updateCellWithAnimation(`change-pct-${safeSymbol}`, `${stock.change_pct.toFixed(2)}%`, stock.change_pct !== prevStock.change_pct); updateCellWithAnimation(`prev-change-${safeSymbol}`, `<span class="change-arrow">${prevChangeSymbol}</span>${stock.prev_change.toFixed(2)}`, stock.prev_change !== prevStock.prev_change); updateCellWithAnimation(`open-${safeSymbol}`, `₹${stock.open.toFixed(2)}`, stock.open !== prevStock.open); updateCellWithAnimation(`high-${safeSymbol}`, `₹${stock.high.toFixed(2)}`, stock.high !== prevStock.high); updateCellWithAnimation(`low-${safeSymbol}`, `₹${stock.low.toFixed(2)}`, stock.low !== prevStock.low); updateCellWithAnimation(`prev-close-${safeSymbol}`, `₹${stock.prev_close.toFixed(2)}`, stock.prev_close !== prevStock.prev_close); updateCellWithAnimation(`volume-${safeSymbol}`, formatVolume(stock.volume), stock.volume !== prevStock.volume); updateCellWithAnimation(`prev-volume-${safeSymbol}`, formatVolume(stock.prev_volume), stock.prev_volume !== prevStock.prev_volume); const row = document.getElementById(`stock-${safeSymbol}`); if (row) { const changeCell = row.querySelector(`#change-${safeSymbol}`); const changePctCell = row.querySelector(`#change-pct-${safeSymbol}`); const prevChangeCell = row.querySelector(`#prev-change-${safeSymbol}`); changeCell.className = changeClass; changePctCell.className = changeClass; prevChangeCell.className = prevChangeClass; } }); }
        function updateCellWithAnimation(cellId, newValue, hasChanged) { try { const cell = document.getElementById(cellId); if (cell && cell.innerHTML !== newValue) { cell.innerHTML = newValue; if (hasChanged) { cell.classList.add('cell-updated'); setTimeout(() => cell.classList.remove('cell-updated'), 1000); } } } catch (error) { console.error(`Error updating cell ${cellId}:`, error); } }
        function updateStats(data) { const statsContainer = document.getElementById('statsContainer'); statsContainer.style.display = 'grid'; const gainers = data.stocks.filter(s => s.change > 0).length; const losers = data.stocks.filter(s => s.change < 0).length; document.getElementById('totalStocks').textContent = data.stocks.length; document.getElementById('gainers').textContent = gainers; document.getElementById('losers').textContent = losers; }
        function formatVolume(volume) { if (volume >= 10000000) return (volume / 10000000).toFixed(2) + ' Cr'; if (volume >= 100000) return (volume / 100000).toFixed(2) + ' L'; if (volume >= 1000) return (volume / 1000).toFixed(2) + ' K'; return volume.toString(); }
        function updateLastRefreshTime() { const now = new Date(); document.getElementById('lastUpdate').textContent = `Last Update: ${now.toLocaleTimeString()}`; }
        function toggleAutoRefresh() { const autoRefreshBtn = document.getElementById('autoRefreshBtn'); refreshIntervalSeconds = parseInt(document.getElementById('intervalInput').value) || 30; if (isAutoRefreshOn) { stopAutoRefresh(); } else { startAutoRefresh(); } }
        function startAutoRefresh() { const autoRefreshBtn = document.getElementById('autoRefreshBtn'); if (autoRefreshInterval) return; fetchData(false); autoRefreshInterval = setInterval(() => fetchData(false), refreshIntervalSeconds * 1000); isAutoRefreshOn = true; autoRefreshBtn.textContent = '⏸️ Stop Auto Refresh'; autoRefreshBtn.className = 'btn-danger'; updateStatus(`Auto-refreshing every ${refreshIntervalSeconds}s`, true); }
        function stopAutoRefresh() { const autoRefreshBtn = document.getElementById('autoRefreshBtn'); if (autoRefreshInterval) { clearInterval(autoRefreshInterval); autoRefreshInterval = null; } isAutoRefreshOn = false; autoRefreshBtn.textContent = '▶️ Start Auto Refresh'; autoRefreshBtn.className = 'btn-secondary'; updateStatus('Auto-refresh stopped', false); }
        function updateStockPrices(stocks) { stocks.forEach(stock => { stockPrices[stock.symbol] = stock.ltp; }); }
        async function fetchPaperTrades() { try { const response = await fetch('/paper_trades'); const data = await response.json(); if (data.success) { displayPaperTrades(data.trades); } else { document.getElementById('paperTradesContainer').innerHTML = `<div class="error">Error fetching paper trades: ${data.error}</div>`; } } catch (error) { document.getElementById('paperTradesContainer').innerHTML = `<div class="error">Network error: ${error.message}</div>`; } }
        function displayPaperTrades(trades) { const container = document.getElementById('paperTradesContainer'); if (!trades || trades.length === 0) { container.innerHTML = `<div class="loading">No paper trades found. Place a paper trade to get started.</div>`; return; } container.innerHTML = ''; trades.forEach(trade => { const currentPrice = stockPrices[trade.symbol] || trade.entry_price; const profit = (currentPrice - trade.entry_price) * trade.quantity; const profitPercent = ((currentPrice - trade.entry_price) / trade.entry_price * 100); const profitClass = profit >= 0 ? 'positive' : 'negative'; const tradeCard = document.createElement('div'); tradeCard.className = `paper-trade-card ${trade.transaction_type === 'SELL' ? 'sell' : ''}`; tradeCard.innerHTML = `<div class="paper-trade-header"><div class="paper-trade-title">${trade.symbol} - ${trade.transaction_type}</div><button class="paper-trade-close" onclick="closePaperTrade(${trade.id})">Close</button></div><div class="paper-trade-details"><div class="paper-trade-detail"><span class="paper-trade-detail-label">Entry Price:</span><span class="paper-trade-detail-value">₹${trade.entry_price.toFixed(2)}</span></div><div class="paper-trade-detail"><span class="paper-trade-detail-label">Current Price:</span><span class="paper-trade-detail-value">₹${currentPrice.toFixed(2)}</span></div><div class="paper-trade-detail"><span class="paper-trade-detail-label">Quantity:</span><span class="paper-trade-detail-value">${trade.quantity}</span></div><div class="paper-trade-detail"><span class="paper-trade-detail-label">Date:</span><span class="paper-trade-detail-value">${new Date(trade.timestamp).toLocaleString()}</span></div><div class="paper-trade-detail"><span class="paper-trade-detail-label">Profit/Loss:</span><span class="paper-trade-profit ${profitClass}">₹${profit.toFixed(2)} (${profitPercent.toFixed(2)}%)</span></div></div>`; container.appendChild(tradeCard); }); }
        async function closePaperTrade(tradeId) { try { const response = await fetch(`/paper_trades/${tradeId}`, { method: 'DELETE' }); const data = await response.json(); if (data.success) { fetchPaperTrades(); } else { alert(`Error closing trade: ${data.error}`); } } catch (error) { alert(`Network error: ${error.message}`); } }
        document.getElementById('intervalInput').addEventListener('change', function() { refreshIntervalSeconds = parseInt(this.value) || 30; if (isAutoRefreshOn) { stopAutoRefresh(); startAutoRefresh(); } });
        document.getElementById('realOrderForm').addEventListener('submit', async function(e) { e.preventDefault(); const formData = new FormData(this); const orderData = {}; for (let [key, value] of formData.entries()) { orderData[key] = value; } try { const response = await fetch('/place_order', { method: 'POST', headers: { 'Content-Type': 'application/json', }, body: JSON.stringify(orderData) }); const data = await response.json(); const resultDiv = document.getElementById('realOrderResult'); if (data.success) { resultDiv.innerHTML = `<div class="paper-trade-profit positive">Order placed successfully! Order ID: ${data.orderId}</div>`; } else { resultDiv.innerHTML = `<div class="error-details"><h4>❌ Error placing order</h4><p>${data.error}</p>${data.details ? `<pre>${JSON.stringify(data.details, null, 2)}</pre>` : ''}</div>`; } } catch (error) { document.getElementById('realOrderResult').innerHTML = `<div class="paper-trade-profit negative">Network error: ${error.message}</div>`; } });
        document.getElementById('paperTradeForm').addEventListener('submit', async function(e) { e.preventDefault(); const formData = new FormData(this); const tradeData = {}; for (let [key, value] of formData.entries()) { tradeData[key] = value; } try { const response = await fetch('/paper_trades', { method: 'POST', headers: { 'Content-Type': 'application/json', }, body: JSON.stringify(tradeData) }); const data = await response.json(); const resultDiv = document.getElementById('paperTradeResult'); if (data.success) { resultDiv.innerHTML = `<div class="paper-trade-profit positive">Paper trade placed successfully!</div>`; fetchPaperTrades(); } else { resultDiv.innerHTML = `<div class="paper-trade-profit negative">Error placing paper trade: ${data.error}</div>`; } } catch (error) { document.getElementById('paperTradeResult').innerHTML = `<div class="paper-trade-profit negative">Network error: ${error.message}</div>`; } });
        window.onload = function() { updateStatus('Ready to fetch data', false); };
    </script>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    return render_template_string(TEMPLATE)

@app.route("/login")
def login():
    login_url = appSession.generate_authcode()
    webbrowser.open(login_url, new=1)
    return redirect(login_url)

@app.route("/callback")
def callback():
    global access_token_global, fyers, token_expiry_time
    auth_code = request.args.get("auth_code")
    if auth_code:
        try:
            appSession.set_token(auth_code)
            token_response = appSession.generate_token()
            access_token_global = token_response.get("access_token")

            if access_token_global:
                token_expiry_time = datetime.now() + timedelta(hours=24)
                fyers = fyersModel.FyersModel(client_id=client_id, token=access_token_global, is_async=False, log_path="")
                connection_status["connected"] = True
                connection_status["error"] = None
                return "<h2>✅ Authentication Successful! You can return to the app 🚀</h2>"
            else:
                connection_status["connected"] = False
                connection_status["error"] = "Failed to get access token"
                return "❌ Failed to get access token. Please retry."
        except Exception as e:
            connection_status["connected"] = False
            connection_status["error"] = str(e)
            return f"❌ Authentication failed: {str(e)}"
    return "❌ Authentication failed. Please retry."

@app.route("/fetch")
def fetch_nifty_50_data():
    global fyers, last_fetch_time, connection_status, previous_data_for_comparison, auto_traded_symbols

    if fyers is None:
        return jsonify({
            "error": "⚠ Please login first! Click the Fyers Login button.",
            "details": "No active Fyers session found. Please authenticate with the Fyers API."
        })

    try:
        if token_expiry_time and datetime.now() > token_expiry_time:
            return jsonify({
                "error": "⚠ Token expired! Please login again.",
                "details": f"Token expired at {token_expiry_time}. Please re-authenticate with the Fyers API."
            })

        all_symbols = [f"NSE:{stock}-EQ" for stock in NIFTY_50_STOCKS]
        stocks_list = []
        batch_size = 20
        for i in range(0, len(all_symbols), batch_size):
            batch_symbols = all_symbols[i:i + batch_size]
            data = {"symbols": ",".join(batch_symbols)}
            response = fyers.quotes(data=data)

            if response and response.get("s") == "ok":
                quotes_data = response.get("d", [])
                if not quotes_data: continue
                for quote in quotes_data:
                    try:
                        symbol = quote.get("n", "").replace("NSE:", "").replace("-EQ", "")
                        v_data = quote.get("v", {})
                        if not v_data: continue
                        ltp = v_data.get("lp", 0)
                        open_price = v_data.get("open_price", 0)
                        high = v_data.get("high_price", 0)
                        low = v_data.get("low_price", 0)
                        prev_close = v_data.get("prev_close_price", 0)
                        volume = v_data.get("volume", 0)
                        if ltp == 0: continue
                        change = ltp - prev_close
                        change_pct = (change / prev_close * 100) if prev_close > 0 else 0
                        
                        # --- MODIFIED LOGIC FOR PREVIOUS COLUMNS ---
                        # Check if this is the first fetch after a restart
                        if not previous_data_for_comparison:
                            # If it's the first fetch, populate 'prev' columns with current values
                            prev_change = change
                            prev_volume = volume
                        else:
                            # If it's a subsequent fetch, get values from the last fetch
                            prev_stock_data = previous_data_for_comparison.get(symbol, {})
                            prev_change = prev_stock_data.get("change", 0)
                            prev_volume = prev_stock_data.get("volume", 0)
                        # --- END OF MODIFIED LOGIC ---

                        stocks_list.append({
                            "symbol": symbol, "ltp": ltp, "change": change, "change_pct": change_pct,
                            "open": open_price, "high": high, "low": low, "prev_close": prev_close, "volume": volume,
                            "prev_change": prev_change, "prev_volume": prev_volume
                        })
                    except Exception as e:
                        print(f"Error processing quote: {e}")
                        continue
            else:
                error_msg = response.get("message", "Failed to fetch stock data")
                connection_status["connected"] = False
                connection_status["error"] = error_msg
                return jsonify({"error": f"API Error: {error_msg}", "details": f"Full response: {json.dumps(response)}"})

        if not stocks_list:
            return jsonify({"error": "No valid stock data found", "details": "Received data but couldn't process any valid stock information."})

        # --- Auto-Order Placement Logic ---
        if AUTO_TRADE_ENABLED:
            print("--- Auto-Trade Check ---")
            for stock in stocks_list:
                if stock['symbol'] not in auto_traded_symbols:
                    if stock['change_pct'] > AUTO_TRADE_CHANGE_PCT_THRESHOLD and stock['volume'] > AUTO_TRADE_VOLUME_THRESHOLD:
                        place_auto_order(stock['symbol'], stock['ltp'], AUTO_TRADE_QUANTITY)
                        auto_traded_symbols.add(stock['symbol']) # Add to set to prevent re-ordering
            print("------------------------")

        # Update the comparison map for the next run
        previous_data_for_comparison = {stock['symbol']: stock for stock in stocks_list}

        stocks_list.sort(key=lambda x: x["change_pct"], reverse=True)
        last_fetch_time = time.time()
        connection_status["connected"] = True
        connection_status["last_check"] = datetime.now().isoformat()
        connection_status["error"] = None
        return jsonify({"stocks": stocks_list})

    except Exception as e:
        connection_status["connected"] = False
        connection_status["error"] = str(e)
        return jsonify({"error": f"Error: {str(e)}", "details": f"Exception occurred: {type(e).__name__}: {str(e)}"})

@app.route("/place_order", methods=["POST"])
def place_real_order():
    global fyers
    if fyers is None:
        return jsonify({"success": False, "error": "Not authenticated. Please login first."})

    try:
        data = request.get_json()
        symbol = data.get("symbol")
        order_type_str = data.get("orderType")
        transaction_type_str = data.get("transactionType")
        quantity = int(data.get("quantity"))
        price = float(data.get("price"))
        stop_loss = data.get("stopLoss")
        validity = data.get("validity")

        if not all([symbol, order_type_str, transaction_type_str, quantity, price, validity]):
            return jsonify({"success": False, "error": "Missing required order parameters."})

        order_type_map = {"LIMIT": 2, "MARKET": 1, "SL": 4, "SL-M": 3}
        side_map = {"BUY": 1, "SELL": -1}

        order_data = {
            "symbol": f"NSE:{symbol}-EQ",
            "qty": quantity,
            "type": order_type_map.get(order_type_str.upper(), 2),
            "side": side_map.get(transaction_type_str.upper(), 1),
            "productType": "INTRADAY",
            "limitPrice": price if order_type_str.upper() in ["LIMIT", "SL"] else 0,
            "stopPrice": float(stop_loss) if order_type_str.upper() in ["SL", "SL-M"] else 0,
            "validity": validity.upper(),
            "disclosedQty": 0,
            "offlineOrder": False,
            "orderTag": "SajidAlgo"
        }
        
        response = fyers.place_order(data=order_data)

        if response.get("s") == "ok":
            return jsonify({"success": True, "orderId": response.get("id"), "message": "Order placed successfully."})
        else:
            error_message = response.get("message", "Unknown error from Fyers")
            return jsonify({
                "success": False, 
                "error": error_message,
                "details": response
            })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/paper_trades", methods=["GET", "POST"])
def handle_paper_trades():
    global paper_trades, trade_id_counter

    if request.method == "POST":
        try:
            data = request.get_json()
            symbol = data.get("symbol")
            transaction_type = data.get("transactionType")
            quantity = int(data.get("quantity"))
            entry_price = float(data.get("price"))

            if not all([symbol, transaction_type, quantity, entry_price]):
                return jsonify({"success": False, "error": "Missing required trade parameters."})

            new_trade = {
                "id": trade_id_counter,
                "symbol": symbol,
                "transaction_type": transaction_type,
                "quantity": quantity,
                "entry_price": entry_price,
                "timestamp": datetime.now().isoformat()
            }
            paper_trades.append(new_trade)
            trade_id_counter += 1
            return jsonify({"success": True, "message": "Paper trade placed successfully."})

        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

    elif request.method == "GET":
        return jsonify({"success": True, "trades": paper_trades})

@app.route("/paper_trades/<int:trade_id>", methods=["DELETE"])
def close_paper_trade(trade_id):
    global paper_trades
    try:
        trade_to_remove = None
        for trade in paper_trades:
            if trade["id"] == trade_id:
                trade_to_remove = trade
                break
        
        if trade_to_remove:
            paper_trades.remove(trade_to_remove)
            return jsonify({"success": True, "message": "Paper trade closed successfully."})
        else:
            return jsonify({"success": False, "error": "Trade not found."})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("\n" + "="*60)
    print("🚀 Sajid Shaikh Nifty 50 Stock Monitor")
    print("="*60)
    print(f"📍 Server: http://127.0.0.1:{port}")
    print("📊 Monitoring Nifty 50 stocks in real-time")
    print("💼 Real and Paper Trading Enabled")
    print("🤖 Auto-Ordering is", "ENABLED" if AUTO_TRADE_ENABLED else "DISABLED")
    print("="*60 + "\n")
    app.run(host="0.0.0.0", port=port, debug=False)