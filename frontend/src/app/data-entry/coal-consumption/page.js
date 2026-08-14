'use client';

import { useState, useEffect } from 'react';
import TechnoExtractedParams from '@/components/TechnoExtractedParams';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

const PARAM_ROWS = [
  { key: 'indigenous_pcc', label: 'Indigenous PCC', unit: "'000 T" },
  { key: 'indigenous_mcc', label: 'Indigenous MCC', unit: "'000 T" },
  { key: 'imported_hard_coal', label: 'Imported Hard Coal', unit: "'000 T" },
  { key: 'imported_soft_coal', label: 'Imported Soft Coal', unit: "'000 T" },
];

// The older PDF/docx source only ever carried a monthly figure for these, no
// cumulative column, so "till month" falls back to a client-computed running
// sum of April through the selected month when the newer Coal OMI Excel
// extractor hasn't already saved a real till_month (see
// TechnoExtractedParams.js — it prefers the stored value when present).
const SUM_TILL_MONTH_KEYS = PARAM_ROWS.map((p) => p.key);

const cell = { padding: '6px 10px', fontSize: '10.5pt', borderBottom: '1px solid #e8eaed' };

function fmtNum(v) {
  if (v === null || v === undefined || v === '') return '—';
  const n = Number(v);
  return Number.isNaN(n) ? String(v) : n.toLocaleString('en-IN', { maximumFractionDigits: 3 });
}

// SAIL-level data (Receipt Plan/Actual, Consumption Actual/Average, Stock as
// of the report month's 1st) from the Coal OMI extractor's second sheet —
// no plant breakdown, so this doesn't fit TechnoExtractedParams' per-plant
// table and gets its own small section instead, sharing that component's
// month/year selection via the renderExtra slot rather than a second picker.
function CoalReceiptStockSection(reportMonth) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`${API_BASE_URL}/api/techno/data?plant=SAIL&report_month=${reportMonth}&unit=Coal_Receipt_Stock`)
      .then((r) => (r.ok ? r.json() : { data: {} }))
      .then((j) => { if (!cancelled) setData(j.data?.Coal_Receipt_Stock?.month || null); })
      .catch(() => { if (!cancelled) setData(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [reportMonth]);

  if (loading) return null;
  if (!data) {
    return (
      <div style={{ marginTop: '24px', fontSize: '11pt', color: '#5f6368' }}>
        No Receipt/Consumption/Stock data (SAIL) for {reportMonth}.
      </div>
    );
  }

  const rows = [
    ['Receipt Plan (TPD)', data.receipt_plan_indigenous, data.receipt_plan_imported, data.receipt_plan_total],
    ['Receipt Actual (TPD)', data.receipt_actual_indigenous, data.receipt_actual_imported, data.receipt_actual_total],
    ["Consumption Actual ('000 T)", data.consumption_actual_indigenous, data.consumption_actual_imported, data.consumption_actual_total],
    ['Consumption Average (TPD)', data.consumption_avg_indigenous, data.consumption_avg_imported, data.consumption_avg_total],
    ["Stock ('000 T)", data.stock_indigenous, data.stock_imported, data.stock_total],
  ];

  return (
    <div style={{ marginTop: '24px' }}>
      <h2 style={{ fontSize: '13pt', fontWeight: 700, color: '#202124', marginBottom: '4px' }}>
        Receipt / Consumption / Stock (SAIL)
      </h2>
      <p style={{ fontSize: '10.5pt', color: '#5f6368', marginBottom: '10px' }}>
        Stock as of {data.stock_as_of_month || reportMonth}. SAIL-level only — no plant breakdown in the source report.
      </p>
      <div style={{ border: '1px solid #dadce0', borderRadius: '8px', overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%' }}>
          <thead>
            <tr style={{ backgroundColor: '#e8f0fe' }}>
              <th style={{ ...cell, textAlign: 'left', fontWeight: 700, color: '#174ea6' }}>Metric</th>
              <th style={{ ...cell, textAlign: 'right', fontWeight: 700, color: '#174ea6' }}>Indigenous</th>
              <th style={{ ...cell, textAlign: 'right', fontWeight: 700, color: '#174ea6' }}>Imported</th>
              <th style={{ ...cell, textAlign: 'right', fontWeight: 700, color: '#174ea6' }}>Total</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, ind, imp, tot], i) => (
              <tr key={label} style={{ backgroundColor: i % 2 === 1 ? '#f8f9fa' : '#fff' }}>
                <td style={cell}>{label}</td>
                <td style={{ ...cell, textAlign: 'right' }}>{fmtNum(ind)}</td>
                <td style={{ ...cell, textAlign: 'right' }}>{fmtNum(imp)}</td>
                <td style={{ ...cell, textAlign: 'right', fontWeight: 700 }}>{fmtNum(tot)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function CoalConsumptionPage() {
  return (
    <TechnoExtractedParams
      title="Coal Consumption"
      description="Indigenous and imported coal consumption across all 5 plants."
      paramRows={PARAM_ROWS}
      sumTillMonthKeys={SUM_TILL_MONTH_KEYS}
      renderExtra={CoalReceiptStockSection}
    />
  );
}
