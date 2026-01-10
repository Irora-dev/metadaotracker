// Ranger Finance Raise Tracker - Netlify Serverless Function

const RANGER_WALLET = "9ApaAe39Z8GEXfqm7F7HL545N4J4tN7RhF8FhS88pRNp";
const USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v";
const SALE_END_TIME = new Date("2026-01-10T16:00:00Z");

// Historical patterns at 5.5h before end (ordered oldest to newest)
const HISTORICAL_PATTERNS = {
  'Umbra': { at_5_5h: 44220255, final: 155194912, pct_at_5_5h: 28.5, sale_date: '2025-10-10', order: 1 },
  'Avici': { at_5_5h: 8036796, final: 34233177, pct_at_5_5h: 23.5, sale_date: '2025-10-18', order: 2 },
  'Loyal': { at_5_5h: 16437386, final: 75898234, pct_at_5_5h: 21.7, sale_date: '2025-10-22', order: 3 },
  'zkSOL': { at_5_5h: 2427947, final: 14886360, pct_at_5_5h: 16.3, sale_date: '2025-10-24', order: 4 },
  'Paystream': { at_5_5h: 1319085, final: 6149247, pct_at_5_5h: 21.5, sale_date: '2025-10-27', order: 5 },
  'Solomon': { at_5_5h: 11779124, final: 102932688, pct_at_5_5h: 11.4, sale_date: '2025-11-18', order: 6 },
};

// Recency-weighted pattern probabilities
const PATTERN_WEIGHTS = {
  'Solomon': 0.35,
  'Paystream': 0.25,
  'zkSOL': 0.17,
  'Loyal': 0.12,
  'Avici': 0.07,
  'Umbra': 0.04,
};

async function getRangerBalance() {
  try {
    const response = await fetch('https://api.mainnet-beta.solana.com', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jsonrpc: '2.0',
        id: 1,
        method: 'getTokenAccountsByOwner',
        params: [
          RANGER_WALLET,
          { mint: USDC_MINT },
          { encoding: 'jsonParsed' }
        ]
      })
    });
    const data = await response.json();
    const accounts = data.result?.value || [];
    if (accounts.length > 0) {
      return accounts[0].account.data.parsed.info.tokenAmount.uiAmount;
    }
  } catch (e) {
    console.error('Error fetching balance:', e);
  }
  return null;
}

async function getTransactionData() {
  try {
    const response = await fetch('https://api.mainnet-beta.solana.com', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jsonrpc: '2.0',
        id: 1,
        method: 'getSignaturesForAddress',
        params: [RANGER_WALLET, { limit: 1000 }]
      })
    });
    const data = await response.json();
    const sigs = data.result || [];
    const successful = sigs.filter(s => s.err === null);

    const hourly = {};
    for (const tx of successful) {
      if (tx.blockTime > 0) {
        const dt = new Date(tx.blockTime * 1000);
        const hourKey = dt.toISOString().slice(0, 13) + ':00';
        hourly[hourKey] = (hourly[hourKey] || 0) + 1;
      }
    }

    return { total: successful.length, hourly };
  } catch (e) {
    console.error('Error fetching transactions:', e);
  }
  return null;
}

async function getPolymarketOdds() {
  let odds = {};
  try {
    const response = await fetch(
      'https://gamma-api.polymarket.com/events?slug=total-commitments-for-the-ranger-public-sale-on-metadao',
      { headers: { Accept: 'application/json' } }
    );
    if (response.ok) {
      const data = await response.json();
      if (data && data.length > 0) {
        const markets = data[0].markets || [];
        for (const market of markets) {
          const question = (market.question || '').toLowerCase();
          const match = question.match(/over\s*\$?(\d+)m/);
          if (match) {
            const threshold = parseInt(match[1]);
            const prices = market.outcomePrices || [];
            if (prices.length > 0) {
              odds[threshold] = parseFloat(prices[0]) * 100;
            }
          }
        }
      }
    }
  } catch (e) {
    console.error('Error fetching Polymarket:', e);
  }

  // Fallback cached odds
  if (Object.keys(odds).length === 0) {
    odds = {
      15: 100, 20: 100, 30: 99, 40: 98, 50: 87,
      60: 83, 70: 74, 80: 64, 90: 56, 100: 45,
      120: 31, 140: 16, 160: 10, 180: 8, 200: 6
    };
  }

  return odds;
}

function calculateProjections(balance, hoursRemaining) {
  const projections = [];

  for (const [name, data] of Object.entries(HISTORICAL_PATTERNS)) {
    const mult = data.final / data.at_5_5h;
    const timeFactor = hoursRemaining / 5.5;
    const adjustedMult = 1 + (mult - 1) * timeFactor;
    const projected = balance * adjustedMult;

    projections.push({
      name,
      multiplier: Math.round(adjustedMult * 100) / 100,
      projected: Math.round(projected),
      weight: PATTERN_WEIGHTS[name] || 0,
      sale_date: data.sale_date || '',
      order: data.order || 0,
      final_raised: data.final
    });
  }

  return projections.sort((a, b) => a.projected - b.projected);
}

function calculateModelProbabilities(projections) {
  const thresholds = [15, 20, 30, 40, 50, 60, 70, 80, 90, 100, 120, 140, 160, 180, 200];
  const probs = {};

  for (const t of thresholds) {
    let prob = 0;
    for (const p of projections) {
      if (p.projected >= t * 1000000) {
        prob += p.weight;
      }
    }
    probs[t] = Math.round(prob * 1000) / 10;
  }

  return probs;
}

export async function handler(event, context) {
  const now = new Date();
  const timeRemaining = SALE_END_TIME - now;
  const hoursRemaining = Math.max(0, timeRemaining / (1000 * 3600));

  const [balance, txData, polymarketOdds] = await Promise.all([
    getRangerBalance(),
    getTransactionData(),
    getPolymarketOdds()
  ]);

  if (balance === null) {
    return {
      statusCode: 500,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ error: 'Could not fetch balance' })
    };
  }

  const projections = calculateProjections(balance, hoursRemaining);
  const modelProbs = calculateModelProbabilities(projections);

  // Calculate opportunities
  const opportunities = {};
  for (const threshold of Object.keys(modelProbs)) {
    const t = parseInt(threshold);
    const pmOdds = polymarketOdds[t] || 50;
    const modelOdds = modelProbs[t];
    const diff = modelOdds - pmOdds;

    if (diff > 10) {
      opportunities[t] = { action: 'BUY YES', edge: Math.round(diff * 10) / 10 };
    } else if (diff < -10) {
      opportunities[t] = { action: 'BUY NO', edge: Math.round(Math.abs(diff) * 10) / 10 };
    } else {
      opportunities[t] = { action: 'FAIR', edge: 0 };
    }
  }

  // Hourly data for chart
  const hourlyData = [];
  if (txData && txData.hourly) {
    const sortedHours = Object.keys(txData.hourly).sort().slice(-12);
    for (const hour of sortedHours) {
      hourlyData.push({
        hour: hour.slice(11, 16),
        transactions: txData.hourly[hour]
      });
    }
  }

  // Dynamic refresh rate
  let refreshRate = 30;
  if (hoursRemaining <= 1) {
    refreshRate = 5;
  } else if (hoursRemaining <= 2) {
    refreshRate = 10;
  }

  // Calculate weighted projection
  const historicalWeighted = projections.reduce((sum, p) => sum + p.projected * p.weight, 0);

  return {
    statusCode: 200,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*'
    },
    body: JSON.stringify({
      timestamp: now.toISOString(),
      hours_remaining: Math.round(hoursRemaining * 100) / 100,
      minutes_remaining: Math.floor(hoursRemaining * 60),
      balance,
      transactions: txData?.total || 0,
      projections,
      model_probabilities: modelProbs,
      polymarket_odds: polymarketOdds,
      opportunities,
      hourly_activity: hourlyData,
      sale_ended: hoursRemaining <= 0,
      refresh_rate: refreshRate,
      combined_projection: Math.round(historicalWeighted),
      historical_projection: Math.round(historicalWeighted),
      data_points_collected: 0
    })
  };
}
