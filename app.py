#!/usr/bin/env python3
"""
Ranger Finance Raise Tracker - Web Dashboard
"""

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import json
import subprocess
import requests
from datetime import datetime
from collections import defaultdict
import re

app = Flask(__name__, static_folder='static')
CORS(app)

# Configuration
RANGER_WALLET = "9ApaAe39Z8GEXfqm7F7HL545N4J4tN7RhF8FhS88pRNp"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SALE_END_TIME = datetime(2026, 1, 10, 16, 0, 0)

# Historical patterns at 5.5h before end
# Ordered by sale date (oldest to newest)
HISTORICAL_PATTERNS = {
    'Umbra': {'at_5_5h': 44220255, 'final': 155194912, 'pct_at_5_5h': 28.5, 'sale_date': '2025-10-10', 'order': 1},
    'Avici': {'at_5_5h': 8036796, 'final': 34233177, 'pct_at_5_5h': 23.5, 'sale_date': '2025-10-18', 'order': 2},
    'Loyal': {'at_5_5h': 16437386, 'final': 75898234, 'pct_at_5_5h': 21.7, 'sale_date': '2025-10-22', 'order': 3},
    'zkSOL': {'at_5_5h': 2427947, 'final': 14886360, 'pct_at_5_5h': 16.3, 'sale_date': '2025-10-24', 'order': 4},
    'Paystream': {'at_5_5h': 1319085, 'final': 6149247, 'pct_at_5_5h': 21.5, 'sale_date': '2025-10-27', 'order': 5},
    'Solomon': {'at_5_5h': 11779124, 'final': 102932688, 'pct_at_5_5h': 11.4, 'sale_date': '2025-11-18', 'order': 6},
}

# Pattern probability weights - RECENCY WEIGHTED
# More recent sales have higher weights as they better reflect current market conditions
# Weights use exponential decay: newest sale (Solomon) gets highest weight
# Order: Umbra (oldest) -> Avici -> Loyal -> zkSOL -> Paystream -> Solomon (newest)
PATTERN_WEIGHTS = {
    'Solomon': 0.35,    # Most recent (Nov 2025) - highest weight
    'Paystream': 0.25,  # Oct 27, 2025
    'zkSOL': 0.17,      # Oct 24, 2025
    'Loyal': 0.12,      # Oct 22, 2025
    'Avici': 0.07,      # Oct 18, 2025
    'Umbra': 0.04,      # Oct 10, 2025 (oldest) - lowest weight
}
# Total: 100%

def get_ranger_balance():
    """Fetch current USDC balance from Solana RPC"""
    cmd = f'''curl -s 'https://api.mainnet-beta.solana.com' -X POST -H "Content-Type: application/json" -d '{{"jsonrpc":"2.0","id":1,"method":"getTokenAccountsByOwner","params":["{RANGER_WALLET}",{{"mint":"{USDC_MINT}"}},{{"encoding":"jsonParsed"}}]}}'  '''
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    try:
        data = json.loads(result.stdout)
        accounts = data.get('result', {}).get('value', [])
        if accounts:
            return accounts[0]['account']['data']['parsed']['info']['tokenAmount']['uiAmount']
    except:
        pass
    return None

def get_transaction_data():
    """Fetch recent transaction data"""
    cmd = f'''curl -s 'https://api.mainnet-beta.solana.com' -X POST -H "Content-Type: application/json" -d '{{"jsonrpc":"2.0","id":1,"method":"getSignaturesForAddress","params":["{RANGER_WALLET}",{{"limit":1000}}]}}'  '''
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    try:
        data = json.loads(result.stdout)
        sigs = data.get('result', [])
        successful = [s for s in sigs if s.get('err') is None]

        hourly = defaultdict(int)
        for tx in successful:
            ts = tx.get('blockTime', 0)
            if ts > 0:
                dt = datetime.utcfromtimestamp(ts)
                hour_key = dt.strftime('%Y-%m-%d %H:00')
                hourly[hour_key] += 1

        return {
            'total': len(successful),
            'hourly': dict(hourly)
        }
    except:
        pass
    return None

def get_polymarket_odds():
    """Fetch Polymarket odds for Ranger thresholds"""
    # Polymarket event slugs for each threshold
    polymarket_markets = {
        15: "over-15m-committed-to-the-ranger-public-sale",
        20: "over-20m-committed-to-the-ranger-public-sale",
        30: "over-30m-committed-to-the-ranger-public-sale",
        40: "over-40m-committed-to-the-ranger-public-sale-819-688",
        50: "over-50m-committed-to-the-ranger-public-sale",
        60: "over-60m-committed-to-the-ranger-public-sale",
        70: "over-70m-committed-to-the-ranger-public-sale",
        80: "over-80m-committed-to-the-ranger-public-sale",
        90: "over-90m-committed-to-the-ranger-public-sale",
        100: "over-100m-committed-to-the-ranger-public-sale",
        120: "over-120m-committed-to-the-ranger-public-sale",
        140: "over-140m-committed-to-the-ranger-public-sale",
        160: "over-160m-committed-to-the-ranger-public-sale",
        180: "over-180m-committed-to-the-ranger-public-sale",
        200: "over-200m-committed-to-the-ranger-public-sale",
    }

    odds = {}

    # Try to fetch from Polymarket API (CLOB API)
    try:
        # Polymarket CLOB API endpoint
        api_url = "https://clob.polymarket.com/markets"
        headers = {"Accept": "application/json"}

        # Try the gamma API which is more accessible
        gamma_url = "https://gamma-api.polymarket.com/events?slug=total-commitments-for-the-ranger-public-sale-on-metadao"
        response = requests.get(gamma_url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                event = data[0]
                markets = event.get('markets', [])

                for market in markets:
                    question = market.get('question', '').lower()
                    # Extract threshold from question
                    match = re.search(r'over\s*\$?(\d+)m', question)
                    if match:
                        threshold = int(match.group(1))
                        # Get the YES price (outcomePrices[0] is typically YES)
                        prices = market.get('outcomePrices', [])
                        if prices and len(prices) > 0:
                            try:
                                yes_price = float(prices[0]) * 100  # Convert to percentage
                                odds[threshold] = yes_price
                            except:
                                pass
    except Exception as e:
        print(f"Error fetching Polymarket: {e}")

    # If API fails, return cached/estimated odds
    if not odds:
        odds = {
            15: 100, 20: 100, 30: 99, 40: 98, 50: 87,
            60: 83, 70: 74, 80: 64, 90: 56, 100: 45,
            120: 31, 140: 16, 160: 10, 180: 8, 200: 6
        }

    return odds

def calculate_projections(balance, hours_remaining):
    """Calculate projections based on historical patterns"""
    projections = []

    for name, data in HISTORICAL_PATTERNS.items():
        mult = data['final'] / data['at_5_5h']
        time_factor = hours_remaining / 5.5
        adjusted_mult = 1 + (mult - 1) * time_factor
        projected = balance * adjusted_mult

        projections.append({
            'name': name,
            'multiplier': round(adjusted_mult, 2),
            'projected': round(projected, 0),
            'weight': PATTERN_WEIGHTS.get(name, 0),
            'sale_date': data.get('sale_date', ''),
            'order': data.get('order', 0),
            'final_raised': data['final']
        })

    # Sort by projected value for display
    return sorted(projections, key=lambda x: x['projected'])

def calculate_model_probabilities(projections):
    """Calculate model probability for each threshold"""
    thresholds = [15, 20, 30, 40, 50, 60, 70, 80, 90, 100, 120, 140, 160, 180, 200]
    probs = {}

    for t in thresholds:
        prob = 0
        for p in projections:
            if p['projected'] >= t * 1_000_000:
                prob += p['weight']
        probs[t] = round(prob * 100, 1)

    return probs

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/data')
def get_data():
    now = datetime.utcnow()
    time_remaining = SALE_END_TIME - now
    hours_remaining = max(0, time_remaining.total_seconds() / 3600)

    balance = get_ranger_balance()
    tx_data = get_transaction_data()
    polymarket_odds = get_polymarket_odds()

    if balance is None:
        return jsonify({'error': 'Could not fetch balance'}), 500

    projections = calculate_projections(balance, hours_remaining)
    model_probs = calculate_model_probabilities(projections)

    # Calculate value opportunities
    opportunities = {}
    for threshold in model_probs:
        pm_odds = polymarket_odds.get(threshold, 50)
        model_odds = model_probs[threshold]
        diff = model_odds - pm_odds

        if diff > 10:
            opportunities[threshold] = {'action': 'BUY YES', 'edge': round(diff, 1)}
        elif diff < -10:
            opportunities[threshold] = {'action': 'BUY NO', 'edge': round(abs(diff), 1)}
        else:
            opportunities[threshold] = {'action': 'FAIR', 'edge': 0}

    # Hourly data for chart
    hourly_data = []
    if tx_data and tx_data.get('hourly'):
        sorted_hours = sorted(tx_data['hourly'].keys())[-12:]  # Last 12 hours
        for hour in sorted_hours:
            hourly_data.append({
                'hour': hour[11:16],  # Just HH:MM
                'transactions': tx_data['hourly'][hour]
            })

    return jsonify({
        'timestamp': now.isoformat(),
        'hours_remaining': round(hours_remaining, 2),
        'minutes_remaining': int(hours_remaining * 60),
        'balance': balance,
        'transactions': tx_data['total'] if tx_data else 0,
        'projections': projections,
        'model_probabilities': model_probs,
        'polymarket_odds': polymarket_odds,
        'opportunities': opportunities,
        'hourly_activity': hourly_data,
        'sale_ended': hours_remaining <= 0
    })

@app.route('/api/historical')
def get_historical():
    """Return historical patterns data"""
    return jsonify(HISTORICAL_PATTERNS)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
