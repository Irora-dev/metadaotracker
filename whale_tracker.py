#!/usr/bin/env python3
"""
Whale Tracker - Analyzes large deposits for MetaDAO sales
"""

import json
import requests
from datetime import datetime, timedelta
from collections import defaultdict
import time

RANGER_WALLET = "9ApaAe39Z8GEXfqm7F7HL545N4J4tN7RhF8FhS88pRNp"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SALE_END_TIME = datetime(2026, 1, 10, 16, 0, 0)

# Whale thresholds
WHALE_THRESHOLD = 10000      # $10k+ is a whale
MEDIUM_THRESHOLD = 1000      # $1k-$10k is medium
MEGA_WHALE_THRESHOLD = 50000 # $50k+ is mega whale

# Historical whale patterns (estimated from final amounts)
# Based on typical MetaDAO sale distribution patterns
HISTORICAL_WHALE_PATTERNS = {
    'Solomon': {
        'final': 102932688,
        'estimated_whale_count': 85,      # ~$1.2M avg per whale
        'estimated_whale_pct': 45,        # 45% from whales
        'mega_whales': 12,
        'at_5h_whale_count': 25,          # Estimated whales at 5h mark
        'at_5h_whale_pct': 35,
    },
    'Umbra': {
        'final': 155194912,
        'estimated_whale_count': 120,
        'estimated_whale_pct': 50,
        'mega_whales': 18,
        'at_5h_whale_count': 35,
        'at_5h_whale_pct': 28,
    },
    'Loyal': {
        'final': 75898234,
        'estimated_whale_count': 60,
        'estimated_whale_pct': 42,
        'mega_whales': 8,
        'at_5h_whale_count': 18,
        'at_5h_whale_pct': 22,
    },
    'Avici': {
        'final': 34233177,
        'estimated_whale_count': 30,
        'estimated_whale_pct': 38,
        'mega_whales': 4,
        'at_5h_whale_count': 9,
        'at_5h_whale_pct': 24,
    },
    'zkSOL': {
        'final': 14886360,
        'estimated_whale_count': 15,
        'estimated_whale_pct': 35,
        'mega_whales': 2,
        'at_5h_whale_count': 5,
        'at_5h_whale_pct': 16,
    },
    'Paystream': {
        'final': 6149247,
        'estimated_whale_count': 8,
        'estimated_whale_pct': 32,
        'mega_whales': 1,
        'at_5h_whale_count': 2,
        'at_5h_whale_pct': 21,
    },
}


def get_transaction_signatures(wallet, limit=1000):
    """Get transaction signatures for a wallet"""
    url = "https://api.mainnet-beta.solana.com"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignaturesForAddress",
        "params": [wallet, {"limit": limit}]
    }

    response = requests.post(url, json=payload)
    data = response.json()
    return data.get('result', [])


def get_transaction_details(signature):
    """Get parsed transaction details"""
    url = "https://api.mainnet-beta.solana.com"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTransaction",
        "params": [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}]
    }

    response = requests.post(url, json=payload)
    data = response.json()
    return data.get('result')


def parse_usdc_deposits(wallet, max_txs=200):
    """Parse USDC deposits to a wallet"""
    print(f"Fetching transactions for {wallet[:8]}...")
    signatures = get_transaction_signatures(wallet)

    deposits = []
    unique_wallets = set()

    print(f"Found {len(signatures)} transactions, parsing up to {max_txs}...")

    for i, sig_info in enumerate(signatures[:max_txs]):
        if sig_info.get('err') is not None:
            continue

        signature = sig_info['signature']
        block_time = sig_info.get('blockTime', 0)

        # Rate limit
        if i > 0 and i % 10 == 0:
            time.sleep(0.5)
            print(f"  Parsed {i}/{min(len(signatures), max_txs)}...")

        try:
            tx = get_transaction_details(signature)
            if not tx:
                continue

            # Look for USDC transfers
            meta = tx.get('meta', {})
            pre_balances = meta.get('preTokenBalances', [])
            post_balances = meta.get('postTokenBalances', [])

            # Find USDC balance changes
            for post in post_balances:
                if post.get('mint') != USDC_MINT:
                    continue

                owner = post.get('owner', '')
                post_amount = float(post.get('uiTokenAmount', {}).get('uiAmount', 0) or 0)

                # Find matching pre-balance
                pre_amount = 0
                for pre in pre_balances:
                    if pre.get('mint') == USDC_MINT and pre.get('owner') == owner:
                        pre_amount = float(pre.get('uiTokenAmount', {}).get('uiAmount', 0) or 0)
                        break

                # If this is the target wallet and balance increased
                if owner == wallet and post_amount > pre_amount:
                    deposit_amount = post_amount - pre_amount

                    # Find the sender
                    sender = None
                    for pre in pre_balances:
                        if pre.get('mint') == USDC_MINT and pre.get('owner') != wallet:
                            pre_bal = float(pre.get('uiTokenAmount', {}).get('uiAmount', 0) or 0)
                            post_bal = 0
                            for p in post_balances:
                                if p.get('owner') == pre.get('owner') and p.get('mint') == USDC_MINT:
                                    post_bal = float(p.get('uiTokenAmount', {}).get('uiAmount', 0) or 0)
                            if pre_bal > post_bal:
                                sender = pre.get('owner')
                                break

                    if deposit_amount > 0:
                        deposits.append({
                            'amount': deposit_amount,
                            'sender': sender,
                            'timestamp': block_time,
                            'signature': signature
                        })
                        if sender:
                            unique_wallets.add(sender)

        except Exception as e:
            continue

    return deposits, unique_wallets


def analyze_whale_activity(deposits):
    """Analyze whale activity from deposits"""
    if not deposits:
        return None

    whales = [d for d in deposits if d['amount'] >= WHALE_THRESHOLD]
    mega_whales = [d for d in deposits if d['amount'] >= MEGA_WHALE_THRESHOLD]
    medium = [d for d in deposits if MEDIUM_THRESHOLD <= d['amount'] < WHALE_THRESHOLD]
    retail = [d for d in deposits if d['amount'] < MEDIUM_THRESHOLD]

    total_volume = sum(d['amount'] for d in deposits)
    whale_volume = sum(d['amount'] for d in whales)
    mega_whale_volume = sum(d['amount'] for d in mega_whales)

    # Unique whale wallets
    whale_wallets = set(d['sender'] for d in whales if d['sender'])

    return {
        'total_deposits': len(deposits),
        'total_volume': total_volume,
        'whale_count': len(whales),
        'whale_volume': whale_volume,
        'whale_pct': (whale_volume / total_volume * 100) if total_volume > 0 else 0,
        'mega_whale_count': len(mega_whales),
        'mega_whale_volume': mega_whale_volume,
        'unique_whale_wallets': len(whale_wallets),
        'medium_count': len(medium),
        'medium_volume': sum(d['amount'] for d in medium),
        'retail_count': len(retail),
        'retail_volume': sum(d['amount'] for d in retail),
        'avg_deposit': total_volume / len(deposits) if deposits else 0,
        'avg_whale_deposit': whale_volume / len(whales) if whales else 0,
        'largest_deposit': max(d['amount'] for d in deposits) if deposits else 0,
        'top_10_deposits': sorted(deposits, key=lambda x: x['amount'], reverse=True)[:10]
    }


def compare_to_historical(current_whale_data, hours_remaining):
    """Compare current whale activity to historical patterns"""
    comparisons = []

    for name, pattern in HISTORICAL_WHALE_PATTERNS.items():
        # Estimate expected whale count at current time
        # Whales tend to come in late, so use exponential curve
        time_factor = (5.5 - hours_remaining) / 5.5 if hours_remaining <= 5.5 else 0

        expected_whale_count = pattern['at_5h_whale_count'] + \
            (pattern['estimated_whale_count'] - pattern['at_5h_whale_count']) * (time_factor ** 0.7)

        expected_whale_pct = pattern['at_5h_whale_pct'] + \
            (pattern['estimated_whale_pct'] - pattern['at_5h_whale_pct']) * (time_factor ** 0.7)

        # Compare current to expected
        whale_count_ratio = current_whale_data['whale_count'] / expected_whale_count if expected_whale_count > 0 else 0
        whale_pct_diff = current_whale_data['whale_pct'] - expected_whale_pct

        comparisons.append({
            'name': name,
            'final_raised': pattern['final'],
            'expected_whale_count': round(expected_whale_count, 1),
            'actual_whale_count': current_whale_data['whale_count'],
            'whale_count_ratio': round(whale_count_ratio, 2),
            'expected_whale_pct': round(expected_whale_pct, 1),
            'actual_whale_pct': round(current_whale_data['whale_pct'], 1),
            'whale_pct_diff': round(whale_pct_diff, 1),
            'signal': 'ABOVE' if whale_count_ratio > 1.1 else 'BELOW' if whale_count_ratio < 0.9 else 'ON_TRACK'
        })

    return sorted(comparisons, key=lambda x: x['final_raised'], reverse=True)


def project_final_from_whales(current_whale_data, hours_remaining):
    """Project final raise based on whale activity patterns"""
    projections = []

    for name, pattern in HISTORICAL_WHALE_PATTERNS.items():
        # If current whale activity matches this pattern, project final
        if pattern['at_5h_whale_count'] > 0:
            whale_ratio = current_whale_data['whale_count'] / pattern['at_5h_whale_count']

            # Project based on whale count extrapolation
            projected_final = pattern['final'] * whale_ratio

            # Adjust for time remaining
            if hours_remaining < 5.5:
                time_factor = hours_remaining / 5.5
                projected_final = projected_final * (1 + (1 - time_factor) * 0.5)

            projections.append({
                'name': name,
                'projected_final': round(projected_final, 0),
                'whale_ratio': round(whale_ratio, 2),
                'confidence': 'HIGH' if 0.8 <= whale_ratio <= 1.2 else 'MEDIUM'
            })

    return projections


def main():
    print("=" * 60)
    print("RANGER FINANCE WHALE TRACKER")
    print("=" * 60)

    now = datetime.utcnow()
    time_remaining = SALE_END_TIME - now
    hours_remaining = max(0, time_remaining.total_seconds() / 3600)

    print(f"\nTime remaining: {hours_remaining:.2f} hours")
    print(f"\nFetching deposit data (this may take a minute)...")

    # Parse deposits
    deposits, unique_wallets = parse_usdc_deposits(RANGER_WALLET, max_txs=300)

    if not deposits:
        print("No deposits found!")
        return

    # Analyze whale activity
    whale_data = analyze_whale_activity(deposits)

    print("\n" + "=" * 60)
    print("CURRENT WHALE ACTIVITY")
    print("=" * 60)
    print(f"\nTotal deposits parsed: {whale_data['total_deposits']}")
    print(f"Total volume: ${whale_data['total_volume']:,.0f}")
    print(f"Unique contributors: {len(unique_wallets)}")
    print(f"\nWhale deposits (>$10k): {whale_data['whale_count']}")
    print(f"Whale volume: ${whale_data['whale_volume']:,.0f} ({whale_data['whale_pct']:.1f}%)")
    print(f"Mega whale deposits (>$50k): {whale_data['mega_whale_count']}")
    print(f"Mega whale volume: ${whale_data['mega_whale_volume']:,.0f}")
    print(f"\nAverage deposit: ${whale_data['avg_deposit']:,.0f}")
    print(f"Largest deposit: ${whale_data['largest_deposit']:,.0f}")

    print("\n" + "=" * 60)
    print("TOP 10 DEPOSITS")
    print("=" * 60)
    for i, dep in enumerate(whale_data['top_10_deposits'], 1):
        ts = datetime.utcfromtimestamp(dep['timestamp']).strftime('%H:%M') if dep['timestamp'] else 'N/A'
        print(f"{i}. ${dep['amount']:>12,.0f}  ({ts})")

    # Compare to historical
    print("\n" + "=" * 60)
    print("COMPARISON TO HISTORICAL SALES")
    print("=" * 60)
    comparisons = compare_to_historical(whale_data, hours_remaining)

    print(f"\n{'Sale':<12} {'Expected':<10} {'Actual':<10} {'Ratio':<8} {'Signal':<10}")
    print("-" * 55)
    for comp in comparisons:
        print(f"{comp['name']:<12} {comp['expected_whale_count']:<10.0f} {comp['actual_whale_count']:<10} {comp['whale_count_ratio']:<8.2f} {comp['signal']:<10}")

    # Whale-based projections
    print("\n" + "=" * 60)
    print("WHALE-BASED PROJECTIONS")
    print("=" * 60)
    projections = project_final_from_whales(whale_data, hours_remaining)

    for proj in sorted(projections, key=lambda x: x['projected_final']):
        print(f"{proj['name']:<12} -> ${proj['projected_final']/1e6:>6.1f}M (whale ratio: {proj['whale_ratio']:.2f})")

    # Return data for API use
    return {
        'whale_data': whale_data,
        'comparisons': comparisons,
        'projections': projections,
        'unique_wallets': len(unique_wallets),
        'hours_remaining': hours_remaining
    }


if __name__ == '__main__':
    main()
