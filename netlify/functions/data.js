// MetaDAO Raise Tracker - Netlify Serverless Function

// Default configuration (can be overridden via query params)
const DEFAULT_WALLET = "9ApaAe39Z8GEXfqm7F7HL545N4J4tN7RhF8FhS88pRNp";
const USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v";
const DEFAULT_SALE_END_TIME = new Date("2026-01-10T16:00:00Z");
const DEFAULT_POLYMARKET_SLUG = "total-commitments-for-the-ranger-public-sale-on-metadao";

// Historical patterns with known data at 5.5h before end
const HISTORICAL_PATTERNS = {
  'Umbra': {
    final: 155194912,
    sale_date: '2025-10-10',
    order: 1,
    pct_at_5_5h: 28.5
  },
  'Avici': {
    final: 34233177,
    sale_date: '2025-10-18',
    order: 2,
    pct_at_5_5h: 23.5
  },
  'Loyal': {
    final: 75898234,
    sale_date: '2025-10-22',
    order: 3,
    pct_at_5_5h: 21.7
  },
  'zkSOL': {
    final: 14886360,
    sale_date: '2025-10-24',
    order: 4,
    pct_at_5_5h: 16.3
  },
  'Paystream': {
    final: 6149247,
    sale_date: '2025-10-27',
    order: 5,
    pct_at_5_5h: 21.5
  },
  'Solomon': {
    final: 102932688,
    sale_date: '2025-11-18',
    order: 6,
    pct_at_5_5h: 11.4
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

async function getRangerBalance(wallet) {
  wallet = wallet || DEFAULT_WALLET;
  try {
    const response = await fetch('https://api.mainnet-beta.solana.com', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jsonrpc: '2.0',
        id: 1,
        method: 'getTokenAccountsByOwner',
        params: [wallet, { mint: USDC_MINT }, { encoding: 'jsonParsed' }]
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

async function getTransactionData(wallet) {
  wallet = wallet || DEFAULT_WALLET;
  try {
    const response = await fetch('https://api.mainnet-beta.solana.com', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jsonrpc: '2.0',
        id: 1,
        method: 'getSignaturesForAddress',
        params: [wallet, { limit: 1000 }]
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

async function getPolymarketOdds(polymarketSlug) {
  polymarketSlug = polymarketSlug || DEFAULT_POLYMARKET_SLUG;
  let odds = {};

  // Skip if no slug provided
  if (!polymarketSlug) {
    return odds;
  }

  try {
    const response = await fetch(
      `https://gamma-api.polymarket.com/events?slug=${polymarketSlug}`,
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
            // outcomePrices may be a JSON string, parse if needed
            let prices = market.outcomePrices || [];
            if (typeof prices === 'string') {
              try {
                prices = JSON.parse(prices);
              } catch (e) {
                prices = [];
              }
            }
            if (prices.length > 0) {
              odds[threshold] = Math.round(parseFloat(prices[0]) * 1000) / 10;
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

function estimatePctAtTime(pctAt5_5h, hoursRemaining) {
  if (hoursRemaining >= 5.5) return pctAt5_5h;
  if (hoursRemaining <= 0) return 100;

  // Higher exp = more back-loaded surge
  const expFactor = pctAt5_5h < 15 ? 2.5 : pctAt5_5h < 25 ? 2.0 : 1.5;

  const remainingPct = 100 - pctAt5_5h;
  const timeElapsed = 5.5 - hoursRemaining;
  const timeRatio = timeElapsed / 5.5;
  const progress = Math.pow(timeRatio, expFactor);

  return pctAt5_5h + remainingPct * progress;
}

function getHistoricalAtTime(hoursRemaining) {
  const snapshots = [];
  for (const [name, data] of Object.entries(HISTORICAL_PATTERNS)) {
    const pctAt5_5h = data.pct_at_5_5h || 20;
    const estimatedPct = estimatePctAtTime(pctAt5_5h, hoursRemaining);
    const estimatedAmount = data.final * estimatedPct / 100;

    snapshots.push({
      name,
      amount: Math.round(estimatedAmount),
      final: data.final,
      pct_of_final: Math.round(estimatedPct * 10) / 10,
      sale_date: data.sale_date,
      order: data.order
    });
  }
  return snapshots.sort((a, b) => a.order - b.order);
}

function calculateProjections(balance, hoursRemaining) {
  const projections = [];
  for (const [name, data] of Object.entries(HISTORICAL_PATTERNS)) {
    const pctAt5_5h = data.pct_at_5_5h || 20;
    const estimatedPct = estimatePctAtTime(pctAt5_5h, hoursRemaining);
    const mult = estimatedPct > 0 ? 100 / estimatedPct : 1;
    const projected = balance * mult;

    projections.push({
      name,
      multiplier: Math.round(mult * 100) / 100,
      projected: Math.round(projected),
      weight: PATTERN_WEIGHTS[name] || 0,
      sale_date: data.sale_date || '',
      order: data.order || 0,
      final_raised: data.final,
      pct_at_5_5h: pctAt5_5h,
      estimated_pct_now: Math.round(estimatedPct * 10) / 10
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
  // Parse query parameters
  const params = event.queryStringParameters || {};
  const wallet = params.wallet || DEFAULT_WALLET;
  const endTimeStr = params.endTime || null;
  const polymarketSlug = params.polymarketSlug || DEFAULT_POLYMARKET_SLUG;

  // Parse end time
  let saleEndTime = DEFAULT_SALE_END_TIME;
  if (endTimeStr) {
    try {
      saleEndTime = new Date(endTimeStr);
      if (isNaN(saleEndTime.getTime())) {
        saleEndTime = DEFAULT_SALE_END_TIME;
      }
    } catch (e) {
      saleEndTime = DEFAULT_SALE_END_TIME;
    }
  }

  const now = new Date();
  const timeRemaining = saleEndTime - now;
  const hoursRemaining = Math.max(0, timeRemaining / (1000 * 3600));

  const [balance, txData, polymarketOdds] = await Promise.all([
    getRangerBalance(wallet),
    getTransactionData(wallet),
    getPolymarketOdds(polymarketSlug)
  ]);

  if (balance === null) {
    return {
      statusCode: 500,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ error: 'Could not fetch balance', wallet: wallet })
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
      historical_snapshots: historicalSnapshots,
      config: {
        wallet: wallet,
        sale_end_time: saleEndTime.toISOString(),
        polymarket_slug: polymarketSlug
      }
    })
  };
}
