// Historical patterns data endpoint

const HISTORICAL_PATTERNS = {
  'Umbra': { at_5_5h: 44220255, final: 155194912, pct_at_5_5h: 28.5, sale_date: '2025-10-10', order: 1 },
  'Avici': { at_5_5h: 8036796, final: 34233177, pct_at_5_5h: 23.5, sale_date: '2025-10-18', order: 2 },
  'Loyal': { at_5_5h: 16437386, final: 75898234, pct_at_5_5h: 21.7, sale_date: '2025-10-22', order: 3 },
  'zkSOL': { at_5_5h: 2427947, final: 14886360, pct_at_5_5h: 16.3, sale_date: '2025-10-24', order: 4 },
  'Paystream': { at_5_5h: 1319085, final: 6149247, pct_at_5_5h: 21.5, sale_date: '2025-10-27', order: 5 },
  'Solomon': { at_5_5h: 11779124, final: 102932688, pct_at_5_5h: 11.4, sale_date: '2025-11-18', order: 6 },
};

export async function handler(event, context) {
  return {
    statusCode: 200,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*'
    },
    body: JSON.stringify(HISTORICAL_PATTERNS)
  };
}
