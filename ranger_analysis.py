#!/usr/bin/env python3
"""
Ranger Finance Raise Tracker
Automatically analyzes raise progress and compares to historical MetaDAO raises
"""

import json
import subprocess
import os
from datetime import datetime, timedelta
from collections import defaultdict

# Configuration
RANGER_WALLET = "9ApaAe39Z8GEXfqm7F7HL545N4J4tN7RhF8FhS88pRNp"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
DUNE_API_KEY = "zbPi4q55eVkn3ZGLNbUv6ikztwFBWoJz"

# Sale end time (approximately 5h 26m from when user told us, which was ~10:30 UTC on Jan 10)
# So end time is approximately 16:00 UTC on Jan 10, 2026
SALE_END_TIME = datetime(2026, 1, 10, 16, 0, 0)  # Adjust if needed

# Historical patterns at 5.5h before end (from our analysis)
HISTORICAL_PATTERNS = {
    'Umbra': {'at_5_5h': 44220255, 'final': 155194912, 'pct_at_5_5h': 28.5},
    'Solomon': {'at_5_5h': 11779124, 'final': 102932688, 'pct_at_5_5h': 11.4},
    'Loyal': {'at_5_5h': 16437386, 'final': 75898234, 'pct_at_5_5h': 21.7},
    'Avici': {'at_5_5h': 8036796, 'final': 34233177, 'pct_at_5_5h': 23.5},
    'zkSOL': {'at_5_5h': 2427947, 'final': 14886360, 'pct_at_5_5h': 16.3},
    'Paystream': {'at_5_5h': 1319085, 'final': 6149247, 'pct_at_5_5h': 21.5},
}

def get_ranger_balance():
    """Fetch current USDC balance from Solana RPC"""
    cmd = f'''curl -s 'https://api.mainnet-beta.solana.com' -X POST -H "Content-Type: application/json" -d '{{"jsonrpc":"2.0","id":1,"method":"getTokenAccountsByOwner","params":["{RANGER_WALLET}",{{"mint":"{USDC_MINT}"}},{{"encoding":"jsonParsed"}}]}}'  '''
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    try:
        data = json.loads(result.stdout)
        accounts = data.get('result', {}).get('value', [])
        if accounts:
            amount = accounts[0]['account']['data']['parsed']['info']['tokenAmount']['uiAmount']
            return amount
    except Exception as e:
        print(f"Error fetching balance: {e}")
    return None

def get_transaction_count():
    """Fetch recent transaction signatures to estimate activity"""
    cmd = f'''curl -s 'https://api.mainnet-beta.solana.com' -X POST -H "Content-Type: application/json" -d '{{"jsonrpc":"2.0","id":1,"method":"getSignaturesForAddress","params":["{RANGER_WALLET}",{{"limit":1000}}]}}'  '''
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    try:
        data = json.loads(result.stdout)
        sigs = data.get('result', [])
        successful = [s for s in sigs if s.get('err') is None]
        
        # Get timestamps
        if successful:
            latest_ts = successful[0].get('blockTime', 0)
            earliest_ts = successful[-1].get('blockTime', 0)
            
            # Count by hour for recent activity
            hourly = defaultdict(int)
            for tx in successful:
                ts = tx.get('blockTime', 0)
                if ts > 0:
                    dt = datetime.utcfromtimestamp(ts)
                    hour_key = dt.strftime('%Y-%m-%d %H:00')
                    hourly[hour_key] += 1
            
            return {
                'total': len(successful),
                'latest_ts': latest_ts,
                'earliest_ts': earliest_ts,
                'hourly': dict(hourly)
            }
    except Exception as e:
        print(f"Error fetching transactions: {e}")
    return None

def calculate_projections(current_balance, hours_remaining):
    """Calculate projections based on historical patterns"""
    projections = []
    
    for name, data in HISTORICAL_PATTERNS.items():
        # Calculate multiplier from current position to final
        mult = data['final'] / data['at_5_5h']
        
        # Scale based on hours remaining (patterns were at 5.5h)
        # Adjust multiplier based on time difference
        time_factor = hours_remaining / 5.5
        adjusted_mult = 1 + (mult - 1) * time_factor
        
        projected = current_balance * adjusted_mult
        
        projections.append({
            'name': name,
            'multiplier': adjusted_mult,
            'projected': projected,
            'pattern_final': data['final'],
            'pattern_pct_at_5_5h': data['pct_at_5_5h']
        })
    
    return sorted(projections, key=lambda x: x['projected'])

def analyze_polymarket_odds(projections):
    """Compare projections against typical Polymarket thresholds"""
    thresholds = [15, 20, 30, 40, 50, 60, 70, 80, 90, 100, 120, 140, 160, 180, 200]
    
    # Assign probability weights to each pattern
    pattern_weights = {
        'Solomon': 0.30,  # Closest $ match
        'Loyal': 0.25,
        'Avici': 0.15,
        'zkSOL': 0.15,
        'Paystream': 0.10,
        'Umbra': 0.05,
    }
    
    threshold_probs = {}
    for t in thresholds:
        prob = 0
        for p in projections:
            if p['projected'] >= t * 1_000_000:
                prob += pattern_weights.get(p['name'], 0)
        threshold_probs[t] = prob * 100
    
    return threshold_probs

def run_analysis():
    """Main analysis function"""
    now = datetime.utcnow()
    time_remaining = SALE_END_TIME - now
    hours_remaining = time_remaining.total_seconds() / 3600
    
    if hours_remaining <= 0:
        print("=" * 80)
        print("SALE HAS ENDED")
        print("=" * 80)
        return False
    
    print("=" * 80)
    print(f"RANGER FINANCE RAISE TRACKER - {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 80)
    print()
    
    # Get current data
    balance = get_ranger_balance()
    tx_data = get_transaction_count()
    
    if balance is None:
        print("ERROR: Could not fetch balance")
        return True
    
    print(f"TIME REMAINING: {int(hours_remaining)}h {int((hours_remaining % 1) * 60)}m")
    print(f"CURRENT BALANCE: ${balance:,.2f} USDC")
    if tx_data:
        print(f"RECENT TRANSACTIONS: {tx_data['total']} (last 1000 slots)")
    print()
    
    # Calculate projections
    projections = calculate_projections(balance, hours_remaining)
    
    print("PROJECTIONS BY HISTORICAL PATTERN:")
    print("-" * 80)
    print(f"{'Pattern':<12} {'Multiplier':>10} {'Projected Final':>20} {'Surge Remaining':>20}")
    print("-" * 80)
    
    for p in projections:
        surge = p['projected'] - balance
        print(f"{p['name']:<12} {p['multiplier']:>9.2f}x ${p['projected']:>18,.0f} ${surge:>18,.0f}")
    
    print("-" * 80)
    print()
    
    # Model probabilities for thresholds
    threshold_probs = analyze_polymarket_odds(projections)
    
    print("MODEL PROBABILITY ESTIMATES:")
    print("-" * 80)
    print(f"{'Threshold':<12} {'Model Prob':>12} {'Notes':>40}")
    print("-" * 80)
    
    for t, prob in sorted(threshold_probs.items()):
        note = ""
        if prob >= 90:
            note = "Very likely"
        elif prob >= 70:
            note = "Likely"
        elif prob >= 50:
            note = "Coin flip"
        elif prob >= 30:
            note = "Possible"
        elif prob > 0:
            note = "Unlikely"
        else:
            note = "Very unlikely"
        print(f">${t}M{'':<7} {prob:>11.0f}% {note:>40}")
    
    print("-" * 80)
    print()
    
    # Recent hourly activity
    if tx_data and tx_data['hourly']:
        print("RECENT HOURLY ACTIVITY:")
        print("-" * 80)
        sorted_hours = sorted(tx_data['hourly'].keys())[-6:]  # Last 6 hours
        for hour in sorted_hours:
            count = tx_data['hourly'][hour]
            print(f"  {hour}: {count} transactions")
        print()
    
    # Summary
    proj_values = [p['projected'] for p in projections]
    min_proj = min(proj_values)
    max_proj = max(proj_values)
    mid_proj = sorted(proj_values)[len(proj_values)//2]
    
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"  Current:    ${balance:,.0f}")
    print(f"  Min Proj:   ${min_proj:,.0f}")
    print(f"  Mid Proj:   ${mid_proj:,.0f}")
    print(f"  Max Proj:   ${max_proj:,.0f}")
    print(f"  Time Left:  {int(hours_remaining)}h {int((hours_remaining % 1) * 60)}m")
    print("=" * 80)
    print()
    
    # Save to log file
    log_entry = {
        'timestamp': now.isoformat(),
        'hours_remaining': hours_remaining,
        'balance': balance,
        'projections': {p['name']: p['projected'] for p in projections},
        'tx_count': tx_data['total'] if tx_data else None
    }
    
    log_file = os.path.expanduser('~/ranger-tracker/ranger_log.jsonl')
    with open(log_file, 'a') as f:
        f.write(json.dumps(log_entry) + '\n')
    
    return True

if __name__ == "__main__":
    run_analysis()
