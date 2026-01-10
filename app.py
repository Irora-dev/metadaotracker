#!/usr/bin/env python3
"""
Ranger Finance Raise Tracker - Web Dashboard
"""

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import json
import subprocess
import requests
from datetime import datetime, timedelta
from collections import defaultdict, deque
import re
import threading
import time

app = Flask(__name__, static_folder='static')
CORS(app)

# Configuration
RANGER_WALLET = "9ApaAe39Z8GEXfqm7F7HL545N4J4tN7RhF8FhS88pRNp"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SALE_END_TIME = datetime(2026, 1, 10, 16, 0, 0)

# Historical balance tracking for velocity calculations
# Stores tuples of (timestamp, balance)
balance_history = deque(maxlen=1000)  # Keep last 1000 data points
balance_history_lock = threading.Lock()

# Historical patterns with multiple time snapshots
# Ordered by sale date (oldest to newest)
HISTORICAL_PATTERNS = {
    'Umbra': {
        'final': 155194912,
        'sale_date': '2025-10-10',
        'order': 1,
        'snapshots': {
            6.0: 38000000,    # 6 hours before end
            5.5: 44220255,    # 5.5 hours before end
            5.0: 51000000,
            4.5: 59000000,
            4.0: 68000000,
            3.5: 78000000,
            3.0: 89000000,
            2.5: 102000000,
            2.0: 115000000,
            1.5: 128000000,
            1.0: 140000000,
            0.5: 150000000,
        }
    },
    'Avici': {
        'final': 34233177,
        'sale_date': '2025-10-18',
        'order': 2,
        'snapshots': {
            6.0: 6800000,
            5.5: 8036796,
            5.0: 9500000,
            4.5: 11200000,
            4.0: 13200000,
            3.5: 15500000,
            3.0: 18200000,
            2.5: 21500000,
            2.0: 25000000,
            1.5: 28500000,
            1.0: 31500000,
            0.5: 33500000,
        }
    },
    'Loyal': {
        'final': 75898234,
        'sale_date': '2025-10-22',
        'order': 3,
        'snapshots': {
            6.0: 13500000,
            5.5: 16437386,
            5.0: 20000000,
            4.5: 24500000,
            4.0: 30000000,
            3.5: 36500000,
            3.0: 44000000,
            2.5: 52000000,
            2.0: 60000000,
            1.5: 67000000,
            1.0: 72000000,
            0.5: 75000000,
        }
    },
    'zkSOL': {
        'final': 14886360,
        'sale_date': '2025-10-24',
        'order': 4,
        'snapshots': {
            6.0: 2000000,
            5.5: 2427947,
            5.0: 3000000,
            4.5: 3800000,
            4.0: 4800000,
            3.5: 6000000,
            3.0: 7500000,
            2.5: 9200000,
            2.0: 11000000,
            1.5: 12800000,
            1.0: 14000000,
            0.5: 14700000,
        }
    },
    'Paystream': {
        'final': 6149247,
        'sale_date': '2025-10-27',
        'order': 5,
        'snapshots': {
            6.0: 1100000,
            5.5: 1319085,
            5.0: 1600000,
            4.5: 2000000,
            4.0: 2500000,
            3.5: 3100000,
            3.0: 3800000,
            2.5: 4500000,
            2.0: 5100000,
            1.5: 5600000,
            1.0: 5900000,
            0.5: 6100000,
        }
    },
    'Solomon': {
        'final': 102932688,
        'sale_date': '2025-11-18',
        'order': 6,
        'snapshots': {
            6.0: 9500000,
            5.5: 11779124,
            5.0: 15000000,
            4.5: 19500000,
            4.0: 26000000,
            3.5: 35000000,
            3.0: 46000000,
            2.5: 58000000,
            2.0: 70000000,
            1.5: 82000000,
            1.0: 92000000,
            0.5: 100000000,
        }
    },
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
                        prices_raw = market.get('outcomePrices', [])
                        # outcomePrices may be a JSON string, parse if needed
                        if isinstance(prices_raw, str):
                            try:
                                prices = json.loads(prices_raw)
                            except:
                                prices = []
                        else:
                            prices = prices_raw
                        if prices and len(prices) > 0:
                            try:
                                yes_price = float(prices[0]) * 100  # Convert to percentage
                                odds[threshold] = round(yes_price, 1)
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

def get_historical_at_time(hours_remaining):
    """Get historical sale amounts at a specific time before end"""
    snapshots = []
    # Round to nearest 0.5 hour for snapshot lookup
    lookup_time = round(hours_remaining * 2) / 2
    lookup_time = max(0.5, min(6.0, lookup_time))

    for name, data in HISTORICAL_PATTERNS.items():
        snapshot_value = data['snapshots'].get(lookup_time)
        if snapshot_value:
            snapshots.append({
                'name': name,
                'amount': snapshot_value,
                'final': data['final'],
                'pct_of_final': round(snapshot_value / data['final'] * 100, 1),
                'sale_date': data['sale_date'],
                'order': data['order']
            })

    return sorted(snapshots, key=lambda x: x['order'])


def calculate_projections(balance, hours_remaining):
    """Calculate projections based on historical patterns"""
    projections = []

    # Round to nearest 0.5 hour for snapshot lookup
    lookup_time = round(hours_remaining * 2) / 2
    lookup_time = max(0.5, min(6.0, lookup_time))

    for name, data in HISTORICAL_PATTERNS.items():
        snapshot_at_time = data['snapshots'].get(lookup_time, data['snapshots'].get(5.5))
        mult = data['final'] / snapshot_at_time if snapshot_at_time else 1
        projected = balance * mult

        projections.append({
            'name': name,
            'multiplier': round(mult, 2),
            'projected': round(projected, 0),
            'weight': PATTERN_WEIGHTS.get(name, 0),
            'sale_date': data.get('sale_date', ''),
            'order': data.get('order', 0),
            'final_raised': data['final'],
            'snapshot_used': snapshot_at_time
        })

    # Sort by projected value for display
    return sorted(projections, key=lambda x: x['projected'])


def calculate_confidence(projections, balance, hours_remaining):
    """Calculate confidence score based on model agreement and time remaining"""
    if not projections:
        return {'score': 0, 'level': 'LOW', 'factors': []}

    factors = []
    score = 50  # Base score

    # Factor 1: Model agreement (how close are the projections?)
    projected_values = [p['projected'] for p in projections]
    mean_proj = sum(projected_values) / len(projected_values)
    std_dev = (sum((p - mean_proj) ** 2 for p in projected_values) / len(projected_values)) ** 0.5
    cv = std_dev / mean_proj if mean_proj > 0 else 1  # Coefficient of variation

    if cv < 0.3:
        score += 20
        factors.append({'factor': 'Model Agreement', 'impact': '+20', 'detail': 'Projections closely aligned'})
    elif cv < 0.5:
        score += 10
        factors.append({'factor': 'Model Agreement', 'impact': '+10', 'detail': 'Moderate projection spread'})
    else:
        score -= 10
        factors.append({'factor': 'Model Agreement', 'impact': '-10', 'detail': 'Wide projection spread'})

    # Factor 2: Time remaining (more confidence as we get closer to end)
    if hours_remaining <= 1:
        score += 25
        factors.append({'factor': 'Time Proximity', 'impact': '+25', 'detail': 'Final hour - high certainty'})
    elif hours_remaining <= 2:
        score += 15
        factors.append({'factor': 'Time Proximity', 'impact': '+15', 'detail': 'Last 2 hours - good certainty'})
    elif hours_remaining <= 4:
        score += 5
        factors.append({'factor': 'Time Proximity', 'impact': '+5', 'detail': 'Within 4 hours'})
    else:
        score -= 10
        factors.append({'factor': 'Time Proximity', 'impact': '-10', 'detail': 'More than 4 hours remaining'})

    # Factor 3: Current raise relative to historical patterns
    historical_snapshots = get_historical_at_time(hours_remaining)
    if historical_snapshots:
        avg_historical = sum(s['amount'] for s in historical_snapshots) / len(historical_snapshots)
        ratio = balance / avg_historical if avg_historical > 0 else 0

        if 0.5 <= ratio <= 2.0:
            score += 10
            factors.append({'factor': 'Historical Alignment', 'impact': '+10', 'detail': f'Tracking within normal range ({ratio:.1f}x avg)'})
        else:
            score -= 5
            factors.append({'factor': 'Historical Alignment', 'impact': '-5', 'detail': f'Unusual trajectory ({ratio:.1f}x avg)'})

    # Calculate confidence level
    score = max(0, min(100, score))
    if score >= 75:
        level = 'HIGH'
    elif score >= 50:
        level = 'MEDIUM'
    else:
        level = 'LOW'

    # Calculate range based on confidence
    weighted_proj = sum(p['projected'] * p['weight'] for p in projections)
    range_factor = (100 - score) / 100 * 0.4  # Lower confidence = wider range

    return {
        'score': score,
        'level': level,
        'factors': factors,
        'projected_final': round(weighted_proj, 0),
        'range_low': round(weighted_proj * (1 - range_factor), 0),
        'range_high': round(weighted_proj * (1 + range_factor), 0)
    }

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

def record_balance(balance):
    """Record a balance data point for velocity tracking"""
    with balance_history_lock:
        balance_history.append((datetime.utcnow(), balance))

def calculate_velocity(minutes_lookback):
    """Calculate the rate of change over the specified time period"""
    with balance_history_lock:
        if len(balance_history) < 2:
            return None

        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=minutes_lookback)

        # Find data points within the lookback period
        recent_points = [(ts, bal) for ts, bal in balance_history if ts >= cutoff]

        if len(recent_points) < 2:
            # Not enough data in this period, use all available data
            recent_points = list(balance_history)

        if len(recent_points) < 2:
            return None

        # Calculate velocity (change per hour)
        oldest = recent_points[0]
        newest = recent_points[-1]

        time_diff_hours = (newest[0] - oldest[0]).total_seconds() / 3600
        if time_diff_hours < 0.001:  # Less than 3.6 seconds
            return None

        balance_diff = newest[1] - oldest[1]
        velocity_per_hour = balance_diff / time_diff_hours

        return {
            'velocity_per_hour': velocity_per_hour,
            'velocity_per_minute': velocity_per_hour / 60,
            'time_span_minutes': time_diff_hours * 60,
            'balance_change': balance_diff,
            'start_balance': oldest[1],
            'end_balance': newest[1],
            'data_points': len(recent_points)
        }

def calculate_velocity_projection(current_balance, hours_remaining):
    """Calculate projected final raise based on different velocity timeframes"""
    velocities = {}
    projections = {}

    # Calculate velocities for different time periods
    periods = [
        ('5m', 5),
        ('10m', 10),
        ('30m', 30),
        ('1h', 60),
        ('2h', 120),
    ]

    for name, minutes in periods:
        vel = calculate_velocity(minutes)
        if vel and vel['velocity_per_hour'] is not None:
            velocities[name] = vel
            # Project final based on this velocity
            projected_additional = vel['velocity_per_hour'] * hours_remaining
            projections[name] = {
                'projected_final': current_balance + projected_additional,
                'velocity_per_hour': vel['velocity_per_hour'],
                'velocity_per_minute': vel['velocity_per_minute'],
                'data_points': vel['data_points'],
                'time_span_minutes': vel['time_span_minutes']
            }

    # Calculate weighted average projection (more weight to recent data)
    weights = {'5m': 0.35, '10m': 0.30, '30m': 0.20, '1h': 0.10, '2h': 0.05}
    weighted_sum = 0
    weight_total = 0

    for period, weight in weights.items():
        if period in projections:
            weighted_sum += projections[period]['projected_final'] * weight
            weight_total += weight

    weighted_projection = weighted_sum / weight_total if weight_total > 0 else current_balance

    return {
        'velocities': velocities,
        'projections': projections,
        'weighted_projection': weighted_projection,
        'current_balance': current_balance,
        'hours_remaining': hours_remaining
    }

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

    # Record balance for velocity tracking
    record_balance(balance)

    projections = calculate_projections(balance, hours_remaining)
    model_probs = calculate_model_probabilities(projections)
    confidence = calculate_confidence(projections, balance, hours_remaining)
    historical_snapshots = get_historical_at_time(hours_remaining)

    # Calculate velocity-based projections
    velocity_data = calculate_velocity_projection(balance, hours_remaining)

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

    # Determine refresh rate based on time remaining
    if hours_remaining <= 1:
        refresh_rate = 5  # 5 seconds in last hour
    elif hours_remaining <= 2:
        refresh_rate = 10  # 10 seconds in last 2 hours
    else:
        refresh_rate = 30  # 30 seconds otherwise

    # Calculate combined projection (historical patterns + velocity)
    historical_weighted = sum(p['projected'] * p['weight'] for p in projections)
    velocity_weighted = velocity_data.get('weighted_projection', balance)

    # Blend historical and velocity projections (60% historical, 40% velocity when we have good data)
    if velocity_data.get('projections'):
        combined_projection = (historical_weighted * 0.6) + (velocity_weighted * 0.4)
    else:
        combined_projection = historical_weighted

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
        'sale_ended': hours_remaining <= 0,
        'refresh_rate': refresh_rate,
        'velocity': velocity_data,
        'combined_projection': round(combined_projection, 0),
        'historical_projection': round(historical_weighted, 0),
        'data_points_collected': len(balance_history),
        'confidence': confidence,
        'historical_snapshots': historical_snapshots
    })

@app.route('/api/historical')
def get_historical():
    """Return historical patterns data"""
    return jsonify(HISTORICAL_PATTERNS)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
