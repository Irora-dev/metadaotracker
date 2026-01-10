// Ranger Finance Raise Tracker - Netlify Serverless Function

const RANGER_WALLET = "9ApaAe39Z8GEXfqm7F7HL545N4J4tN7RhF8FhS88pRNp";
const USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v";
const SALE_END_TIME = new Date("2026-01-10T16:00:00Z");

// Historical patterns with time-based snapshots
const HISTORICAL_PATTERNS = {
  'Umbra': {
    final: 155194912,
    sale_date: '2025-10-10',
    order: 1,
    snapshots: {
      6.0: 38000000, 5.5: 44220255, 5.0: 51000000, 4.5: 59000000,
      4.0: 68000000, 3.5: 78000000, 3.0: 89000000, 2.5: 102000000,
      2.0: 115000000, 1.5: 128000000, 1.0: 140000000, 0.5: 150000000
    }
  },
  'Avici': {
    final: 34233177,
    sale_date: '2025-10-18',
    order: 2,
    snapshots: {
      6.0: 6800000, 5.5: 8036796, 5.0: 9500000, 4.5: 11200000,
      4.0: 13200000, 3.5: 15500000, 3.0: 18200000, 2.5: 21500000,
      2.0: 25000000, 1.5: 28500000, 1.0: 31500000, 0.5: 33500000
    }
  },
  'Loyal': {
    final: 75898234,
    sale_date: '2025-10-22',
    order: 3,
    snapshots: {
      6.0: 13500000, 5.5: 16437386, 5.0: 20000000, 4.5: 24500000,
      4.0: 30000000, 3.5: 36500000, 3.0: 44000000, 2.5: 52000000,
      2.0: 60000000, 1.5: 67000000, 1.0: 72000000, 0.5: 75000000
    }
  },
  'zkSOL': {
    final: 14886360,
    sale_date: '2025-10-24',
    order: 4,
    snapshots: {
      6.0: 2000000, 5.5: 2427947, 5.0: 3000000, 4.5: 3800000,
      4.0: 4800000, 3.5: 6000000, 3.0: 7500000, 2.5: 9200000,
      2.0: 11000000, 1.5: 12800000, 1.0: 14000000, 0.5: 14700000
    }
  },
  'Paystream': {
    final: 6149247,
    sale_date: '2025-10-27',
    order: 5,
    snapshots: {
      6.0: 1100000, 5.5: 1319085, 5.0: 1600000, 4.5: 2000000,
      4.0: 2500000, 3.5: 3100000, 3.0: 3800000, 2.5: 4500000,
      2.0: 5100000, 1.5: 5600000, 1.0: 5900000, 0.5: 6100000
    }
  },
  'Solomon': {
    final: 102932688,
    sale_date: '2025-11-18',
    order: 6,
    snapshots: {
      6.0: 9500000, 5.5: 11779124, 5.0: 15000000, 4.5: 19500000,
      4.0: 26000000, 3.5: 35000000, 3.0: 46000000, 2.5: 58000000,
      2.0: 70000000, 1.5: 82000000, 1.0: 92000000, 0.5: 100000000
    }
  }
};

const PATTERN_WEIGHTS = {
  'Solomon': 0.35,
  'Paystream': 0.25,
  'zkSOL': 0.17,
  'Loyal': 0.12,
  'Avici': 0.07,
  'Umbra': 0.04
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
        params: [RANGER_WALLET, { mint: USDC_MINT }, { encoding: 'jsonParsed' }]
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

  // Fallback cached odds if API fails
  if (Object.keys(odds).length === 0) {
    odds = {
      15: 100, 20: 100, 30: 99, 40: 98, 50: 87,
      60: 83, 70: 74, 80: 64, 90: 56, 100: 45,
      120: 31, 140: 16, 160: 10, 180: 8, 200: 6
    };
  }
  return odds;
}

function getHistoricalAtTime(hoursRemaining) {
  const lookupTime = Math.round(hoursRemaining * 2) / 2;
  const clampedTime = Math.max(0.5, Math.min(6.0, lookupTime));

  const snapshots = [];
  for (const [name, data] of Object.entries(HISTORICAL_PATTERNS)) {
    const snapshotValue = data.snapshots[clampedTime];
    if (snapshotValue) {
      snapshots.push({
        name,
        amount: snapshotValue,
        final: data.final,
        pct_of_final: Math.round(snapshotValue / data.final * 1000) / 10,
        sale_date: data.sale_date,
        order: data.order
      });
    }
  }
  return snapshots.sort((a, b) => a.order - b.order);
}

function calculateProjections(balance, hoursRemaining) {
  const lookupTime = Math.round(hoursRemaining * 2) / 2;
  const clampedTime = Math.max(0.5, Math.min(6.0, lookupTime));

  const projections = [];
  for (const [name, data] of Object.entries(HISTORICAL_PATTERNS)) {
    const snapshotAtTime = data.snapshots[clampedTime] || data.snapshots[5.5];
    const mult = snapshotAtTime ? data.final / snapshotAtTime : 1;
    const projected = balance * mult;

    projections.push({
      name,
      multiplier: Math.round(mult * 100) / 100,
      projected: Math.round(projected),
      weight: PATTERN_WEIGHTS[name] || 0,
      sale_date: data.sale_date || '',
      order: data.order || 0,
      final_raised: data.final,
      snapshot_used: snapshotAtTime
    });
  }
  return projections.sort((a, b) => a.projected - b.projected);
}

function calculateConfidence(projections, balance, hoursRemaining) {
  if (!projections.length) return { score: 0, level: 'LOW', factors: [] };

  const factors = [];
  let score = 50;

  // Factor 1: Model agreement
  const projectedValues = projections.map(p => p.projected);
  const meanProj = projectedValues.reduce((a, b) => a + b, 0) / projectedValues.length;
  const variance = projectedValues.reduce((sum, p) => sum + Math.pow(p - meanProj, 2), 0) / projectedValues.length;
  const stdDev = Math.sqrt(variance);
  const cv = meanProj > 0 ? stdDev / meanProj : 1;

  if (cv < 0.3) {
    score += 20;
    factors.push({ factor: 'Model Agreement', impact: '+20', detail: 'Projections closely aligned' });
  } else if (cv < 0.5) {
    score += 10;
    factors.push({ factor: 'Model Agreement', impact: '+10', detail: 'Moderate projection spread' });
  } else {
    score -= 10;
    factors.push({ factor: 'Model Agreement', impact: '-10', detail: 'Wide projection spread' });
  }

  // Factor 2: Time remaining
  if (hoursRemaining <= 1) {
    score += 25;
    factors.push({ factor: 'Time Proximity', impact: '+25', detail: 'Final hour - high certainty' });
  } else if (hoursRemaining <= 2) {
    score += 15;
    factors.push({ factor: 'Time Proximity', impact: '+15', detail: 'Last 2 hours - good certainty' });
  } else if (hoursRemaining <= 4) {
    score += 5;
    factors.push({ factor: 'Time Proximity', impact: '+5', detail: 'Within 4 hours' });
  } else {
    score -= 10;
    factors.push({ factor: 'Time Proximity', impact: '-10', detail: 'More than 4 hours remaining' });
  }

  // Factor 3: Historical alignment
  const historicalSnapshots = getHistoricalAtTime(hoursRemaining);
  if (historicalSnapshots.length) {
    const avgHistorical = historicalSnapshots.reduce((sum, s) => sum + s.amount, 0) / historicalSnapshots.length;
    const ratio = avgHistorical > 0 ? balance / avgHistorical : 0;

    if (ratio >= 0.5 && ratio <= 2.0) {
      score += 10;
      factors.push({ factor: 'Historical Alignment', impact: '+10', detail: `Tracking within normal range (${ratio.toFixed(1)}x avg)` });
    } else {
      score -= 5;
      factors.push({ factor: 'Historical Alignment', impact: '-5', detail: `Unusual trajectory (${ratio.toFixed(1)}x avg)` });
    }
  }

  score = Math.max(0, Math.min(100, score));
  const level = score >= 75 ? 'HIGH' : score >= 50 ? 'MEDIUM' : 'LOW';

  const weightedProj = projections.reduce((sum, p) => sum + p.projected * p.weight, 0);
  const rangeFactor = (100 - score) / 100 * 0.4;

  return {
    score,
    level,
    factors,
    projected_final: Math.round(weightedProj),
    range_low: Math.round(weightedProj * (1 - rangeFactor)),
    range_high: Math.round(weightedProj * (1 + rangeFactor))
  };
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
  const confidence = calculateConfidence(projections, balance, hoursRemaining);
  const historicalSnapshots = getHistoricalAtTime(hoursRemaining);

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
      data_points_collected: 0,
      confidence,
      historical_snapshots: historicalSnapshots
    })
  };
}
