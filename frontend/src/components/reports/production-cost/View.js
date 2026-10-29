'use client';

import React, { useEffect, useState } from 'react';
import { ReportPage, FilterBar, Field, Status, Toggle, Empty, entryStyles as es, wb } from '../ReportUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// Cost of Production (backend cost_production.py): Rs/T of BF Coke, Sinter,
// Hot Metal, Crude Steel and Saleable Steel for every plant, month-wise for
// one FY or year-wise. Total = Variable + Fixed, computed by the backend.

const PRODUCTS = [
  { id: 'ALL', label: 'All' },
  { id: 'COKE', label: 'BF Coke' },
  { id: 'SINTER', label: 'Sinter' },
  { id: 'HM', label: 'Hot Metal' },
  { id: 'CS', label: 'Crude Steel' },
  { id: 'SS', label: 'Saleable Steel' },
];

const LINE = '1px solid #dadce0';
const TH = {
  padding: '6px 10px', background: '#dbeafe', borderBottom: LINE, borderRight: LINE,
  fontSize: 12.5, fontWeight: 700, textAlign: 'center', whiteSpace: 'nowrap',
};
const TD = { padding: '5px 10px', borderBottom: LINE, borderRight: LINE, fontSize: 13, textAlign: 'right', whiteSpace: 'nowrap' };
const TILL_BG = '#e2e8f0';
const SAIL_BG = '#FEF3C7';

function fmt(v) {
  return v == null ? '' : Math.round(v).toLocaleString('en-IN');
}

function query(view, fy, product) {
  const q = new URLSearchParams({ view });
  if (view === 'monthly' && fy) q.set('fy', fy);
  if (product !== 'ALL') q.set('products', product);
  return q.toString();
}

function ProductTable({ data, prod }) {
  const { periods } = data;
  return (
    <section style={{ marginBottom: 24 }}>
      <h3 style={{ fontSize: 15, fontWeight: 700, color: '#1e3a8a', margin: '0 0 6px' }}>{prod.name}</h3>
      <div style={{ overflowX: 'auto', border: LINE, borderRadius: 6 }}>
        <table style={{ borderCollapse: 'separate', borderSpacing: 0, width: '100%' }}>
          <thead>
            <tr>
              <th style={{ ...TH, textAlign: 'left', minWidth: 120 }}>Plant</th>
              {periods.map((p) => (
                <th key={p.key} style={{ ...TH, minWidth: 84, background: p.kind === 'till' ? TILL_BG : TH.background }}>{p.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {prod.blocks.map((b) => (
              <React.Fragment key={b.cost_type}>
                <tr>
                  <td colSpan={periods.length + 1} style={{ ...TD, textAlign: 'left', fontWeight: 700, color: '#1d4ed8', background: '#eef2ff' }}>{b.label}</td>
                </tr>
                {b.rows.map((r) => {
                  const sail = r.plant.startsWith('SAIL');
                  return (
                    <tr key={r.plant}>
                      <td style={{ ...TD, textAlign: 'left', fontWeight: sail ? 700 : 400, background: sail ? SAIL_BG : undefined }}>{r.plant}</td>
                      {r.values.map((v, i) => (
                        <td key={periods[i].key} style={{
                          ...TD, fontWeight: sail ? 700 : 400,
                          background: periods[i].kind === 'till' ? TILL_BG : sail ? SAIL_BG : undefined,
                        }}>{fmt(v)}</td>
                      ))}
                    </tr>
                  );
                })}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
      {prod.note && <p style={{ fontSize: 12, fontStyle: 'italic', color: '#475569', margin: '4px 0 0' }}>{prod.note}</p>}
    </section>
  );
}

export default function ProductionCostView() {
  const [view, setView] = useState('monthly');
  const [fy, setFy] = useState(null); // null: the backend's default (running FY)
  const [product, setProduct] = useState('ALL');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState(null); // null | 'xlsx' | 'pdf'

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/api/cost-production?${query(view, fy, product)}`)
      .then((r) => (r.ok ? r.json() : r.json().then((b) => { throw new Error(b.detail || r.statusText); })))
      .then((d) => { if (!cancelled) { setData(d); setError(null); } })
      .catch((e) => { if (!cancelled) { setData(null); setError(e.message); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [view, fy, product]);

  const change = (setter) => (v) => { setLoading(true); setter(v); };

  const download = async (kind) => {
    setDownloading(kind);
    try {
      const res = await fetch(`${API}/api/cost-production/${kind}?${query(view, data?.fy ?? fy, product)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Cost_of_Production_${view === 'monthly' ? (data?.fy ?? 'FY') : 'Yearly'}.${kind}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      setError(`Download failed: ${e.message}`);
    } finally {
      setDownloading(null);
    }
  };

  const hasData = data && data.periods.length > 0 && data.products.length > 0;

  return (
    <ReportPage
      maxWidth={1600}
      title={data ? data.title : 'Cost of Production'}
      description="BF Coke, Sinter, Hot Metal, Crude Steel and Saleable Steel cost of production (Rs/T), all plants. Total Cost = Variable + Fixed."
    >
      <FilterBar actions={<>
        {loading && <span className={es.ctxNote}>Loading…</span>}
        <button type="button" className={wb.btn} onClick={() => download('xlsx')} disabled={!hasData || downloading !== null}>
          {downloading === 'xlsx' ? 'Generating…' : '⬇ Excel'}
        </button>
        <button type="button" className={wb.btn} onClick={() => download('pdf')} disabled={!hasData || downloading !== null}>
          {downloading === 'pdf' ? 'Generating…' : '⬇ PDF'}
        </button>
      </>}>
        <Field label="View">
          <Toggle label="View" value={view} onChange={change(setView)}
                  options={[{ id: 'monthly', label: 'Monthly' }, { id: 'yearly', label: 'Yearly' }]} />
        </Field>
        {view === 'monthly' && (
          <Field label="Financial year" htmlFor="cop-fy">
            <select id="cop-fy" className={es.control} style={{ minWidth: 120 }}
                    value={data?.fy ?? fy ?? ''} onChange={(e) => change(setFy)(e.target.value)}>
              {(data?.fy_options ?? (fy ? [fy] : [])).map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          </Field>
        )}
        <Field label="Product" htmlFor="cop-product">
          <select id="cop-product" className={es.control} style={{ minWidth: 150 }}
                  value={product} onChange={(e) => change(setProduct)(e.target.value)}>
            {PRODUCTS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select>
        </Field>
      </FilterBar>

      <Status status={error ? { type: 'error', text: error } : null} />

      {!loading && !error && data && !hasData && (
        <Empty>No cost of production data entered for {view === 'monthly' ? `FY ${data.fy}` : 'any year'}.</Empty>
      )}
      {hasData && (
        <div style={{ marginTop: 12 }}>
          <div style={{ textAlign: 'right', fontSize: 12.5, fontWeight: 600, marginBottom: 4 }}>Unit: {data.unit}</div>
          {data.products.map((p) => <ProductTable key={p.code} data={data} prod={p} />)}
        </div>
      )}
    </ReportPage>
  );
}
