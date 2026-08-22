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
const stockInput = { width: 100, padding: '4px 8px', borderRadius: 4, textAlign: 'right', fontSize: '9.5pt' };

// Opening-stock (Indigenous/Imported/Total) is the one row on this section
// editable by hand — everything else here still only ever comes from the
// Coal OMI workbook upload. Manual entry exists specifically so
// page_coal_receipts_stock.py's 4-FY opening-stock-history tables can be
// backfilled for months whose source workbook isn't available (see
// api_coal_omi_techno.py's /opening-stock endpoint).
function CoalReceiptStockSection(reportMonth) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [stockEdit, setStockEdit] = useState({ indigenous: '', imported: '', total: '' });
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);

  const load = () => {
    let cancelled = false;
    setLoading(true);
    fetch(`${API_BASE_URL}/api/techno/data?plant=SAIL&report_month=${reportMonth}&unit=Coal_Receipt_Stock`)
      .then((r) => (r.ok ? r.json() : { data: {} }))
      .then((j) => {
        if (cancelled) return;
        const m = j.data?.Coal_Receipt_Stock?.month || null;
        setData(m);
        setStockEdit({
          indigenous: m?.stock_indigenous ?? '',
          imported: m?.stock_imported ?? '',
          total: m?.stock_total ?? '',
        });
      })
      .catch(() => { if (!cancelled) setData(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  };

  useEffect(load, [reportMonth]);

  const handleSaveStock = () => {
    const body = { report_month: reportMonth };
    let any = false;
    for (const [k, apiKey] of [['indigenous', 'stock_indigenous'], ['imported', 'stock_imported'], ['total', 'stock_total']]) {
      const v = stockEdit[k];
      if (v !== '' && v !== null && !Number.isNaN(Number(v))) { body[apiKey] = Number(v); any = true; }
    }
    if (!any) { setStatus({ type: 'error', text: 'Enter at least one value.' }); return; }
    setSaving(true);
    setStatus(null);
    fetch(`${API_BASE_URL}/api/coal-omi/opening-stock`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`);
        return r.json();
      })
      .then(() => { setStatus({ type: 'success', text: 'Opening stock saved.' }); load(); })
      .catch((e) => setStatus({ type: 'error', text: `Save failed: ${e.message}` }))
      .finally(() => setSaving(false));
  };

  if (loading) return null;

  const rows = data ? [
    ['Receipt Plan (TPD)', data.receipt_plan_indigenous, data.receipt_plan_imported, data.receipt_plan_total],
    ['Receipt Actual (TPD)', data.receipt_actual_indigenous, data.receipt_actual_imported, data.receipt_actual_total],
    ["Consumption Actual ('000 T)", data.consumption_actual_indigenous, data.consumption_actual_imported, data.consumption_actual_total],
    ['Consumption Average (TPD)', data.consumption_avg_indigenous, data.consumption_avg_imported, data.consumption_avg_total],
  ] : [];

  return (
    <div style={{ marginTop: '24px' }}>
      <h2 style={{ fontSize: '13pt', fontWeight: 700, color: '#202124', marginBottom: '4px' }}>
        Receipt / Consumption / Stock (SAIL)
      </h2>
      <p style={{ fontSize: '10.5pt', color: '#5f6368', marginBottom: '10px' }}>
        {data ? `Stock as of ${data.stock_as_of_month || reportMonth}.` : `No Receipt/Consumption/Stock data (SAIL) for ${reportMonth} yet — Opening Stock can still be entered below.`} SAIL-level only — no plant breakdown in the source report.
      </p>
      {rows.length > 0 && (
        <div style={{ border: '1px solid #dadce0', borderRadius: '8px', overflowX: 'auto', marginBottom: 14 }}>
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
      )}

      <div style={{ border: '1px solid #dadce0', borderRadius: '8px', overflow: 'hidden' }}>
        <div style={{ padding: '10px 14px', backgroundColor: '#fef7e0', color: '#8a6d00', fontWeight: 700, fontSize: '10pt' }}>
          Opening Stock ('000 T) — Manual Entry for {reportMonth}
        </div>
        <div style={{ padding: '12px 14px', display: 'flex', gap: 14, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          {[['indigenous', 'Indigenous'], ['imported', 'Imported'], ['total', 'Total']].map(([k, label]) => (
            <div key={k}>
              <div style={{ fontSize: '8pt', color: '#5f6368', marginBottom: 4 }}>{label}</div>
              <input
                type="number" step="0.001" value={stockEdit[k]}
                onChange={(e) => setStockEdit((prev) => ({ ...prev, [k]: e.target.value }))}
                style={{ ...stockInput, border: '1px solid #dadce0' }}
              />
            </div>
          ))}
          <button
            onClick={handleSaveStock} disabled={saving}
            style={{ padding: '7px 16px', borderRadius: 4, border: 'none', backgroundColor: '#10b981', color: '#fff', fontWeight: 600, fontSize: '9pt', cursor: saving ? 'default' : 'pointer' }}
          >
            {saving ? 'Saving...' : 'Save Opening Stock'}
          </button>
        </div>
        {status && (
          <div style={{ margin: '0 14px 12px', padding: '8px 12px', borderRadius: 6, fontSize: '8.5pt',
                        backgroundColor: status.type === 'success' ? '#e6f4ea' : '#fce8e6',
                        color: status.type === 'success' ? '#188038' : '#d93025' }}>
            {status.text}
          </div>
        )}
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
