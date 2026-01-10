# MetaDAO Raise Tracker

Real-time tracking and analysis dashboard for MetaDAO public sales on Solana.

## Features

- **Live Balance Tracking**: Fetches current USDC balance from Solana RPC
- **Historical Pattern Analysis**: Compares against previous MetaDAO raises (Umbra, Solomon, Loyal, Avici, zkSOL, Paystream)
- **Projection Models**: Calculates expected final raise amounts based on recency-weighted historical multipliers
- **Polymarket Integration**: Fetches and compares odds from Polymarket prediction markets
- **Value Signals**: Identifies potential mispricings between model estimates and market odds
- **Dynamic Refresh**: 5s refresh in last hour, 10s in last 2 hours, 30s otherwise

## Deployment

### Netlify (Recommended)

1. Connect your GitHub repo to Netlify
2. Build settings are auto-configured via `netlify.toml`
3. Deploy automatically on push

### Local Development

```bash
pip install flask flask-cors requests
python3 app.py
```

Open http://localhost:8080 in your browser.

### CLI Analysis

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

Edit the following in `app.py` (or `netlify/functions/data.js` for Netlify):

- `RANGER_WALLET` - Solana wallet address to track
- `SALE_END_TIME` - Expected end time of the raise
- `HISTORICAL_PATTERNS` - Reference data from past raises
- `PATTERN_WEIGHTS` - Recency-weighted probabilities for each historical sale

## Tech Stack

- **Backend**: Python/Flask (local) or Netlify Functions (deployed)
- **Frontend**: Vanilla JS with Chart.js
- **Data Source**: Solana RPC, Polymarket API
