# MetaDAO Raise Tracker

Real-time tracking and analysis dashboard for MetaDAO public sales on Solana.

## Features

- **Live Balance Tracking**: Fetches current USDC balance from Solana RPC
- **Historical Pattern Analysis**: Compares against previous MetaDAO raises (Umbra, Solomon, Loyal, Avici, zkSOL, Paystream)
- **Projection Models**: Calculates expected final raise amounts based on historical multipliers
- **Polymarket Integration**: Fetches and compares odds from Polymarket prediction markets
- **Value Signals**: Identifies potential mispricings between model estimates and market odds

## Installation

```bash
pip install flask flask-cors requests
```

## Usage

### Start the Web Dashboard

```bash
python3 app.py
```

Open http://localhost:8080 in your browser.

### Run CLI Analysis

```bash
python3 ranger_analysis.py
```

### Auto-Running Tracker (every 30 minutes)

```bash
./run_tracker.sh
```

## API Endpoints

- `GET /` - Web dashboard
- `GET /api/data` - Current raise data, projections, and opportunities
- `GET /api/historical` - Historical pattern data

## Configuration

Edit the following in `app.py`:

- `RANGER_WALLET` - Solana wallet address to track
- `SALE_END_TIME` - Expected end time of the raise
- `HISTORICAL_PATTERNS` - Reference data from past raises

## Tech Stack

- **Backend**: Python/Flask
- **Frontend**: Vanilla JS with Chart.js
- **Data Source**: Solana RPC, Polymarket API
