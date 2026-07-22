'use client';

import React, { useState, useEffect, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
import RequireEditor from '@/components/RequireEditor';

const months = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

const MONTH_NUM = {
  'January': '01', 'February': '02', 'March': '03', 'April': '04',
  'May': '05', 'June': '06', 'July': '07', 'August': '08',
  'September': '09', 'October': '10', 'November': '11', 'December': '12',
};

const YEAR_RANGE_START = 2000;
const _now = new Date();
// FY start year: Apr..Dec -> this calendar year; Jan..Mar -> previous calendar year
const CURRENT_FY_START_YEAR = _now.getMonth() >= 3 ? _now.getFullYear() : _now.getFullYear() - 1;
const CURRENT_FY_END_YEAR = CURRENT_FY_START_YEAR + 1;

// Calendar years: 2000 through the current FY's end year (covers Jan-Mar
// report months that fall in the current FY but the next calendar year).
const years = Array.from(
  { length: CURRENT_FY_END_YEAR - YEAR_RANGE_START + 1 },
  (_, i) => (YEAR_RANGE_START + i).toString()
);

// Financial years: 2000-01 through the current FY only.
const financialYears = Array.from(
  { length: CURRENT_FY_START_YEAR - YEAR_RANGE_START + 1 },
  (_, i) => {
    const start = YEAR_RANGE_START + i;
    const end = (start + 1) % 100;
    return `${start}-${end.toString().padStart(2, '0')}`;
  }
);

const defaultFY = () => {
  const d = new Date();
  d.setMonth(d.getMonth() - 2);
  const year = d.getFullYear();
  const monthIdx = d.getMonth();
  const startYear = (monthIdx < 3) ? year - 1 : year;
  const endYear = (startYear + 1) % 100;
  return `${startYear}-${endYear.toString().padStart(2, '0')}`;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

const getDefaultDate = () => {
  const d = new Date();
  d.setMonth(d.getMonth() - 2);
  return {
    month: months[d.getMonth()],
    year: d.getFullYear().toString()
  };
};

function PreviewTable({ title, headers, rows }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: '9pt', fontWeight: 700, color: '#a5b4fc', margin: '8px 0 6px' }}>{title}</div>
      <div style={{ overflowX: 'auto', border: '1px solid #dadce0', borderRadius: 6, maxHeight: 320, overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '8.5pt' }}>
          <thead>
            <tr style={{ backgroundColor: '#ffffff', position: 'sticky', top: 0 }}>
              {headers.map((h) => (
                <th key={h} style={{ padding: '6px 10px', textAlign: 'left', color: '#5f6368',
                                     fontWeight: 600, borderBottom: '1px solid #dadce0', whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((cells, i) => {
              const status = cells[cells.length - 1];
              const ok = status === 'ok';
              return (
                <tr key={i} style={{
                  backgroundColor: ok ? (i % 2 ? '#f8f9fa' : '#ffffff') : 'rgba(248,113,113,0.07)',
                  borderBottom: '1px solid #f8f9fa', opacity: ok ? 1 : 0.6,
                }}>
                  {cells.map((c, j) => (
                    <td key={j} style={{
                      padding: '4px 10px',
                      color: j === 0 ? '#1a73e8' : (j === cells.length - 1 ? (ok ? '#34d399' : '#f87171') : '#202124'),
                      fontWeight: j === 0 || j === cells.length - 1 ? 600 : 400,
                      whiteSpace: 'nowrap',
                      fontFamily: String(c).match(/^[A-Z]+\d+/) ? 'monospace' : 'inherit',
                    }}>{c}</td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TechnoCheckTable({ rows }) {
  const okCount      = rows.filter((r) => r.status === 'ok').length;
  const mismatchCount = rows.filter((r) => r.mapping_ok === false).length;
  const title = `Techno-Economic Parameters (${okCount} ok${mismatchCount > 0 ? `, ⚠ ${mismatchCount} mapping issues` : ''}) → techno_table`;

  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: '9pt', fontWeight: 700, color: mismatchCount > 0 ? '#fbbf24' : '#a5b4fc', margin: '8px 0 6px' }}>
        {title}
      </div>
      <div style={{ overflowX: 'auto', border: '1px solid #dadce0', borderRadius: 6, maxHeight: 320, overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '8.5pt' }}>
          <thead>
            <tr style={{ backgroundColor: '#ffffff', position: 'sticky', top: 0 }}>
              {['Parameter', 'Unit', 'Month', 'YTD', 'Cell', 'File Label', 'Status'].map((h) => (
                <th key={h} style={{ padding: '6px 10px', textAlign: 'left', color: '#5f6368',
                                     fontWeight: 600, borderBottom: '1px solid #dadce0', whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const ok     = r.status === 'ok';
              const mapOk  = r.mapping_ok !== false;
              const rowBg  = !mapOk
                ? 'rgba(251,191,36,0.10)'
                : ok ? (i % 2 ? '#f8f9fa' : '#ffffff') : 'rgba(248,113,113,0.07)';
              return (
                <tr key={i} style={{ backgroundColor: rowBg, borderBottom: '1px solid #f8f9fa' }}>
                  <td style={{ padding: '4px 10px', color: '#1a73e8', fontWeight: 600, whiteSpace: 'nowrap' }}>{r.parameter}</td>
                  <td style={{ padding: '4px 10px', color: '#202124', whiteSpace: 'nowrap' }}>{r.unit}</td>
                  <td style={{ padding: '4px 10px', color: '#202124', whiteSpace: 'nowrap' }}>{r.month_actual ?? ''}</td>
                  <td style={{ padding: '4px 10px', color: '#202124', whiteSpace: 'nowrap' }}>{r.ytd_actual ?? ''}</td>
                  <td style={{ padding: '4px 10px', color: '#5f6368', whiteSpace: 'nowrap',
                               fontFamily: 'monospace', fontSize: '8pt' }}>{r.cell}</td>
                  <td style={{ padding: '4px 10px', color: mapOk ? '#5f6368' : '#fbbf24',
                               fontWeight: mapOk ? 400 : 700, whiteSpace: 'nowrap' }}>
                    {r.row_label || '—'}{!mapOk && ' ⚠'}
                  </td>
                  <td style={{ padding: '4px 10px', color: ok ? '#34d399' : '#f87171',
                               fontWeight: 600, whiteSpace: 'nowrap' }}>{r.status}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function EditableSpecialSteelTable({ plant, rows, onToggle, onEditGrade, onEditSection }) {
  const selCount = rows.filter((r) => r.selected).length;
  const cellStyle = { padding: '4px 10px', color: '#202124', whiteSpace: 'nowrap' };
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: '9pt', fontWeight: 700, color: '#fbbf24', margin: '8px 0 6px' }}>
        Special Steel Performance ({selCount} selected) → special_steel_orders
      </div>
      <div style={{ overflowX: 'auto', border: '1px solid #dadce0', borderRadius: 6, maxHeight: 360, overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '8.5pt' }}>
          <thead>
            <tr style={{ backgroundColor: '#ffffff', position: 'sticky', top: 0, zIndex: 1 }}>
              {['Insert', 'Product', 'Quality/Grade (editable)', 'Section (editable)', 'Order Qty', 'ABP Month', 'Desp', 'Unit', 'Cell', 'Status'].map((h) => (
                <th key={h} style={{ padding: '6px 10px', textAlign: 'left', color: '#5f6368',
                                     fontWeight: 600, borderBottom: '1px solid #dadce0', whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const isTotal = r.status === 'total';
              const canInsert = !isTotal;
              return (
                <tr key={i} style={{
                  backgroundColor: isTotal
                    ? 'rgba(251,191,36,0.06)'
                    : r.selected ? (i % 2 ? '#f8f9fa' : '#ffffff') : 'rgba(248,113,113,0.07)',
                  borderBottom: '1px solid #f8f9fa',
                  opacity: isTotal ? 0.7 : r.selected ? 1 : 0.65,
                }}>
                  <td style={{ ...cellStyle, textAlign: 'center' }}>
                    <input type="checkbox" checked={!!r.selected} disabled={!canInsert}
                           title={isTotal ? 'Total rows are for cross-check only' : 'Include in insert'}
                           onChange={(e) => onToggle(i, e.target.checked)}
                           style={{ accentColor: '#10b981', cursor: canInsert ? 'pointer' : 'not-allowed' }} />
                  </td>
                  <td style={{ ...cellStyle, color: '#1a73e8', fontWeight: 600 }}>{r.product || ''}</td>
                  <td style={cellStyle}>
                    {isTotal ? (
                      <span style={{ color: '#fbbf24', fontStyle: 'italic' }}>{r.quality_grade}</span>
                    ) : (
                      <input type="text" value={r.grade_edit ?? r.quality_grade}
                             onChange={(e) => onEditGrade(i, e.target.value)}
                             style={{ width: 180, background: '#fff', color: '#202124',
                                      border: '1px solid #dadce0', borderRadius: 4,
                                      padding: '3px 6px', fontSize: '8.5pt' }} />
                    )}
                  </td>
                  <td style={cellStyle}>
                    {isTotal ? '' : (
                      <input type="text" value={r.section_edit ?? r.section ?? ''}
                             onChange={(e) => onEditSection(i, e.target.value)}
                             style={{ width: 100, background: '#fff', color: '#202124',
                                      border: '1px solid #dadce0', borderRadius: 4,
                                      padding: '3px 6px', fontSize: '8.5pt' }} />
                    )}
                  </td>
                  <td style={{ ...cellStyle, textAlign: 'right' }}>{r.order_qty ?? ''}</td>
                  <td style={{ ...cellStyle, textAlign: 'right', color: '#5f6368' }}>{r.abp_month ?? r.prodn ?? ''}</td>
                  <td style={{ ...cellStyle, textAlign: 'right' }}>{r.actual_despatch ?? ''}</td>
                  <td style={cellStyle}>{r.unit}</td>
                  <td style={{ ...cellStyle, color: '#5f6368' }}>{r.cell}</td>
                  <td style={{ ...cellStyle,
                               color: isTotal ? '#fbbf24' : '#34d399', fontWeight: 600 }}>
                    {isTotal ? 'total (skip)' : 'ok'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AllMonthsProductionTable({ rows, unit = "'000T" }) {
  if (!rows || rows.length === 0) return null;

  // Extract unique months from all rows
  const allMonths = new Set();
  rows.forEach(r => {
    if (r.months) Object.keys(r.months).forEach(m => allMonths.add(m));
  });
  const sortedMonths = Array.from(allMonths).sort();

  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: '9pt', fontWeight: 700, color: '#a5b4fc', margin: '8px 0 6px' }}>
        Production — All Months ({sortedMonths.length} months extracted) → production_table
      </div>
      <div style={{ overflowX: 'auto', border: '1px solid #dadce0', borderRadius: 6, maxHeight: 400, overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '8pt' }}>
          <thead>
            <tr style={{ backgroundColor: '#ffffff', position: 'sticky', top: 0, zIndex: 2 }}>
              <th style={{ padding: '6px 10px', textAlign: 'left', color: '#5f6368', fontWeight: 600, borderBottom: '1px solid #dadce0', whiteSpace: 'nowrap', minWidth: 150 }}>
                Item
              </th>
              {sortedMonths.map((month) => (
                <th key={month} style={{ padding: '6px 8px', textAlign: 'center', color: '#60a5fa', fontWeight: 600, borderBottom: '1px solid #dadce0', whiteSpace: 'nowrap', minWidth: 80 }}>
                  {month}
                </th>
              ))}
              <th style={{ padding: '6px 10px', textAlign: 'left', color: '#5f6368', fontWeight: 600, borderBottom: '1px solid #dadce0', whiteSpace: 'nowrap', minWidth: 60 }}>
                Status
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const ok = r.status === 'ok';
              return (
                <tr key={i} style={{
                  backgroundColor: ok ? (i % 2 ? '#f8f9fa' : '#ffffff') : 'rgba(248,113,113,0.07)',
                  borderBottom: '1px solid #f8f9fa', opacity: ok ? 1 : 0.6,
                }}>
                  <td style={{ padding: '4px 10px', color: '#1a73e8', fontWeight: 600, whiteSpace: 'nowrap' }}>
                    {r.item_name || r.pdf_label}
                  </td>
                  {sortedMonths.map((month) => (
                    <td key={month} style={{ padding: '4px 8px', textAlign: 'right', color: '#202124', fontFamily: 'monospace' }}>
                      {r.months[month] ?? '—'}
                    </td>
                  ))}
                  <td style={{ padding: '4px 10px', color: ok ? '#34d399' : '#f87171', fontWeight: 600, whiteSpace: 'nowrap' }}>
                    {ok ? 'ok' : 'unmapped'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function EditableProductionTable({ plant, rows, onToggle, onEditName }) {
  const selCount = rows.filter((r) => r.selected).length;
  const cellStyle = { padding: '4px 10px', color: '#202124', whiteSpace: 'nowrap' };
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: '9pt', fontWeight: 700, color: '#a5b4fc', margin: '8px 0 6px' }}>
        Production ({selCount} selected) → production_table
      </div>
      <div style={{ overflowX: 'auto', border: '1px solid #dadce0', borderRadius: 6, maxHeight: 360, overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '8.5pt' }}>
          <thead>
            <tr style={{ backgroundColor: '#ffffff', position: 'sticky', top: 0, zIndex: 1 }}>
              {['Insert', 'Plant', 'Item (editable)', 'In DB', 'Extracted', 'Unit', 'Cell', 'PDF Label', 'Status'].map((h) => (
                <th key={h} style={{ padding: '6px 10px', textAlign: 'left', color: '#5f6368',
                                     fontWeight: 600, borderBottom: '1px solid #dadce0', whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const wasOk = r.status === 'ok';
              const named = (r.item_edit || '').trim() !== '';
              const edited = named && wasOk && r.item_edit.trim() !== r.item_name;
              const statusText = !named ? 'unmapped'
                : edited ? 'ok (renamed)'
                : wasOk ? 'ok'
                : 'ok (mapped here)';
              const statusOk = named;
              const dbVal = r.db_value;
              const changedFromDb = dbVal != null && r.value != null && Number(dbVal) !== Number(r.value);
              return (
                <tr key={i} style={{
                  backgroundColor: r.selected ? (i % 2 ? '#f8f9fa' : '#ffffff') : 'rgba(248,113,113,0.07)',
                  borderBottom: '1px solid #f8f9fa', opacity: r.selected ? 1 : 0.65,
                }}>
                  <td style={{ ...cellStyle, textAlign: 'center' }}>
                    <input type="checkbox" checked={r.selected} disabled={!named}
                           title={named ? 'Include this row in the insert' : 'Type an item name first'}
                           onChange={(e) => onToggle(i, e.target.checked)}
                           style={{ accentColor: '#10b981', cursor: named ? 'pointer' : 'not-allowed' }} />
                  </td>
                  <td style={{ ...cellStyle, color: '#1a73e8', fontWeight: 600 }}>{plant}</td>
                  <td style={cellStyle}>
                    <input type="text" value={r.item_edit}
                           placeholder={r.pdf_label || r.item_name}
                           onChange={(e) => onEditName(i, e.target.value)}
                           style={{ width: 180, background: '#fff', color: edited || !wasOk ? '#b45309' : '#202124',
                                    border: '1px solid ' + (edited || (!wasOk && named) ? '#fbbf24' : '#dadce0'),
                                    borderRadius: 4, padding: '3px 6px', fontSize: '8.5pt' }} />
                  </td>
                  <td style={{ ...cellStyle, color: '#5f6368' }} title="Current value in production_table for this item/month">
                    {dbVal != null ? dbVal : '—'}
                  </td>
                  <td style={{ ...cellStyle, color: changedFromDb ? '#b06000' : '#202124', fontWeight: changedFromDb ? 700 : 400 }}>{r.value ?? ''}</td>
                  <td style={cellStyle}>{r.unit}</td>
                  <td style={{ ...cellStyle, color: '#5f6368' }}>{r.cell}</td>
                  <td style={{ ...cellStyle, color: '#5f6368', fontStyle: 'italic' }}>{r.pdf_label || ''}</td>
                  <td style={{ ...cellStyle, color: statusOk ? '#34d399' : '#f87171', fontWeight: 600 }}>{statusText}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div style={{ fontSize: '8pt', color: '#5f6368', marginTop: 4 }}>
        <span style={{ color: '#b06000', fontWeight: 700 }}>Amber</span> = extracted value differs from what's currently in the DB for that item/month.
      </div>
    </div>
  );
}

function RspTechnoPreviewTable({ preview }) {
  const [openUnit, setOpenUnit] = useState(null);

  if (!preview || !preview.records?.length) return null;

  const totalParams = preview.records.reduce(
    (s, r) => s + Object.keys(r.techno_json?.month || {}).length, 0
  );

  return (
    <div style={{ padding: '20px', backgroundColor: '#f8f9fa', border: '1px solid #10b981', borderRadius: '8px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 14 }}>
        <h3 style={{ fontSize: '11pt', fontWeight: 700, color: '#202124', margin: 0 }}>
          RSP Technopara Preview
          <span style={{ fontSize: '8.5pt', color: '#5f6368', fontWeight: 400, marginLeft: 10 }}>
            {preview.report_month} · {preview.source_file}
          </span>
        </h3>
        <span style={{ fontSize: '8.5pt', color: '#10b981', fontWeight: 600 }}>
          {preview.units_extracted} units · {totalParams} parameters
        </span>
      </div>

      {preview.records.map((rec) => {
        const monthData = rec.techno_json?.month || {};
        const tillData = rec.techno_json?.till_month || {};
        const params = Object.keys(monthData);
        const isOpen = openUnit === rec.unit;
        const nonNullCount = params.filter(p => monthData[p] != null && monthData[p] !== '').length;

        return (
          <div key={rec.unit} style={{ marginBottom: 6, border: '1px solid #dadce0', borderRadius: 5, overflow: 'hidden' }}>
            <button
              onClick={() => setOpenUnit(isOpen ? null : rec.unit)}
              style={{
                width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '7px 12px', background: isOpen ? '#e8f0fe' : '#ffffff',
                color: '#202124', border: 'none', cursor: 'pointer', fontSize: '9pt', fontWeight: 600,
              }}
            >
              <span>{rec.unit}</span>
              <span style={{ color: '#5f6368', fontSize: '8pt', fontWeight: 400 }}>
                {nonNullCount}/{params.length} values &nbsp;{isOpen ? '▲' : '▼'}
              </span>
            </button>

            {isOpen && (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '8.5pt' }}>
                  <thead>
                    <tr style={{ backgroundColor: '#ffffff' }}>
                      <th style={{ padding: '5px 12px', textAlign: 'left', color: '#5f6368', fontWeight: 600, borderBottom: '1px solid #dadce0', minWidth: 180 }}>Parameter</th>
                      <th style={{ padding: '5px 10px', textAlign: 'right', color: '#60a5fa', fontWeight: 600, borderBottom: '1px solid #dadce0', minWidth: 90 }}>Month</th>
                      <th style={{ padding: '5px 10px', textAlign: 'right', color: '#5f6368', fontWeight: 600, borderBottom: '1px solid #dadce0', minWidth: 90 }}>Cumulative</th>
                    </tr>
                  </thead>
                  <tbody>
                    {params.map((param, idx) => {
                      const mv = monthData[param];
                      const tv = tillData[param];
                      const fmt = v => (v != null && v !== '') ? Number(v).toLocaleString(undefined, { maximumFractionDigits: 3 }) : '—';
                      return (
                        <tr key={param} style={{ backgroundColor: idx % 2 ? '#f8f9fa' : '#ffffff', borderBottom: '1px solid #f8f9fa' }}>
                          <td style={{ padding: '4px 12px', color: '#1a73e8', fontWeight: 500 }}>{param}</td>
                          <td style={{ padding: '4px 10px', textAlign: 'right', fontFamily: 'monospace', color: mv != null ? '#dadce0' : '#dadce0' }}>{fmt(mv)}</td>
                          <td style={{ padding: '4px 10px', textAlign: 'right', fontFamily: 'monospace', color: tv != null ? '#5f6368' : '#dadce0' }}>{fmt(tv)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function UploadPageInner() {
  const defaultDate = getDefaultDate();
  const [uploadMode, setUploadMode] = useState('preview'); // 'preview' | 'plan'
  const [showDirectExtract, setShowDirectExtract] = useState(false);
  const [uploadPlantName, setUploadPlantName] = useState('RSP');
  const [uploadMonthName, setUploadMonthName] = useState(defaultDate.month);
  const [uploadYear, setUploadYear] = useState(defaultDate.year);
  const [uploadFile, setUploadFile] = useState(null);

  const [uploadPlanPlantName, setUploadPlanPlantName] = useState('RSP');
  const [uploadPlanFY, setUploadPlanFY] = useState(defaultFY());
  const [uploadPlanFile, setUploadPlanFile] = useState(null);

  const [technoPlant, setTechnoPlant] = useState('RSP');
  const [technoMonthName, setTechnoMonthName] = useState(defaultDate.month);
  const [technoYear, setTechnoYear] = useState(defaultDate.year);
  const [technoFile, setTechnoFile] = useState(null);
  const [technoPreview, setTechnoPreview] = useState(null);
  const [prodRows, setProdRows] = useState([]);   // editable copy of production_rows
  const [stockRows, setStockRows] = useState([]);
  const [planPreview, setPlanPreview] = useState(null);   // ABP Plan tab preview
  const [isPlanBusy, setIsPlanBusy] = useState(false);
  const [ssRows, setSsRows] = useState([]);       // editable copy of special_steel_rows
  const [isTechnoBusy, setIsTechnoBusy] = useState(false);
  const [isRspTechnoBusy, setIsRspTechnoBusy] = useState(false);
  const [rspTechnoPreview, setRspTechnoPreview] = useState(null);

  // ASP PDF state (single-step auto-detect: REP or FL file)
  const [aspResult, setAspResult] = useState(null);
  const [aspProdRows, setAspProdRows] = useState([]);
  const [aspBusy, setAspBusy] = useState(false);

  // DSP PDF three-step state (independent from the generic technoPreview flow)
  const [dspProdResult, setDspProdResult] = useState(null);
  const [dspProdRows, setDspProdRows] = useState([]);
  const [dspProdAllMonths, setDspProdAllMonths] = useState(null);  // Multi-month preview
  const [dspAllMonthsMode, setDspAllMonthsMode] = useState(false); // Toggle between single vs all months
  const [dspTechnoResult, setDspTechnoResult] = useState(null);
  const [dspSsResult, setDspSsResult] = useState(null);
  const [dspSsRows, setDspSsRows] = useState([]);
  const [dspStockResult, setDspStockResult] = useState(null);
  const [dspBusy, setDspBusy] = useState({ production: false, techno: false, special_steel: false, stock: false, production_all: false });

  // Item mapping suggestions
  const [dspItemSuggestions, setDspItemSuggestions] = useState(null);  // {items: [...], aliases: {...}}
  const [dspItemMappingCache, setDspItemMappingCache] = useState({});  // Cache for loaded suggestions

  // Month mismatch handling
  const [dspMonthMismatch, setDspMonthMismatch] = useState(null);  // Warning if PDF month != selected month
  const [dspUseActualMonth, setDspUseActualMonth] = useState(false);  // User confirmed to use PDF's actual month
  
  const [isUploading, setIsUploading] = useState(false);
  const [logs, setLogs] = useState([
    { type: 'info', text: 'System ready. Select a spreadsheet and click "Extract Data".' }
  ]);
  const [extractionLog, setExtractionLog] = useState([]);

  const saveDspItemAlias = async (pdfLabel, itemName, convertT = 1) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/save-item-alias`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plant: 'DSP', pdf_label: pdfLabel, item_name: itemName, convert_t: convertT }),
      });
      if (res.ok) {
        // Clear cache to reload suggestions
        setDspItemMappingCache({});
      }
    } catch (e) {
      console.error('Failed to save alias:', e);
    }
  };

  const fetchExtractionLog = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/extraction-log?limit=30`);
      if (res.ok) {
        const data = await res.json();
        setExtractionLog(data.logs || []);
      }
    } catch (_) {}
  }, []);

  useEffect(() => { fetchExtractionLog(); }, [fetchExtractionLog]);

  // Load DSP item suggestions when plant changes
  useEffect(() => {
    if (technoPlant === 'DSP' && !dspItemMappingCache['DSP']) {
      fetch(`${API_BASE_URL}/api/item-mapping-suggestions?plant=DSP`)
        .then(r => r.json())
        .then(data => {
          setDspItemSuggestions(data);
          setDspItemMappingCache(prev => ({ ...prev, 'DSP': data }));
        })
        .catch(e => console.error('Failed to load item suggestions:', e));
    } else if (technoPlant === 'DSP' && dspItemMappingCache['DSP']) {
      setDspItemSuggestions(dspItemMappingCache['DSP']);
    }
  }, [technoPlant, dspItemMappingCache]);

  const addLog = (type, text) => {
    setLogs((prev) => [...prev, { type, text, time: new Date().toLocaleTimeString() }]);
  };

  const handleExcelUpload = async (e) => {
    e.preventDefault();
    if (!uploadFile) {
      alert("Please select an Excel file to upload.");
      return;
    }

    setIsUploading(true);
    const targetPeriod = `${uploadYear}-${MONTH_NUM[uploadMonthName]}`;
    
    setLogs([]);
    addLog('info', `Starting extraction job for ${uploadPlantName} (${targetPeriod})...`);
    addLog('info', `Validating spreadsheet: ${uploadFile.name} (${(uploadFile.size / 1024).toFixed(1)} KB)`);

    const formData = new FormData();
    formData.append("file", uploadFile);
    formData.append("plant_name", uploadPlantName);
    formData.append("month", targetPeriod);

    try {
      addLog('info', 'Uploading spreadsheet file to FastAPI backend...');
      const response = await fetch(`${API_BASE_URL}/api/upload-excel`, {
        method: "POST",
        body: formData,
      });

      const result = await response.json();
      if (response.ok) {
        addLog('success', `Excel file uploaded successfully!`);
        addLog('success', `Extractor Status: ${result.message}`);
        addLog('success', `Database table production_table updated. Extraction logged.`);
        fetchExtractionLog();
        alert(result.message || "Excel sheet parsed and extracted successfully!");
      } else {
        const errMsg = result.detail || "Database write failure.";
        addLog('error', `Data Extraction Failed: ${errMsg}`);
        alert(`Extraction failed: ${errMsg}`);
      }
    } catch (err) {
      console.error(err);
      addLog('error', `Connection Error: Backend server is not running at ${API_BASE_URL}.`);
      alert("An error occurred during upload. Ensure the backend server is running.");
    } finally {
      setIsUploading(false);
      setUploadFile(null);
      const fileInput = document.getElementById("excel-file-input");
      if (fileInput) fileInput.value = "";
    }
  };

  const handleTechnoExtract = async (e) => {
    e.preventDefault();
    if (!technoFile) {
      alert('Please select the Excel file to extract.');
      return;
    }
    setIsTechnoBusy(true);
    setTechnoPreview(null);
    const targetPeriod = `${technoYear}-${MONTH_NUM[technoMonthName]}`;
    setLogs([]);
    addLog('info', `Extracting ${technoPlant} report for preview (${targetPeriod})...`);

    const formData = new FormData();
    formData.append('file', technoFile);
    formData.append('plant_name', technoPlant);
    formData.append('month', targetPeriod);

    try {
      const res = await fetch(`${API_BASE_URL}/api/extract-preview`, { method: 'POST', body: formData });
      const rawText = await res.text();
      let result;
      try {
        result = JSON.parse(rawText);
      } catch (_) {
        throw new Error(rawText.substring(0, 300));
      }
      if (!res.ok) throw new Error(result.detail || 'extraction failed');
      const prodOk = (result.production_rows || []).filter((r) => r.status === 'ok').length;
      const teOk = (result.techno_rows || []).filter((r) => r.status === 'ok').length;
      const millOk = (result.techno_param_rows || []).filter((r) => r.status === 'ok').length;
      addLog('success', `File type: ${result.source_type} (month ${result.month})`);
      if (result.month_mismatch) {
        if (result.month_mismatch.warning_only) {
          // Same-FY earlier month extracted from a later report — valid, just inform.
          addLog('warning', `⚠ ${result.month_mismatch.message}`);
        } else {
          addLog('error', `Month mismatch: ${result.month_mismatch.message || `file contains data for ${result.month} but you selected ${result.selected_month}. File month (${result.month}) will be used — please re-select the correct month if needed.`}`);
        }
      }
      addLog('info', `Workbook sheets: ${(result.workbook_sheets || []).join(' | ')}`);
      if (!result.production_rows?.length) {
        addLog('info', 'No production data: this file was not recognized as a Final Monthly Report (sheets "page-9" + "page 1-8") or Morning Report. If it should contain production, check the sheet names above.');
      }
      if (result.shops_found?.length) {
        addLog('success', `Mill techno: sheet "${result.mill_sheet}", cols ${result.month_col}/${result.cum_col}` +
          (result.columns_detected ? ' (auto-detected)' : ' (defaults)') + ` — shops: ${result.shops_found.join(', ')}`);
      }
      addLog('success', `Extracted: ${prodOk} production, ${teOk} techno, ${millOk} mill techno values. Review below, then Insert.`);

      // Compute Pellet% in Burden for BF-wise data (BSL BF PDF)
      if ((result.techno_param_rows || []).some(r => r.parameter === 'Pellet')) {
        const orig = result.techno_param_rows || [];
        // Pre-build section → param → value map for computation
        const secVals = {};
        orig.forEach(r => {
          if (!secVals[r.section]) secVals[r.section] = {};
          secVals[r.section][r.parameter] = r.actual ?? 0;
        });
        // Insert a Pellet% row immediately after each Pellet row
        const augmented = [];
        orig.forEach(r => {
          augmented.push(r);
          if (r.parameter === 'Pellet') {
            const v = secVals[r.section] || {};
            const total = (v['Iron Ore'] ?? 0) + (v['Sinter'] ?? 0) + (v['Scrap'] ?? 0) + (v['Pellet'] ?? 0);
            const pct = total > 0 ? Math.round((v['Pellet'] ?? 0) / total * 1000) / 10 : null;
            augmented.push({
              group_code: r.group_code, section: r.section,
              parameter: 'Pellet% in Burden', unit: '%',
              actual: pct, cum_actual: null,
              sort_order: (r.sort_order || 0) + 5,
              cell: 'computed: Pellet÷(IronOre+Sinter+Scrap+Pellet)×100',
              file_label: 'Pellet% in Burden',
              plant: r.plant, month: r.month,
              found_via: 'frontend computed',
              status: pct !== null ? 'ok' : 'skip',
            });
          }
        });
        result = { ...result, techno_param_rows: augmented };
      }

      setTechnoPreview(result);
      setProdRows((result.production_rows || []).map((r) => ({
        ...r,
        selected: r.status === 'ok',
        item_edit: r.status === 'ok' ? r.item_name : '',
      })));
      setSsRows((result.special_steel_rows || []).map((r) => ({
        ...r,
        selected: r.status === 'ok',
        grade_edit: r.quality_grade ?? '',
        section_edit: r.section ?? '',
      })));
      setStockRows(result.stock_rows || []);
      const stockOk = (result.stock_rows || []).filter(r => r.status === 'ok').length;
      if (stockOk > 0) {
        const sm = (result.stock_rows || []).find(r => r.stock_month)?.stock_month || '';
        addLog('success', `Opening Stock: ${stockOk} items extracted for stock_month ${sm} → stock_table`);
      }
      if (result.special_steel_note) {
        addLog('info', `Special Steel: ${result.special_steel_note}`);
      } else if ((result.special_steel_rows || []).length) {
        const ssOk = (result.special_steel_rows || []).filter((r) => r.status === 'ok').length;
        addLog('success', `Special Steel: ${ssOk} data rows + ${(result.special_steel_rows || []).length - ssOk} total rows extracted.`);
      }
    } catch (err) {
      addLog('error', `Extraction failed: ${err.message}`);
      alert(`Extraction failed: ${err.message}`);
    } finally {
      setIsTechnoBusy(false);
    }
  };

  const handleTechnoInsert = async () => {
    if (!technoPreview) return;
    // Only rows the user kept ticked (and named) are inserted. Raw-tonne values
    // of newly mapped rows are converted to '000T to match DB conventions.
    const chosen = prodRows.filter((r) => r.selected && (r.item_edit || '').trim());
    // Count-type items (e.g. "Oven Pushing(nos/d)") are plain numbers, not
    // tonnes — never ÷1000, and remembered with convert_t=0.
    const isNosItem = (r) =>
      /\(nos/i.test(r.item_edit || '') || /^nos/i.test(r.unit || '');
    const production_rows = chosen.map((r) => {
      let value = r.value;
      let unit = r.unit;
      if (isNosItem(r)) {
        unit = 'nos/day';
      } else if (r.status !== 'ok' && unit === 'T' && typeof value === 'number') {
        value = Math.round(value) / 1000;
        unit = "'000T";
      }
      return { ...r, item_name: r.item_edit.trim(), value, unit };
    });
    // Renames + newly mapped labels are remembered server-side for future extractions.
    const item_overrides = chosen
      .filter((r) => r.pdf_label && (r.status !== 'ok' || r.item_edit.trim() !== r.item_name))
      .map((r) => ({
        pdf_label: r.pdf_label,
        item_name: r.item_edit.trim(),
        convert_t: isNosItem(r) ? 0 : 1,
      }));
    // Techno rows intentionally excluded — use Techno Manual Entry page instead
    const techno_rows = [];
    const techno_param_rows = [];
    const special_steel_rows = ssRows
      .filter((r) => r.selected && r.status === 'ok')
      .map((r) => ({
        ...r,
        quality_grade: (r.grade_edit ?? r.quality_grade ?? '').trim(),
        section: (r.section_edit ?? r.section ?? '').trim(),
      }));
    const stock_rows = stockRows.filter(r => r.status === 'ok');
    if (!production_rows.length && !techno_rows.length && !techno_param_rows.length && !special_steel_rows.length && !stock_rows.length) {
      alert('No extracted values to insert.');
      return;
    }
    setIsTechnoBusy(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/confirm-extraction`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          month: technoPreview.month,
          plant: technoPreview.plant,
          source_type: technoPreview.source_type,
          sheets: technoPreview.sheets,
          file_name: technoPreview.file_name || '',
          production_rows,
          item_overrides,
          techno_rows,
          techno_param_rows,
          special_steel_rows,
          stock_rows,
        }),
      });
      const text = await res.text();
      let result;
      try { result = JSON.parse(text); } catch { throw new Error(text.slice(0, 300) || `Server error ${res.status}`); }
      if (!res.ok) throw new Error(result.detail || 'insert failed');
      addLog('success', result.message);
      alert(result.message);
      setTechnoPreview(null);
      setProdRows([]);
      setSsRows([]);
      setStockRows([]);
      setTechnoFile(null);
      const fi = document.getElementById('techno-file-input');
      if (fi) fi.value = '';
      fetchExtractionLog();
    } catch (err) {
      addLog('error', `Insert failed: ${err.message}`);
      alert(`Insert failed: ${err.message}`);
    } finally {
      setIsTechnoBusy(false);
    }
  };

  const technoOkCount = technoPreview
    ? prodRows.filter((r) => r.selected && (r.item_edit || '').trim()).length +
      (technoPreview.techno_rows || []).filter((r) => r.status === 'ok').length +
      (technoPreview.techno_param_rows || []).filter((r) => r.status === 'ok').length +
      ssRows.filter((r) => r.selected && r.status === 'ok').length +
      stockRows.filter((r) => r.status === 'ok').length
    : 0;

  const toggleProdRow = (idx, checked) =>
    setProdRows((prev) => prev.map((r, i) => (i === idx ? { ...r, selected: checked } : r)));

  const editProdRowName = (idx, name) =>
    setProdRows((prev) => prev.map((r, i) => {
      if (i !== idx) return r;
      // auto-tick a row the moment the user gives it a name; untick if cleared
      const named = name.trim() !== '';
      return { ...r, item_edit: name, selected: named ? (r.selected || r.status !== 'ok') : false };
    }));

  const toggleSsRow = (idx, checked) =>
    setSsRows((prev) => prev.map((r, i) => (i === idx ? { ...r, selected: checked } : r)));

  const editSsGrade = (idx, val) =>
    setSsRows((prev) => prev.map((r, i) => (i === idx ? { ...r, grade_edit: val } : r)));

  const editSsSection = (idx, val) =>
    setSsRows((prev) => prev.map((r, i) => (i === idx ? { ...r, section_edit: val } : r)));

  // ── ASP PDF handlers ────────────────────────────────────────────────────
  const isAspPdf = technoPlant === 'ASP';
  const isRspTechno = technoPlant === 'RSP_TECHNO';

  const handleAspExtract = async (e) => {
    e.preventDefault();
    if (!technoFile) { alert('Please select the ASP PDF file first.'); return; }
    const targetPeriod = `${technoYear}-${MONTH_NUM[technoMonthName]}`;
    setAspBusy(true);
    setAspResult(null);
    setAspProdRows([]);
    setLogs([]);
    const isRep = technoFile.name.toUpperCase().startsWith('REP');
    const isFl  = technoFile.name.toUpperCase().startsWith('FL');
    const hint  = isRep ? 'REP (crude steel)' : isFl ? 'FL (finished steel)' : 'auto-detect';
    addLog('info', `ASP: extracting ${hint} PDF for ${targetPeriod} — ${technoFile.name}...`);
    const formData = new FormData();
    formData.append('file', technoFile);
    formData.append('plant_name', 'ASP');
    formData.append('month', targetPeriod);
    try {
      const res = await fetch(`${API_BASE_URL}/api/extract-preview`, { method: 'POST', body: formData });
      const rawText = await res.text();
      let result;
      try { result = JSON.parse(rawText); } catch (_) { throw new Error(rawText.substring(0, 300)); }
      if (!res.ok) throw new Error(result.detail || 'extraction failed');
      setAspResult(result);
      setAspProdRows((result.production_rows || []).map((r) => ({
        ...r, selected: r.status === 'ok', item_edit: r.status === 'ok' ? r.item_name : '',
      })));
      const ok = (result.production_rows || []).filter((r) => r.status === 'ok').length;
      addLog('success', `ASP ${result.report_type}: ${ok} items extracted (${result.source_type}). Review below, then Insert.`);
    } catch (err) {
      addLog('error', `ASP extraction failed: ${err.message}`);
      alert(`Extraction failed: ${err.message}`);
    } finally {
      setAspBusy(false);
    }
  };

  const handleAspInsert = async () => {
    if (!aspResult) return;
    const chosen = aspProdRows.filter((r) => r.selected && (r.item_edit || '').trim());
    if (!chosen.length) { alert('No rows selected.'); return; }
    const targetPeriod = `${technoYear}-${MONTH_NUM[technoMonthName]}`;
    const production_rows = chosen.map((r) => {
      let value = r.value;
      if (r.status !== 'ok' && r.unit === 'T' && typeof value === 'number') value = Math.round(value) / 1000;
      return { ...r, item_name: r.item_edit.trim(), value };
    });
    const item_overrides = chosen
      .filter((r) => r.pdf_label && (r.status !== 'ok' || r.item_edit.trim() !== r.item_name))
      .map((r) => ({ pdf_label: r.pdf_label, item_name: r.item_edit.trim(), convert_t: 1 }));
    setAspBusy(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/confirm-extraction`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          month: aspResult.month || targetPeriod,
          plant: 'ASP',
          source_type: aspResult.source_type,
          sheets: aspResult.sheets,
          file_name: technoFile?.name || '',
          production_rows,
          item_overrides,
          techno_rows: [],
          techno_param_rows: [],
          special_steel_rows: [],
        }),
      });
      const text = await res.text();
      let result;
      try { result = JSON.parse(text); } catch { throw new Error(text.slice(0, 300) || `Server error ${res.status}`); }
      if (!res.ok) throw new Error(result.detail || 'insert failed');
      addLog('success', result.message);
      alert(result.message);
      setAspResult(null);
      setAspProdRows([]);
      const fi = document.getElementById('techno-file-input');
      if (fi) fi.value = '';
      fetchExtractionLog();
    } catch (err) {
      addLog('error', `ASP insert failed: ${err.message}`);
      alert(`Insert failed: ${err.message}`);
    } finally {
      setAspBusy(false);
    }
  };

  const toggleAspRow = (idx, checked) =>
    setAspProdRows((prev) => prev.map((r, i) => (i === idx ? { ...r, selected: checked } : r)));
  const editAspRowName = (idx, name) =>
    setAspProdRows((prev) => prev.map((r, i) => {
      if (i !== idx) return r;
      const named = name.trim() !== '';
      return { ...r, item_edit: name, selected: named ? (r.selected || r.status !== 'ok') : false };
    }));

  // ── RSP Technopara handlers ─────────────────────────────────────────────
  const handleRspTechnoExtract = async (e) => {
    e.preventDefault();
    if (!technoFile) { alert('Please select the RSP Technopara Excel file first.'); return; }
    const targetPeriod = `${technoYear}-${MONTH_NUM[technoMonthName]}`;
    setIsRspTechnoBusy(true);
    setRspTechnoPreview(null);
    setLogs([]);
    addLog('info', `RSP Technopara: extracting ${technoFile.name} for ${targetPeriod}...`);
    const formData = new FormData();
    formData.append('file', technoFile);
    formData.append('report_month', targetPeriod);
    try {
      const res = await fetch(`${API_BASE_URL}/api/rsp-techno/preview`, { method: 'POST', body: formData });
      const result = await res.json();
      if (!res.ok) throw new Error(result.detail || 'Extraction failed');
      addLog('success', `Preview ready: ${result.units_extracted} units, ${result.total_params} parameters for ${targetPeriod}. Review below, then Insert.`);
      setRspTechnoPreview(result);
    } catch (err) {
      addLog('error', `RSP Technopara extraction failed: ${err.message}`);
    } finally {
      setIsRspTechnoBusy(false);
    }
  };

  const handleRspTechnoInsert = async () => {
    if (!rspTechnoPreview) return;
    setIsRspTechnoBusy(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/rsp-techno/insert`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          report_month: rspTechnoPreview.report_month,
          source_file: rspTechnoPreview.source_file,
          records: rspTechnoPreview.records,
        }),
      });
      const result = await res.json();
      if (!res.ok) throw new Error(result.detail || 'Insert failed');
      addLog('success', result.message);
      addLog('success', 'View at: Data Entry → Techno → RSP Techno Excel Extract.');
      setRspTechnoPreview(null);
      setTechnoFile(null);
      const fi = document.getElementById('techno-file-input');
      if (fi) fi.value = '';
      fetchExtractionLog();
    } catch (err) {
      addLog('error', `RSP Technopara insert failed: ${err.message}`);
    } finally {
      setIsRspTechnoBusy(false);
    }
  };

  // ── DSP PDF three-step helpers ──────────────────────────────────────────
  const isDspPdf = technoPlant === 'DSP' && technoFile?.name?.toLowerCase().endsWith('.pdf');

  const handleDspExtractAllMonths = async () => {
    // Delegate to handleDspExtract with allMonths=true
    await handleDspExtract('production', true);
  };

  const handleDspExtract = async (block, allMonths = false) => {
    if (!technoFile) { alert('Please select the DSP PDF file first.'); return; }
    const targetPeriod = `${technoYear}-${MONTH_NUM[technoMonthName]}`;
    const busyKey = allMonths ? 'production_all' : block;
    setDspBusy((b) => ({ ...b, [busyKey]: true }));
    setLogs([]);
    addLog('info', `DSP: extracting ${block} (${targetPeriod}) from ${technoFile.name}${allMonths ? ' (ALL MONTHS)' : ''}...`);
    const formData = new FormData();
    formData.append('file', technoFile);
    formData.append('plant_name', 'DSP');
    formData.append('month', targetPeriod);
    formData.append('extract_block', block);
    if (allMonths) {
      formData.append('all_months', 'true');
    }
    try {
      const res = await fetch(`${API_BASE_URL}/api/extract-preview`, { method: 'POST', body: formData });
      const rawText = await res.text();
      let result;
      try { result = JSON.parse(rawText); } catch (_) { throw new Error(rawText.substring(0, 300)); }
      if (!res.ok) throw new Error(result.detail || 'extraction failed');
      if (block === 'production') {
        // Check for month mismatch
        if (result.month_mismatch) {
          setDspMonthMismatch(result.month_mismatch);
          addLog('warning', `⚠ Month mismatch: ${result.month_mismatch.message}`);
          setDspUseActualMonth(false);
          // Don't proceed yet - wait for user confirmation
          setDspBusy((b) => ({ ...b, [busyKey]: false }));
          return;
        }

        if (allMonths) {
          // All-months mode: group rows by item
          const allMonthsMap = {};
          (result.production_rows || []).forEach((r) => {
            const key = r.item_name || r.pdf_label;
            if (!allMonthsMap[key]) {
              allMonthsMap[key] = { item_name: r.item_name, pdf_label: r.pdf_label, status: r.status, unit: r.unit, months: {} };
            }
            allMonthsMap[key].months[r.report_month] = r.value;
          });

          setDspProdAllMonths({ ...result, grouped_rows: Object.values(allMonthsMap), single_rows: result.production_rows });
          setDspAllMonthsMode(true);
          const totalRows = (result.production_rows || []).length;
          const ok = result.production_rows.filter((r) => r.status === 'ok').length;
          addLog('success', `✓ ALL months extracted: ${ok}/${totalRows} items mapped across all FY months`);
        } else {
          // Single-month mode: show traditional table
          setDspProdResult(result);
          setDspProdRows((result.production_rows || []).map((r) => ({
            ...r, selected: r.status === 'ok', item_edit: r.status === 'ok' ? r.item_name : '',
          })));
          setDspAllMonthsMode(false);
          const ok = (result.production_rows || []).filter((r) => r.status === 'ok').length;
          addLog('success', `Production: ${ok} items extracted. Review below, then Insert Production.`);
        }
      } else if (block === 'techno') {
        setDspTechnoResult(result);
        const ok = (result.techno_param_rows || []).filter((r) => r.status === 'ok').length;
        addLog('success', `Techno: ${ok} parameters extracted. Review below, then Insert Techno.`);
      } else if (block === 'special_steel') {
        setDspSsResult(result);
        setDspSsRows((result.special_steel_rows || []).map((r) => ({
          ...r, selected: r.status === 'ok', grade_edit: r.quality_grade ?? '', section_edit: r.section ?? '',
        })));
        const ok = (result.special_steel_rows || []).filter((r) => r.status === 'ok').length;
        const note = result.special_steel_note;
        if (note) addLog('info', `Special Steel: ${note}`);
        else addLog('success', `Special Steel: ${ok} rows extracted. Review below, then Insert Special Steel.`);
      } else if (block === 'stock') {
        setDspStockResult(result);
        const ok = (result.stock_rows || []).filter((r) => r.status === 'ok').length;
        if (result.month_mismatch)
          addLog('error', `Flash stock: detected date ${result.detected_date} (month ${result.detected_month}) ≠ selected month ${result.selected_month} — verify before inserting.`);
        addLog('success', `Flash stock: ${ok}/4 rows extracted. Review below, then Insert Stock.`);
      }
    } catch (err) {
      addLog('error', `DSP ${block} extraction failed: ${err.message}`);
      alert(`Extraction failed: ${err.message}`);
    } finally {
      setDspBusy((b) => ({ ...b, [block]: false }));
    }
  };

  const handleDspInsert = async (block) => {
    const targetPeriod = `${technoYear}-${MONTH_NUM[technoMonthName]}`;
    const baseResult = dspProdResult || dspTechnoResult || dspSsResult || dspStockResult;
    const month = baseResult?.month || targetPeriod;

    // ── Stock (Flash.pdf) insert ──────────────────────────────────────────
    if (block === 'stock' && dspStockResult) {
      const okRows = (dspStockResult.stock_rows || []).filter((r) => r.status === 'ok' && r.value != null);
      if (!okRows.length) { alert('No stock rows to insert.'); return; }
      const payload = {
        month, plant: 'DSP', source_type: 'DSP Flash Report (Closing Stock)',
        sheets: 'Flash.pdf page 1', file_name: technoFile?.name || '',
        production_rows: [], item_overrides: [], techno_rows: [],
        techno_param_rows: [], special_steel_rows: [],
        stock_rows: okRows,
      };
      setDspBusy((b) => ({ ...b, stock: true }));
      try {
        const res = await fetch(`${API_BASE_URL}/api/confirm-extraction`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
        });
        const text = await res.text();
        let result;
        try { result = JSON.parse(text); } catch { throw new Error(text.slice(0, 300) || `Server error ${res.status}`); }
        if (!res.ok) throw new Error(result.detail || 'insert failed');
        addLog('success', result.message);
        alert(result.message);
        setDspStockResult(null);
        fetchExtractionLog();
      } catch (err) {
        addLog('error', `DSP stock insert failed: ${err.message}`);
        alert(`Insert failed: ${err.message}`);
      } finally {
        setDspBusy((b) => ({ ...b, stock: false }));
      }
      return;
    }

    let payload = {
      month, plant: 'DSP', source_type: 'DSP OMI PDF Report',
      sheets: '', file_name: technoFile?.name || '',
      production_rows: [], item_overrides: [], techno_rows: [],
      techno_param_rows: [], special_steel_rows: [],
    };
    if (block === 'production' && (dspProdResult || dspProdAllMonths)) {
      if (dspAllMonthsMode && dspProdAllMonths) {
        // Insert all-months data: use the single_rows with each month's report_month
        const allMonthsRows = (dspProdAllMonths.single_rows || [])
          .filter((r) => r.status === 'ok')
          .map((r) => {
            let value = r.value;
            if (r.unit === 'T' && typeof value === 'number') value = Math.round(value) / 1000;

            // Save this mapping for future use
            if (r.pdf_label && r.item_name !== r.pdf_label) {
              saveDspItemAlias(r.pdf_label, r.item_name, r.unit === 'nos/d' ? 0 : 1);
            }

            return { ...r, item_name: r.item_name, value, report_month: r.report_month };
          });
        if (!allMonthsRows.length) { alert('No production rows to insert.'); return; }
        payload.production_rows = allMonthsRows;
        payload.sheets = dspProdAllMonths.sheets || '';
        // For all-months mode, month is already set from baseResult.month (report month)
      } else {
        // Insert single-month data (traditional mode)
        const chosen = dspProdRows.filter((r) => r.selected && (r.item_edit || '').trim());
        if (!chosen.length) { alert('No production rows selected.'); return; }
        payload.production_rows = chosen.map((r) => {
          let value = r.value;
          if (r.status !== 'ok' && r.unit === 'T' && typeof value === 'number') value = Math.round(value) / 1000;

          // Save this mapping for future use
          if (r.pdf_label && r.item_edit.trim() !== r.pdf_label) {
            saveDspItemAlias(r.pdf_label, r.item_edit.trim(), r.unit === 'nos/d' ? 0 : 1);
          }

          return { ...r, item_name: r.item_edit.trim(), value };
        });
        payload.item_overrides = chosen
          .filter((r) => r.pdf_label && (r.status !== 'ok' || r.item_edit.trim() !== r.item_name))
          .map((r) => ({ pdf_label: r.pdf_label, item_name: r.item_edit.trim(), convert_t: r.unit === 'nos/d' ? 0 : 1 }));
        payload.sheets = dspProdResult.sheets || '';
      }
    } else if (block === 'techno' && dspTechnoResult) {
      payload.techno_param_rows = (dspTechnoResult.techno_param_rows || []).filter((r) => r.status === 'ok');
      if (!payload.techno_param_rows.length) { alert('No techno rows to insert.'); return; }
      payload.sheets = dspTechnoResult.sheets || '';
    } else if (block === 'special_steel' && dspSsResult) {
      payload.special_steel_rows = dspSsRows
        .filter((r) => r.selected && r.status === 'ok')
        .map((r) => ({ ...r, quality_grade: (r.grade_edit ?? r.quality_grade ?? '').trim(), section: (r.section_edit ?? r.section ?? '').trim() }));
      if (!payload.special_steel_rows.length) { alert('No special steel rows selected.'); return; }
      payload.sheets = dspSsResult.sheets || '';
    } else { return; }

    setDspBusy((b) => ({ ...b, [block]: true }));
    try {
      const res = await fetch(`${API_BASE_URL}/api/confirm-extraction`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      });
      const text = await res.text();
      let result;
      try { result = JSON.parse(text); } catch { throw new Error(text.slice(0, 300) || `Server error ${res.status}`); }
      if (!res.ok) throw new Error(result.detail || 'insert failed');
      addLog('success', result.message);
      alert(result.message);
      if (block === 'production') {
        setDspProdResult(null);
        setDspProdRows([]);
        setDspProdAllMonths(null);
        setDspAllMonthsMode(false);
      }
      else if (block === 'techno') { setDspTechnoResult(null); }
      else { setDspSsResult(null); setDspSsRows([]); }
      fetchExtractionLog();
    } catch (err) {
      addLog('error', `DSP ${block} insert failed: ${err.message}`);
      alert(`Insert failed: ${err.message}`);
    } finally {
      setDspBusy((b) => ({ ...b, [block]: false, production_all: false }));
    }
  };

  const toggleDspProdRow = (idx, checked) =>
    setDspProdRows((prev) => prev.map((r, i) => (i === idx ? { ...r, selected: checked } : r)));
  const editDspProdName = (idx, name) =>
    setDspProdRows((prev) => prev.map((r, i) => {
      if (i !== idx) return r;
      const named = name.trim() !== '';
      return { ...r, item_edit: name, selected: named ? (r.selected || r.status !== 'ok') : false };
    }));
  const toggleDspSsRow = (idx, checked) =>
    setDspSsRows((prev) => prev.map((r, i) => (i === idx ? { ...r, selected: checked } : r)));
  const editDspSsGrade = (idx, val) =>
    setDspSsRows((prev) => prev.map((r, i) => (i === idx ? { ...r, grade_edit: val } : r)));
  const editDspSsSection = (idx, val) =>
    setDspSsRows((prev) => prev.map((r, i) => (i === idx ? { ...r, section_edit: val } : r)));

  const handlePlanExtract = async (e) => {
    e.preventDefault();
    if (!uploadPlanFile) {
      alert('Please select a Plan file to upload.');
      return;
    }
    setIsPlanBusy(true);
    addLog('info', `Extracting ABP Plan for ${uploadPlanPlantName} (${uploadPlanFY})…`);
    const fd = new FormData();
    fd.append('file', uploadPlanFile);
    fd.append('plant_name', uploadPlanPlantName);
    fd.append('financial_year', uploadPlanFY);
    try {
      const res = await fetch(`${API_BASE_URL}/api/preview-plan`, { method: 'POST', body: fd });
      const text = await res.text();
      let result;
      try { result = JSON.parse(text); } catch { throw new Error(text.slice(0, 300) || `Server error ${res.status}`); }
      if (!res.ok) throw new Error(result.detail || 'extraction failed');
      const okCount = (result.plan_rows || []).filter(r => r.status === 'ok').length;
      addLog('success', `Preview ready: ${okCount} plan rows for ${uploadPlanPlantName} FY ${uploadPlanFY}. Review then insert.`);
      setPlanPreview(result);
    } catch (err) {
      addLog('error', `Plan extraction failed: ${err.message}`);
      alert(`Extraction failed: ${err.message}`);
    } finally {
      setIsPlanBusy(false);
    }
  };

  const handlePlanInsert = async () => {
    if (!planPreview) return;
    const plan_rows = (planPreview.plan_rows || []).filter(r => r.status === 'ok');
    if (!plan_rows.length) { alert('No rows to insert.'); return; }
    setIsPlanBusy(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/confirm-plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan_rows, plant: planPreview.plant, financial_year: planPreview.financial_year }),
      });
      const text = await res.text();
      let result;
      try { result = JSON.parse(text); } catch { throw new Error(text.slice(0, 300)); }
      if (!res.ok) throw new Error(result.detail || 'insert failed');
      addLog('success', result.message);
      alert(result.message);
      setPlanPreview(null);
      setUploadPlanFile(null);
      const fi = document.getElementById('plan-file-input');
      if (fi) fi.value = '';
      fetchExtractionLog();
    } catch (err) {
      addLog('error', `Plan insert failed: ${err.message}`);
      alert(`Insert failed: ${err.message}`);
    } finally {
      setIsPlanBusy(false);
    }
  };

  return (
    <>
      {/* Global Navbar */}
      <GlobalNavbar />

      <main className="app-container">
      {/* Sidebar Control Panel */}
      <div className="sidebar no-print">
        <div className="sidebar-header">
          <h1>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--primary)' }}>
              <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            Excel Ingestion
          </h1>
          <p>Data Upload Engine</p>
        </div>

        {/* Unified Data Upload — single section with mode toggle */}
        <div className="control-section">
          <h2>Data Upload</h2>

          {/* Mode selector — 2 tabs */}
          <div style={{ display: 'flex', gap: 4, marginBottom: 14, paddingBottom: 10, borderBottom: '1px solid #dadce0' }}>
            {[['preview', 'Preview & Insert'], ['plan', 'ABP Plan']].map(([mode, label]) => (
              <button key={mode} type="button" onClick={() => setUploadMode(mode)}
                style={{ flex: 1, padding: '5px 2px', fontSize: '7.5pt', fontWeight: uploadMode === mode ? 700 : 500,
                         border: `1px solid ${uploadMode === mode ? '#1a73e8' : '#dadce0'}`,
                         borderRadius: 4, cursor: 'pointer', whiteSpace: 'nowrap',
                         backgroundColor: uploadMode === mode ? 'rgba(56,189,248,0.12)' : 'transparent',
                         color: uploadMode === mode ? '#1a73e8' : '#5f6368' }}>
                {label}
              </button>
            ))}
          </div>

          {/* ── PREVIEW & INSERT MODE (includes direct extract) ───── */}
          {uploadMode === 'preview' && (
            <>
            <form onSubmit={handleTechnoExtract}>
              <div className="form-group" style={{ marginBottom: '12px' }}>
                <label>Plant Source</label>
                <select className="form-control" value={technoPlant}
                        onChange={(e) => setTechnoPlant(e.target.value)}>
                  <option value="RSP">RSP (Excel — production / general)</option>
                  <option value="DSP">DSP (OMI PDF or MCR-I Excel)</option>
                  <option value="ISP">ISP (Morning/Final Excel, or Special Steel PNG)</option>
                  <option value="BSP">BSP (Flash PDF / PPC MIS Month-End .xls / Special Steel .xlsx)</option>
                  <option value="BSL">BSL (DPR .xlsx / Corporate SS .xlsx)</option>
                  <option value="ASP">ASP (xlsx or PDF — REP / FL actuals)</option>
                  <option value="SSP">SSP (PDF — Monthly DPR)</option>
                  <option value="VISL">VISL (PDF — Monthly Report)</option>
                </select>
              </div>
              <div className="form-group" style={{ marginBottom: '12px' }}>
                <label>Report Month</label>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <select className="form-control" style={{ flex: 2 }} value={technoMonthName}
                          onChange={(e) => setTechnoMonthName(e.target.value)}>
                    {months.map((m) => <option key={m} value={m}>{m}</option>)}
                  </select>
                  <select className="form-control" style={{ flex: 1 }} value={technoYear}
                          onChange={(e) => setTechnoYear(e.target.value)}>
                    {years.map((y) => <option key={y} value={y}>{y}</option>)}
                  </select>
                </div>
              </div>
              <div className="form-group" style={{ marginBottom: '15px' }}>
                <label>
                  {technoPlant === 'RSP_TECHNO' ? 'RSP Technopara Excel (.xlsx — sheet: page1-8)'
                    : technoPlant === 'DSP' ? 'DSP Report (.pdf or MCR-I .xls)'
                    : technoPlant === 'ISP' ? 'ISP File (.xlsx production/techno, or .png Special Steel screenshot)'
                    : technoPlant === 'BSP' ? 'BSP File (flash-*.pdf Monthly / .xls Month-End PPC MIS / .xlsx Techno/OISCO/SS)'
                    : technoPlant === 'BSL' ? 'BSL — DPR Mail (.xlsx) or Techno (.xls) or Corporate SS (.xlsx) or BF Performance / Main Products PDF (.pdf)'
                    : technoPlant === 'ASP' ? 'ASP file — asp.xlsx  or  REP*.pdf / FL*.pdf'
                    : technoPlant === 'SSP' ? 'SSP DPR PDF (e.g. SSP-DPR-DD.MM.YY.pdf)'
                    : technoPlant === 'VISL' ? 'VISL Monthly Report PDF (e.g. VISLreportsMONYY.pdf)'
                    : 'RSP Excel File (.xlsx)'}
                </label>
                <input id="techno-file-input" type="file" className="form-control"
                       accept={technoPlant === 'DSP' ? '.pdf,.xls' : technoPlant === 'BSP' ? '.xls,.xlsx,.pdf' : technoPlant === 'BSL' ? '.xls,.xlsx,.pdf' : technoPlant === 'ASP' ? '.xlsx,.pdf' : (technoPlant === 'SSP' || technoPlant === 'VISL') ? '.pdf' : technoPlant === 'ISP' ? '.xlsx,.png,.jpg,.jpeg' : '.xlsx'}
                       style={{ padding: '4px', fontSize: '0.8rem' }}
                       suppressHydrationWarning
                       onChange={(e) => setTechnoFile(e.target.files[0])} />
                <div style={{ fontSize: '7.5pt', color: '#fbbf24', marginTop: '4px' }}>
                  {technoPlant === 'RSP_TECHNO'
                    ? 'RSP Technopara monthly Excel (e.g. technoparaMay2026.xlsx). Sheet must be named page1-8. Extracts BF, SMS, Sinter, Coke oven & General params unit-wise into techno_data table. Select the report month above first.'
                    : technoPlant === 'DSP'
                    ? 'OMI PDF: production + special steel + techno. MCR-I .xls: 21 production items. Month auto-detected.'
                    : technoPlant === 'ISP'
                    ? 'Morning Report (DAILYREPORT1): ~19 items, month from K5. Final Monthly: ~17 items, set month above. Summarized Monthly (B-FCE): ~37 techno params. Special Steel screenshot (.png/.jpg of the PPC ISP "Order vs Despatch" email): OCR-read PRODUCTS/ORDER/DESPATCH table (WR COIL, TMT COIL, TMT BAR, STRUCTURALS, 150 BLT, 200 BLM), month auto-detected from the title — always review before inserting.'
                    : technoPlant === 'BSP'
                    ? "File type auto-detected from content: flash-<mon>YY.pdf → BSP Flash Monthly PDF — full production (incl. furnace-wise BF#1/4/5/6/7), ~80 techno params (coke yield, sinter, BF, SMS-2/3, all mills, energy) + closing stock, month auto-detected from cover. BSPMIS*.xls → PPC MIS Month-End (sheet S1) — production + opening stock (closing stock saved as next month). BSP MIS 2_coff_print*.xls/.xlsx → furnace-wise Hot Metal production (tentative; BF-1/4/5/6/7/8, column D CUM, month from row 2). BSP_Spstl-*.xlsx → Special Steel (sheet CORP). BSP-3-page-Tech.xlsx → techno params (Sheet1, month from A3). OISCO_<Mon>'YY.xlsx → OISCO techno params (month from C3)."
                    : technoPlant === 'BSL'
                    ? 'DPR XLSX: BSL_DPR_DDMMYYYY.xlsx (sheet DPR) — 19 production items, month auto-detected from O1. | Techno XLS: TECHNO <MON><YYYY>.XLS — 14+ techno params, set month above. | Corp SS XLSX: grade-wise Order Qty & Despatch, month auto-detected. | BF PDF: BSL_BlastFurnace_DDMMYYYY.pdf — furnace-wise HM production (BF-1/2/4/5) into production_table; the other 13 techno params for this PDF are entered via /data-entry/techno. | Main Products PDF: the plant\'s month-end PDF bundle (e.g. "Rev <Mon><YY> (n).pdf") — auto-detected from its "PRODUCTION OF MAIN PRODUCTS" page. Extracts the same 19 production items as the DPR path (Sinter, Hot Metal, Pig Iron, SMS-1/2, Crude Steel, HR Coil/Plate/Sheet, CR Coil/Sheet, GP/GC, Saleable Steel, Finished Steel, Saleable Semis) straight from the finalised report; month auto-detected from the page header.'
                    : technoPlant === 'ASP'
                    ? "asp.xlsx → reads cells F10/F11/F13/F21/L26 (Crude Steel, Concast, Ingot, Saleable, Stock). Month auto-detected from E3. REP*.pdf → same items via keyword search. FL*.pdf → BARS+FS PRD+PL MILL → Finished Steel (col3=Actual)."
                    : technoPlant === 'SSP'
                    ? "SSP DPR PDF → SMS(SLAB) row: 1st number = Crude Steel (Cum Actual). Saleable Production TOTAL row: 2nd number = Finished & Saleable Steel (Cum Actual). Values in Tonnes → stored as '000T."
                    : technoPlant === 'VISL'
                    ? "VISL Monthly PDF → 'Total Saleable Steel' row: 2nd number (To Date) = Finished Steel & Saleable Steel. 'Sales (AS+MS)' row: 2nd number (To Date) = Saleable Steel Despatch. Values in Tonnes → stored as '000T."
                    : 'Final Monthly, Morning Report or Techno file — auto-detected. Production + techno both extracted.'}
                  {' '}Shown for review before insertion.
                </div>
              </div>
              {isDspPdf ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <div style={{ fontSize: '8pt', color: '#5f6368', marginBottom: 2 }}>
                    DSP PDF — extract each block separately, then insert:
                  </div>
                  {[
                    ['production', '1. Extract Production', '#10b981'],
                    ['special_steel', '2. Extract Special Steel', '#f59e0b'],
                    ['stock', '3. Extract Stock (Flash.pdf)', '#ef4444'],
                  ].map(([block, label, color]) => (
                    <button key={block} type="button" onClick={() => handleDspExtract(block)}
                            disabled={dspBusy[block]}
                            style={{ width: '100%', padding: '8px', borderRadius: 6, fontWeight: 700,
                                     backgroundColor: color, border: `1px solid ${color}`, color: '#fff',
                                     cursor: dspBusy[block] ? 'not-allowed' : 'pointer', fontSize: '9pt' }}>
                      {dspBusy[block] ? 'Extracting...' : label}
                    </button>
                  ))}
                  <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid #dadce0', fontSize: '8pt', color: '#5f6368' }}>
                    Production — extract all FY months at once:
                  </div>
                  <button type="button" onClick={handleDspExtractAllMonths}
                          disabled={dspBusy.production_all}
                          style={{ width: '100%', padding: '8px', borderRadius: 6, fontWeight: 700,
                                   backgroundColor: '#06b6d4', border: '1px solid #06b6d4', color: '#fff',
                                   cursor: dspBusy.production_all ? 'not-allowed' : 'pointer', fontSize: '9pt' }}>
                    {dspBusy.production_all ? 'Extracting All Months...' : '🔄 Extract All Previous Months'}
                  </button>
                </div>
              ) : isAspPdf ? (
                <button type="button" onClick={handleAspExtract} disabled={aspBusy}
                        style={{ width: '100%', padding: '8px', borderRadius: 6, fontWeight: 700,
                                 backgroundColor: '#0ea5e9', border: '1px solid #0ea5e9', color: '#fff',
                                 cursor: aspBusy ? 'not-allowed' : 'pointer', fontSize: '9pt' }}>
                  {aspBusy ? 'Extracting ASP PDF...' : 'Extract ASP PDF (REP / FL)'}
                </button>
              ) : isRspTechno ? (
                <button type="button" onClick={handleRspTechnoExtract} disabled={isRspTechnoBusy}
                        style={{ width: '100%', padding: '8px', borderRadius: 6, fontWeight: 700,
                                 backgroundColor: '#10b981', border: '1px solid #10b981', color: '#fff',
                                 cursor: isRspTechnoBusy ? 'not-allowed' : 'pointer', fontSize: '9pt' }}>
                  {isRspTechnoBusy ? 'Extracting...' : 'Extract & Save RSP Technopara'}
                </button>
              ) : (
                <button type="submit" className="btn btn-primary" disabled={isTechnoBusy}
                        style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                                 backgroundColor: '#8b5cf6', borderColor: '#8b5cf6' }}>
                  {isTechnoBusy ? 'Working...' : 'Extract & Preview'}
                </button>
              )}
            </form>

            {/* ── Month Mismatch Warning Dialog ────────────────────── */}
            {dspMonthMismatch && (
              <div style={{ marginTop: 16, padding: 16, backgroundColor: '#fbbf24', borderRadius: 8, border: '1px solid #f59e0b' }}>
                <div style={{ fontSize: '9pt', fontWeight: 700, color: '#78350f', marginBottom: 12 }}>
                  ⚠️ Month Mismatch Warning
                </div>
                <div style={{ fontSize: '8.5pt', color: '#78350f', marginBottom: 12, lineHeight: 1.5 }}>
                  {dspMonthMismatch.message}
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={() => {
                    setDspUseActualMonth(true);
                    // Re-extract with actual month
                    setDspMonthMismatch(null);
                    // Set the month to the actual PDF month
                    const [pdfYear, pdfMonth] = dspMonthMismatch.actual_month.split('-').map(Number);
                    setTechnoMonth(months[pdfMonth - 1]);
                    setTechnoYear(pdfYear.toString());
                    addLog('info', `Using PDF's actual month: ${dspMonthMismatch.actual_month}`);
                  }}
                  style={{ padding: '6px 12px', backgroundColor: '#f59e0b', border: 'none', color: '#fff', borderRadius: 4, fontSize: '8.5pt', fontWeight: 600, cursor: 'pointer' }}>
                    ✓ Use PDF's Actual Month ({dspMonthMismatch.actual_month})
                  </button>
                  <button onClick={() => setDspMonthMismatch(null)}
                  style={{ padding: '6px 12px', backgroundColor: '#78350f', border: 'none', color: '#fef3c7', borderRadius: 4, fontSize: '8.5pt', fontWeight: 600, cursor: 'pointer' }}>
                    ✗ Cancel
                  </button>
                </div>
              </div>
            )}

            {/* ── Direct Data Extraction (no preview) ─────────────── */}
            <div style={{ marginTop: 16, borderTop: '1px solid #dadce0', paddingTop: 12 }}>
              <button type="button" onClick={() => setShowDirectExtract((v) => !v)}
                style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                         background: 'none', border: 'none', cursor: 'pointer', padding: 0, marginBottom: showDirectExtract ? 10 : 0 }}>
                <span style={{ fontSize: '8pt', fontWeight: 600, color: '#5f6368' }}>Direct Data Extraction (no preview)</span>
                <span style={{ fontSize: '9pt', color: '#5f6368' }}>{showDirectExtract ? '▲' : '▼'}</span>
              </button>
              {showDirectExtract && (
                <form onSubmit={handleExcelUpload}>
                  <div className="form-group" style={{ marginBottom: '10px' }}>
                    <label>Plant Source</label>
                    <select className="form-control" value={uploadPlantName}
                            onChange={(e) => setUploadPlantName(e.target.value)}>
                      <option value="RSP">RSP</option>
                      <option value="BSP">BSP</option>
                      <option value="ISP">ISP</option>
                      <option value="BSL">BSL</option>
                      <option value="DSP">DSP</option>
                      <option value="ASP">ASP (not yet supported)</option>
                      <option value="SSP">SSP (not yet supported)</option>
                      <option value="VISL">VISL (not yet supported)</option>
                    </select>
                  </div>
                  <div className="form-group" style={{ marginBottom: '10px' }}>
                    <label>Target Period</label>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <select className="form-control" style={{ flex: 2 }} value={uploadMonthName}
                              onChange={(e) => setUploadMonthName(e.target.value)}>
                        {months.map((m) => <option key={m} value={m}>{m}</option>)}
                      </select>
                      <select className="form-control" style={{ flex: 1 }} value={uploadYear}
                              onChange={(e) => setUploadYear(e.target.value)}>
                        {years.map((y) => <option key={y} value={y}>{y}</option>)}
                      </select>
                    </div>
                  </div>
                  <div className="form-group" style={{ marginBottom: '12px' }}>
                    <label>Excel File {(uploadPlantName === 'BSP' || uploadPlantName === 'DSP') ? '(.xls)' : '(.xlsx)'}</label>
                    <input id="excel-file-input" type="file" className="form-control"
                           accept={(uploadPlantName === 'BSP' || uploadPlantName === 'DSP') ? '.xls' : '.xlsx'}
                           style={{ padding: '4px', fontSize: '0.8rem' }}
                           onChange={(e) => setUploadFile(e.target.files[0])} />
                    {(uploadPlantName === 'BSP' || uploadPlantName === 'BSL' || uploadPlantName === 'DSP' || uploadPlantName === 'ISP') && (
                      <div style={{ fontSize: '7.5pt', color: '#fbbf24', marginTop: '4px' }}>
                        {uploadPlantName === 'BSP' ? 'Month auto-detected from N1 (sheet S1).'
                          : uploadPlantName === 'BSL' ? 'Month auto-detected from O1 (sheet DPR).'
                          : uploadPlantName === 'DSP' ? 'Month auto-detected from MCR-I header.'
                          : 'Morning Report: month from K5. Final Monthly: set month above.'}
                      </div>
                    )}
                  </div>
                  <button type="submit" className="btn btn-primary" disabled={isUploading}
                          style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                                   backgroundColor: '#10b981', borderColor: '#10b981' }}>
                    {isUploading ? 'Extracting...' : (
                      <><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '8px' }}>
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
                      </svg>Extract Data</>
                    )}
                  </button>
                </form>
              )}
            </div>
            </>
          )}

          {/* ── ABP PLAN MODE ─────────────────────────────────────── */}
          {uploadMode === 'plan' && !planPreview && (
            <form onSubmit={handlePlanExtract}>
              <div className="form-group" style={{ marginBottom: '12px' }}>
                <label>Plant Source</label>
                <select className="form-control" value={uploadPlanPlantName}
                        onChange={(e) => setUploadPlanPlantName(e.target.value)}>
                  <option value="RSP">RSP (.xlsx)</option>
                  <option value="ISP">ISP (.xlsx)</option>
                  <option value="BSP">BSP (.xlsx)</option>
                  <option value="DSP">DSP (.xlsx)</option>
                  <option value="BSL">BSL (.xlsx)</option>
                  <option value="ASP_SSP_VISL">ASP / SSP / VISL combined (.xlsx)</option>
                  <option value="ASP">ASP — BARS / FORGINGS / PLATES (.pdf)</option>
                </select>
              </div>
              <div className="form-group" style={{ marginBottom: '12px' }}>
                <label>Financial Year</label>
                <select className="form-control" value={uploadPlanFY}
                        onChange={(e) => setUploadPlanFY(e.target.value)}>
                  {financialYears.map((fy) => <option key={fy} value={fy}>{fy}</option>)}
                </select>
              </div>
              <div style={{ fontSize: '7.5pt', color: '#5f6368', marginBottom: 8 }}>
                {uploadPlanPlantName === 'ASP'
                  ? 'ASP ABP Plan PDF → extracts BARS, FORGINGS, PLATES for all 12 months; computes Finished Steel per month.'
                  : 'RSP: sheet1 · ISP: SUMM PROD · BSP: Table 1 · DSP: Monthwise · BSL: PLAN SUMMARY · ASP/SSP/VISL: APP 26-27'}
              </div>
              <div className="form-group" style={{ marginBottom: '15px' }}>
                <label>{uploadPlanPlantName === 'ASP' ? 'ASP ABP Plan PDF' : 'ABP Excel File (.xlsx)'}</label>
                <input id="plan-file-input" type="file" className="form-control"
                       accept={uploadPlanPlantName === 'ASP' ? '.pdf' : '.xlsx'}
                       style={{ padding: '4px', fontSize: '0.8rem' }}
                       onChange={(e) => setUploadPlanFile(e.target.files[0])} />
              </div>
              <button type="submit" className="btn btn-primary" disabled={isPlanBusy}
                      style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                               backgroundColor: '#3b82f6', borderColor: '#3b82f6' }}>
                {isPlanBusy ? 'Extracting...' : (
                  <><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '8px' }}>
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
                  </svg>Extract & Preview Plan</>
                )}
              </button>
            </form>
          )}
          {uploadMode === 'plan' && planPreview && (
            <div>
              <div style={{ fontSize: '9pt', color: '#5f6368', marginBottom: 10 }}>
                <strong style={{ color: '#202124' }}>{planPreview.plant}</strong> · FY {planPreview.financial_year}
                <span style={{ marginLeft: 8, color: '#5f6368' }}>({planPreview.plan_rows?.filter(r=>r.status==='ok').length} rows ready)</span>
              </div>
              <div style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
                <button onClick={handlePlanInsert} disabled={isPlanBusy}
                        style={{ flex: 1, padding: '7px 0', fontSize: '8.5pt', fontWeight: 700,
                                 backgroundColor: '#10b981', border: 'none', color: '#fff',
                                 borderRadius: 4, cursor: 'pointer' }}>
                  {isPlanBusy ? 'Inserting...' : `Insert ${planPreview.plan_rows?.filter(r=>r.status==='ok').length} rows into DB`}
                </button>
                <button onClick={() => { setPlanPreview(null); setUploadPlanFile(null); const fi = document.getElementById('plan-file-input'); if (fi) fi.value = ''; }}
                        disabled={isPlanBusy}
                        style={{ padding: '7px 14px', fontSize: '8.5pt', background: 'none',
                                 border: '1px solid #5f6368', color: '#5f6368', borderRadius: 4, cursor: 'pointer' }}>
                  Discard
                </button>
              </div>
            </div>
          )}

          {/* RSP Technopara preview summary + insert controls */}
          {rspTechnoPreview && (
            <div>
              <div style={{ fontSize: '9pt', color: '#5f6368', marginBottom: 10 }}>
                <strong style={{ color: '#10b981' }}>RSP Technopara</strong> · {rspTechnoPreview.report_month}
                <div style={{ marginTop: 4, color: '#5f6368' }}>
                  {rspTechnoPreview.units_extracted} units · {rspTechnoPreview.total_params} parameters
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
                <button onClick={handleRspTechnoInsert} disabled={isRspTechnoBusy}
                        style={{ flex: 1, padding: '7px 0', fontSize: '8.5pt', fontWeight: 700,
                                 backgroundColor: '#10b981', border: 'none', color: '#fff',
                                 borderRadius: 4, cursor: 'pointer' }}>
                  {isRspTechnoBusy ? 'Saving...' : `Save ${rspTechnoPreview.units_extracted} units to DB`}
                </button>
                <button onClick={() => { setRspTechnoPreview(null); }}
                        disabled={isRspTechnoBusy}
                        style={{ padding: '7px 14px', fontSize: '8.5pt', background: 'none',
                                 border: '1px solid #5f6368', color: '#5f6368', borderRadius: 4, cursor: 'pointer' }}>
                  Discard
                </button>
              </div>
            </div>
          )}
        </div>

        <div style={{ marginTop: 'auto', fontSize: '0.75rem', color: '#5f6368', textAlign: 'center', paddingTop: '15px' }}>
          SAIL Informatics Report Portal • v1.0.0
        </div>
      </div>

      {/* Ingestion Console Screen */}
      <div className="preview-area" style={{ padding: '30px', backgroundColor: '#ffffff', overflowY: 'auto' }}>
        <div style={{ maxWidth: '800px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          
          {/* Headline */}
          <div>
            <h1 style={{ fontSize: '20pt', fontWeight: '800', color: '#202124', margin: 0 }}>
              Excel Data Extraction Control Room
            </h1>
            <p style={{ fontSize: '10pt', color: '#5f6368', marginTop: '4px', margin: 0 }}>
              Ingest plant spreadsheets, populate SQLite production tables, and seed techno-economic metrics dynamically.
            </p>
          </div>

          {/* Guidelines info card */}
          <div style={{ padding: '20px', backgroundColor: '#f8f9fa', border: '1px solid #dadce0', borderRadius: '8px' }}>
            <h3 style={{ fontSize: '11pt', fontWeight: '700', color: '#202124', margin: '0 0 12px 0', borderBottom: '1px solid #dadce0', paddingBottom: '6px' }}>
              Guidelines for Ingestion
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '25px' }}>
              <div>
                <h4 style={{ fontSize: '9.5pt', fontWeight: 'bold', color: '#10b981', margin: '0 0 6px 0' }}>RSP, ISP, BSP, BSL, DSP & ASP Actuals + Special Steel Ingestion</h4>
                <ul style={{ fontSize: '8.5pt', color: '#202124', lineHeight: '1.6', margin: 0, paddingLeft: '15px' }}>
                  <li><strong>RSP — Final Monthly (.xlsx):</strong> Sheets <strong>page-9</strong> + <strong>page 1-8</strong>. Set month manually.</li>
                  <li><strong>RSP — Morning Report (.xlsx):</strong> Sheet starts with <strong>&quot;RSP Morning Report Data for-&quot;</strong>. Month from <strong>A2</strong>. Auto-detected.</li>
                  <li><strong>ISP — Final Monthly (.xlsx):</strong> Sheet <strong>Maj Production Summ</strong>. Set month manually.</li>
                  <li><strong>ISP — Morning Report (.xlsx):</strong> Sheet <strong>DAILYREPORT1</strong>. Month from <strong>K5</strong>. Auto-detected. 19 items extracted.</li>
                  <li><strong>BSP — Flash Monthly (.pdf):</strong> One file replaces the PPC MIS / MIS-2 / Techno / OISCO uploads: full production (23 items + furnace-wise BF#1/4/5/6/7), ~80 techno params (coke yield, SP-2/3, blast furnaces incl. per-furnace CDI &amp; productivity, SMS-2/3, all six mills, energy rate) and closing stock (saved as next month&apos;s opening). Pages found by heading, month auto-detected from the cover.</li>
                  <li><strong>BSP — PPC MIS (.xls):</strong> Sheet <strong>S1</strong>. Month from <strong>N1</strong>. Auto-detected.</li>
                  <li><strong>BSP — MIS-2 Month-End (.xls/.xlsx):</strong> Furnace-wise Hot Metal production (tentative). Auto-detected by row 2 = "BSP MIS-2"; month from the "Date:" cell on row 2. Column D ("CUM") for furnace rows BF-1/4/5/6/7/8 → items <strong>BF#1</strong>/<strong>BF#4</strong>/<strong>BF#5</strong>/<strong>BF#6</strong>/<strong>BF#7</strong>/<strong>BF#8</strong>. BF#8 shares the existing item with the PPC MIS upload (preview shows current DB value for comparison) — the shop total is not extracted since it duplicates the existing <strong>Hot Metal</strong> item.</li>
                  <li><strong>BSL — DPR Mail (.xlsx):</strong> Sheet <strong>DPR</strong>. Month from <strong>O1</strong>. Auto-detected.</li>
                  <li><strong>BSL — Production of Main Products (.pdf):</strong> The plant&apos;s month-end PDF bundle (e.g. <em>Rev &lt;Mon&gt;&lt;YY&gt; (n).pdf</em>) — auto-detected by its <strong>&quot;PRODUCTION OF MAIN PRODUCTS&quot;</strong> page title, distinguishing it from the BF Performance PDF above. Reads the same 19 production items as the DPR path (Oven Pushing, Sinter, Hot Metal, Pig Iron, SMS-1 CCM-1, SMS-2 CCM-1&amp;2, Crude Steel, HSM HR Coil (total &amp; saleable), HSM HR Plate, HR Sheet, CRC(3), CRC&amp;S(1&amp;2), GPC3, GP/GC, CRSALE, Saleable Steel, Finished Steel, Saleable Semis) from the finalised monthly figures — Finished Steel and Saleable Semis come from the report&apos;s page 3 breakup table. Month auto-detected from the page header (e.g. &quot;JUNE 2026&quot;).</li>
                  <li><strong>BSL — Corporate Office Special Steel (.xlsx):</strong> Use <strong>Extraction with Preview → Insert</strong> (plant: BSL). Auto-detected by Sheet1 + "SPECIAL STEEL" title. Month from cell <strong>I2</strong>. Products: HR COIL / HR PLATE / HR SHEET / CR COIL/SHEET/GP GC / SLAB. Order Qty = col G (ORDER AVAILABLE TOTAL); Actual = col I (Despatch Till Date, monthly). Saves to <strong>special_steel_orders</strong>; shown on report page 22.</li>
                  <li><strong>DSP — MCR-I (.xls):</strong> Tab-separated text file (<em>mcr1_*.xls</em>). Month from header row. Auto-detected. 21 items extracted.</li>
                  <li><strong>ASP — asp.xlsx</strong> (Preview &amp; Insert, plant: ASP): Reads cells <strong>F10</strong> (Crude Steel), <strong>F11</strong> (Concast), <strong>F12</strong> (Ingot), <strong>F20</strong> (Saleable Steel), <strong>L25</strong> (Stock). Month <strong>auto-detected from E3</strong> (e.g. 30/04/2026 → Apr&apos;26). Sheet: <em>md cell</em>.</li>
                  <li><strong>ASP — REP*.pdf</strong> (Preview &amp; Insert, plant: ASP): Same items as xlsx via keyword search. Set month manually.</li>
                  <li><strong>ASP — FL*.pdf</strong> (Preview &amp; Insert, plant: ASP): Extracts <strong>BARS Mill, FS PRD, Plate Mill</strong> (Plan col2, Actual col3) + computes <strong>Finished Steel</strong> total. Set month manually.</li>
                  <li>All tonnage values converted Tonnes → &apos;000 T automatically. Every upload is logged below.</li>
                  <li><strong>BSP — Special Steel (.xlsx):</strong> Use <strong>Extraction with Preview → Insert</strong> (plant: BSP). File auto-detected by sheet name <strong>CORP</strong>. Extracts grade-wise Orders (Effective) &amp; Loading from BSP_Spstl-*.xlsx. Data saved to <strong>special_steel_orders</strong> and displayed on report page 19.</li>
                </ul>
              </div>
              <div>
                <h4 style={{ fontSize: '9.5pt', fontWeight: 'bold', color: '#3b82f6', margin: '0 0 6px 0' }}>RSP, ISP, BSP, DSP & BSL ABP Targets Ingestion (Annual)</h4>
                <ul style={{ fontSize: '8.5pt', color: '#202124', lineHeight: '1.6', margin: 0, paddingLeft: '15px' }}>
                  <li>Spreadsheet files must be in <strong>.xlsx</strong> format.</li>
                  <li><strong>RSP</strong> — sheet <strong>sheet1</strong>; <strong>ISP</strong> — sheet <strong>SUMM PROD</strong>; <strong>BSP</strong> — sheet <strong>Table 1</strong>; <strong>DSP</strong> — sheet <strong>Monthwise</strong>.</li>
                  <li><strong>BSL</strong> — sheet <strong>PLAN SUMMARY</strong>. Months in rows (Apr row 10 → Mar row 24), items in columns B–R. Quarter rows auto-skipped.</li>
                  <li><strong>ASP / SSP / VISL</strong> — single combined <code>.xlsx</code> file (sheet <strong>APP 26-27</strong>). Row 1 has month dates (col C onward); col A = plant name, col B = item. All three plants extracted in one upload.</li>
                  <li>Extracts and populates targets for all 12 months in a single upload.</li>
                  <li>Preserves the plan sheet scale.</li>
                </ul>
              </div>
            </div>
          </div>

          {/* ABP Plan preview — pivot table shown before DB insert */}
          {planPreview && (() => {
            const rows = planPreview.plan_rows || [];
            const plants = [...new Set(rows.map(r => r.plant))].sort();
            const months = [...new Set(rows.map(r => r.month))].sort();
            const fmtM = m => {
              const mn = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
              return `${mn[parseInt(m.slice(5))-1]}'${m.slice(2,4)}`;
            };
            const TH = { padding:'2px 5px', fontSize:'7.5pt', borderBottom:'1px solid #dadce0', whiteSpace:'nowrap', color:'#5f6368', textAlign:'right' };
            const TD = { padding:'2px 5px', fontSize:'8pt', textAlign:'right', borderBottom:'1px solid #f8f9fa' };
            const okCount = rows.filter(r => r.status === 'ok').length;
            return (
              <div style={{ padding:'16px', backgroundColor:'#f8f9fa', border:'1px solid #3b82f6', borderRadius:'8px' }}>
                <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:10 }}>
                  <h3 style={{ fontSize:'11pt', fontWeight:700, color:'#f8f9fa', margin:0 }}>
                    ABP Plan Preview — {planPreview.plant} FY {planPreview.financial_year}
                    <span style={{ fontSize:'8pt', color:'#5f6368', fontWeight:400, marginLeft:8 }}>{okCount} rows</span>
                  </h3>
                  <div style={{ display:'flex', gap:8 }}>
                    <button onClick={handlePlanInsert} disabled={isPlanBusy}
                            style={{ padding:'5px 14px', fontSize:'8.5pt', fontWeight:700, backgroundColor:'#10b981',
                                     border:'none', color:'#fff', borderRadius:4, cursor:'pointer' }}>
                      {isPlanBusy ? 'Inserting…' : `Insert ${okCount} rows`}
                    </button>
                    <button onClick={() => { setPlanPreview(null); setUploadPlanFile(null); const fi = document.getElementById('plan-file-input'); if (fi) fi.value = ''; }}
                            disabled={isPlanBusy}
                            style={{ padding:'5px 12px', fontSize:'8.5pt', background:'none',
                                     border:'1px solid #5f6368', color:'#5f6368', borderRadius:4, cursor:'pointer' }}>
                      Discard
                    </button>
                  </div>
                </div>
                {plants.map(plant => {
                  const pRows = rows.filter(r => r.plant === plant);
                  const items = [...new Set(pRows.map(r => r.item_name))];
                  const lookup = {};
                  pRows.forEach(r => {
                    if (!lookup[r.item_name]) lookup[r.item_name] = {};
                    lookup[r.item_name][r.month] = r;
                  });
                  return (
                    <div key={plant} style={{ marginBottom:12 }}>
                      {plants.length > 1 && (
                        <div style={{ fontSize:'8pt', fontWeight:700, color:'#60a5fa', marginBottom:4 }}>{plant}</div>
                      )}
                      <div style={{ overflowX:'auto' }}>
                        <table style={{ borderCollapse:'collapse', fontSize:'8pt', color:'#dadce0', width:'100%' }}>
                          <thead>
                            <tr>
                              <th style={{...TH, textAlign:'left', paddingLeft:6}}>Item</th>
                              {months.map(m => <th key={m} style={TH}>{fmtM(m)}</th>)}
                              <th style={TH}>Total</th>
                            </tr>
                          </thead>
                          <tbody>
                            {items.map(item => {
                              const unit = lookup[item]?.[months[0]]?.unit || "'000T";
                              const isFin = item === 'Finished Steel';
                              const vals = months.map(m => lookup[item]?.[m]?.value ?? null);
                              const total = vals.reduce((a,b) => a + (b ?? 0), 0);
                              const fmt = v => v === null ? '—' : unit === 'nos/d' ? v.toFixed(0) : (v * 1000).toFixed(0);
                              return (
                                <tr key={item}>
                                  <td style={{...TD, textAlign:'left', paddingLeft:6,
                                              fontWeight:isFin?700:400, color:isFin?'#34d399':'#dadce0'}}>
                                    {item}
                                  </td>
                                  {vals.map((v,i) => (
                                    <td key={i} style={{...TD, fontWeight:isFin?700:400, color:isFin?'#34d399':v===null?'#dadce0':'#dadce0'}}>
                                      {fmt(v)}
                                    </td>
                                  ))}
                                  <td style={{...TD, fontWeight:700, color:'#fbbf24'}}>{fmt(total)}</td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                      <div style={{fontSize:'7pt',color:'#5f6368',marginTop:3}}>
                        Values in {(lookup[items[0]]?.[months[0]]?.unit||"'000T") === 'nos/d' ? 'nos/d' : "T (display) — stored as '000T"}
                      </div>
                    </div>
                  );
                })}
              </div>
            );
          })()}

          {/* RSP extraction preview — verify production + stock + special-steel before insertion */}
          {technoPreview && (
            <div style={{ padding: '20px', backgroundColor: '#f8f9fa', border: '1px solid #8b5cf6', borderRadius: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                <h3 style={{ fontSize: '11pt', fontWeight: 700, color: '#202124', margin: 0 }}>
                  Extracted Data — {technoPreview.plant} {technoPreview.month}
                  <span style={{ fontSize: '8pt', color: '#5f6368', fontWeight: 400, marginLeft: 10 }}>
                    {technoPreview.source_type}{technoPreview.sheets ? ` · ${technoPreview.sheets}` : ''}
                  </span>
                </h3>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={() => { setTechnoPreview(null); setProdRows([]); setSsRows([]); setStockRows([]); }} disabled={isTechnoBusy}
                          style={{ background: 'none', border: '1px solid #5f6368', borderRadius: 4,
                                   color: '#5f6368', fontSize: '8.5pt', padding: '5px 12px', cursor: 'pointer' }}>
                    Discard
                  </button>
                  <button onClick={handleTechnoInsert} disabled={isTechnoBusy}
                          style={{ backgroundColor: '#10b981', border: '1px solid #10b981', borderRadius: 4,
                                   color: '#fff', fontSize: '8.5pt', fontWeight: 700, padding: '5px 14px', cursor: 'pointer' }}>
                    {isTechnoBusy ? 'Inserting...' : `Insert ${technoOkCount} rows into DB`}
                  </button>
                </div>
              </div>

              {/* 1. Production rows → production_table (selectable + item name editable) */}
              {prodRows.length > 0 && (
                <EditableProductionTable
                  plant={technoPreview.plant}
                  rows={prodRows}
                  onToggle={toggleProdRow}
                  onEditName={editProdRowName}
                />
              )}

              {/* 2. Special Steel rows → special_steel_orders */}
              {ssRows.length > 0 && (
                <EditableSpecialSteelTable
                  plant={technoPreview.plant}
                  rows={ssRows}
                  onToggle={toggleSsRow}
                  onEditGrade={editSsGrade}
                  onEditSection={editSsSection}
                />
              )}
              {technoPreview.special_steel_note && (
                <div style={{ fontSize: '8pt', color: '#fbbf24', margin: '4px 0' }}>
                  ⚠ {technoPreview.special_steel_note}
                </div>
              )}

              {/* 3. Opening Stock rows → stock_table */}
              {stockRows.length > 0 && (() => {
                const months = [...new Set(stockRows.map(r => r.stock_month).filter(Boolean))];
                const smLabel = months.join(', ');
                const okCount = stockRows.filter(r => r.status === 'ok').length;
                const plant = technoPreview?.plant || technoPlant || '';
                return (
                  <PreviewTable
                    title={`Opening Stock — ${plant} (${okCount} ok, stock_month: ${smLabel}) → stock_table`}
                    headers={['Item Type', 'Stock Type', 'Stock Month', "Value ('000T)", 'Formula', 'Status']}
                    rows={stockRows.map(r => [
                      r.item_type,
                      r.stock_type || '—',
                      r.stock_month || '—',
                      r.value != null ? r.value.toFixed(3) : '—',
                      r.formula,
                      r.status,
                    ])}
                  />
                );
              })()}

              <div style={{ fontSize: '8pt', color: '#5f6368', marginTop: 8 }}>
                Production: only <strong style={{ color: '#34d399' }}>ticked</strong> rows are inserted — untick any
                row to skip it, or type an item name on an <strong style={{ color: '#f87171' }}>unmapped</strong> row
                to map &amp; include it (raw tonne values are stored as &apos;000T). Renamed / newly mapped labels are
                remembered and applied automatically in future {technoPreview.plant} extractions.
                <span style={{ color: '#fbbf24' }}> Techno parameters are excluded from this flow — use the Techno Manual Entry page.</span>
              </div>
            </div>
          )}

          {/* DSP PDF — three independent block preview panels */}
          {(dspProdResult || dspProdAllMonths) && (
            <div style={{ padding: '20px', backgroundColor: '#f8f9fa', border: '1px solid #10b981', borderRadius: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <h3 style={{ fontSize: '11pt', fontWeight: 700, color: '#202124', margin: 0 }}>
                  Step 1 — Production&nbsp;
                  <span style={{ fontSize: '8pt', color: '#5f6368', fontWeight: 400 }}>
                    DSP {dspProdAllMonths?.month || dspProdResult?.month} · {dspProdAllMonths ? 'ALL MONTHS' : dspProdResult?.source_type}
                  </span>
                </h3>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={() => { setDspProdResult(null); setDspProdRows([]); setDspProdAllMonths(null); setDspAllMonthsMode(false); }}
                          disabled={dspBusy.production || dspBusy.production_all}
                          style={{ background: 'none', border: '1px solid #5f6368', borderRadius: 4,
                                   color: '#5f6368', fontSize: '8.5pt', padding: '5px 12px', cursor: 'pointer' }}>
                    Discard
                  </button>
                  <button onClick={() => handleDspInsert('production')}
                          disabled={dspBusy.production || dspBusy.production_all}
                          style={{ backgroundColor: '#10b981', border: '1px solid #10b981', borderRadius: 4,
                                   color: '#fff', fontSize: '8.5pt', fontWeight: 700, padding: '5px 14px', cursor: 'pointer' }}>
                    {dspBusy.production || dspBusy.production_all ? 'Processing...' : `Insert Production (${dspAllMonthsMode
                      ? (dspProdAllMonths?.grouped_rows || []).filter(r => r.status === 'ok').length + ' items'
                      : dspProdRows.filter(r => r.selected && (r.item_edit||'').trim()).length + ' rows'})`}
                  </button>
                </div>
              </div>
              {dspAllMonthsMode && dspProdAllMonths ? (
                <>
                  <AllMonthsProductionTable rows={dspProdAllMonths.grouped_rows} />
                  <div style={{ fontSize: '8pt', color: '#5f6368', marginTop: 12, padding: 10, backgroundColor: '#ffffff', borderRadius: 4 }}>
                    <strong>ℹ️ All Months Mode:</strong> Extract production data for all FY months (APR–SEP, APR–DEC, etc.).
                    Each row shows values across all extracted months. Click "Insert Production" to save all months to database.
                  </div>
                </>
              ) : (
                <EditableProductionTable plant="DSP" rows={dspProdRows}
                  onToggle={toggleDspProdRow} onEditName={editDspProdName} />
              )}
            </div>
          )}

          {dspSsResult && (
            <div style={{ padding: '20px', backgroundColor: '#f8f9fa', border: '1px solid #f59e0b', borderRadius: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <h3 style={{ fontSize: '11pt', fontWeight: 700, color: '#202124', margin: 0 }}>
                  Step 3 — Special Steel&nbsp;
                  <span style={{ fontSize: '8pt', color: '#5f6368', fontWeight: 400 }}>
                    DSP {dspSsResult.month}
                  </span>
                </h3>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={() => { setDspSsResult(null); setDspSsRows([]); }}
                          disabled={dspBusy.special_steel}
                          style={{ background: 'none', border: '1px solid #5f6368', borderRadius: 4,
                                   color: '#5f6368', fontSize: '8.5pt', padding: '5px 12px', cursor: 'pointer' }}>
                    Discard
                  </button>
                  <button onClick={() => handleDspInsert('special_steel')}
                          disabled={dspBusy.special_steel}
                          style={{ backgroundColor: '#f59e0b', border: '1px solid #f59e0b', borderRadius: 4,
                                   color: '#fff', fontSize: '8.5pt', fontWeight: 700, padding: '5px 14px', cursor: 'pointer' }}>
                    {dspBusy.special_steel ? 'Inserting...' : `Insert Special Steel (${dspSsRows.filter(r=>r.selected&&r.status==='ok').length} rows)`}
                  </button>
                </div>
              </div>
              {dspSsResult.special_steel_note && (
                <div style={{ fontSize: '8pt', color: '#fbbf24', margin: '4px 0 8px' }}>
                  {dspSsResult.special_steel_note}
                </div>
              )}
              <EditableSpecialSteelTable plant="DSP" rows={dspSsRows}
                onToggle={toggleDspSsRow} onEditGrade={editDspSsGrade} onEditSection={editDspSsSection} />
            </div>
          )}

          {/* DSP Flash Stock preview panel */}
          {dspStockResult && (
            <div style={{ padding: '20px', backgroundColor: '#f8f9fa', border: '1px solid #ef4444', borderRadius: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <h3 style={{ fontSize: '11pt', fontWeight: 700, color: '#202124', margin: 0 }}>
                  Step 4 — Closing Stock (Flash.pdf)&nbsp;
                  <span style={{ fontSize: '8pt', color: '#5f6368', fontWeight: 400 }}>
                    DSP {dspStockResult.month}
                    {dspStockResult.detected_date ? ` · file date ${dspStockResult.detected_date}` : ''}
                  </span>
                </h3>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={() => setDspStockResult(null)}
                          disabled={dspBusy.stock}
                          style={{ background: 'none', border: '1px solid #5f6368', borderRadius: 4,
                                   color: '#5f6368', fontSize: '8.5pt', padding: '5px 12px', cursor: 'pointer' }}>
                    Discard
                  </button>
                  <button onClick={() => handleDspInsert('stock')}
                          disabled={dspBusy.stock}
                          style={{ backgroundColor: '#ef4444', border: '1px solid #ef4444', borderRadius: 4,
                                   color: '#fff', fontSize: '8.5pt', fontWeight: 700, padding: '5px 14px', cursor: 'pointer' }}>
                    {dspBusy.stock ? 'Inserting...' : `Insert Stock (${(dspStockResult.stock_rows || []).filter(r => r.status === 'ok').length} rows)`}
                  </button>
                </div>
              </div>
              {dspStockResult.month_mismatch && (
                <div style={{ fontSize: '8pt', color: '#fbbf24', marginBottom: 8 }}>
                  Warning: file date {dspStockResult.detected_date} (month {dspStockResult.detected_month}) does not match selected month {dspStockResult.selected_month}.
                </div>
              )}
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '8.5pt' }}>
                <thead>
                  <tr>
                    {['Item Type', 'Stock Type', "Value ('000T)", 'Formula', 'Status'].map((h) => (
                      <th key={h} style={{ padding: '4px 8px', backgroundColor: '#f1f3f4', color: '#5f6368',
                                           textAlign: 'left', border: '1px solid #dadce0' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(dspStockResult.stock_rows || []).map((r, i) => (
                    <tr key={i} style={{ backgroundColor: i % 2 ? '#f8f9fa' : '#263548' }}>
                      <td style={{ padding: '3px 8px', border: '1px solid #dadce0', color: '#202124' }}>{r.item_type}</td>
                      <td style={{ padding: '3px 8px', border: '1px solid #dadce0', color: '#202124' }}>{r.stock_type || '—'}</td>
                      <td style={{ padding: '3px 8px', border: '1px solid #dadce0', color: r.status === 'ok' ? '#86efac' : '#f87171',
                                   textAlign: 'right' }}>{r.value != null ? r.value.toFixed(3) : '—'}</td>
                      <td style={{ padding: '3px 8px', border: '1px solid #dadce0', color: '#5f6368' }}>{r.formula}</td>
                      <td style={{ padding: '3px 8px', border: '1px solid #dadce0',
                                   color: r.status === 'ok' ? '#86efac' : '#f87171' }}>{r.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div style={{ fontSize: '7.5pt', color: '#5f6368', marginTop: 6 }}>
                Stock month (opening of next month): {(dspStockResult.stock_rows || [])[0]?.stock_month || '—'}
              </div>
            </div>
          )}

          {/* ASP PDF — single-step extract & preview panel */}
          {aspResult && (
            <div style={{ padding: '20px', backgroundColor: '#f8f9fa', border: '1px solid #0ea5e9', borderRadius: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <h3 style={{ fontSize: '11pt', fontWeight: 700, color: '#202124', margin: 0 }}>
                  ASP —&nbsp;
                  {aspResult.report_type === 'EXCEL' ? 'Crude Steel (Excel)'
                    : aspResult.report_type === 'REP' ? 'Crude Steel (REP PDF)'
                    : 'Finished Steel (FL PDF)'}
                  &nbsp;<span style={{ fontSize: '8pt', color: '#5f6368', fontWeight: 400 }}>
                    ASP {aspResult.month} · {aspResult.source_type}
                  </span>
                </h3>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={() => { setAspResult(null); setAspProdRows([]); }}
                          disabled={aspBusy}
                          style={{ background: 'none', border: '1px solid #5f6368', borderRadius: 4,
                                   color: '#5f6368', fontSize: '8.5pt', padding: '5px 12px', cursor: 'pointer' }}>
                    Discard
                  </button>
                  <button onClick={handleAspInsert}
                          disabled={aspBusy}
                          style={{ backgroundColor: '#0ea5e9', border: '1px solid #0ea5e9', borderRadius: 4,
                                   color: '#fff', fontSize: '8.5pt', fontWeight: 700, padding: '5px 14px', cursor: 'pointer' }}>
                    {aspBusy ? 'Inserting...' : `Insert ${aspProdRows.filter(r => r.selected && (r.item_edit||'').trim()).length} rows into DB`}
                  </button>
                </div>
              </div>

              {/* Report type badge */}
              <div style={{ marginBottom: 10 }}>
                {(() => {
                  const rt = aspResult.report_type;
                  const color = rt === 'EXCEL' ? '#1a73e8' : rt === 'REP' ? '#34d399' : '#fbbf24';
                  const bg    = rt === 'EXCEL' ? 'rgba(56,189,248,0.12)' : rt === 'REP' ? 'rgba(16,185,129,0.15)' : 'rgba(245,158,11,0.15)';
                  const label = rt === 'EXCEL'
                    ? `Excel (${aspResult.sheets}) — cells F10/F11/F12/F20/L25 → Crude Steel, Concast, Ingot, Saleable, Stock`
                    : rt === 'REP'
                    ? 'REP PDF — OMI Production (Crude Steel, Ingot, Concast, Saleable, Stock)'
                    : 'FL PDF — Finished Steel by Mill (BARS + FS PRD + PL MILL)';
                  return (
                    <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: 4,
                                   fontSize: '8pt', fontWeight: 700, backgroundColor: bg,
                                   color, border: `1px solid ${color}` }}>
                      {label}
                    </span>
                  );
                })()}
              </div>

              <EditableProductionTable plant="ASP" rows={aspProdRows}
                onToggle={toggleAspRow} onEditName={editAspRowName} />

              <div style={{ fontSize: '8pt', color: '#5f6368', marginTop: 8 }}>
                All values converted from Tonnes → &apos;000T automatically. Tick/untick rows to include or skip.
                Edit item names to override the DB mapping. For multi-month PDFs, verify the &quot;Value&quot; column
                matches the expected month-end figure (extractor picks the largest number on each keyword line).
              </div>
            </div>
          )}

          {/* Terminal log window */}
          <div style={{
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: '9.5pt',
            backgroundColor: '#020617',
            border: '1px solid #30363d',
            borderRadius: '6px',
            padding: '20px',
            minHeight: '280px',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            color: '#e2e8f0',
            boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.6)'
          }}>
            <div style={{ color: '#8b949e', borderBottom: '1px solid #30363d', paddingBottom: '6px', marginBottom: '4px', fontSize: '8pt', display: 'flex', justifyContent: 'space-between' }}>
              <span>EXTRACTION JOB OUTPUT LOGS</span>
              <span>v1.0.0</span>
            </div>
            
            {logs.map((log, index) => {
              let color = '#1a73e8';
              let prefix = '[INFO]';
              if (log.type === 'success') {
                color = '#34d399';
                prefix = '[SUCCESS]';
              } else if (log.type === 'error') {
                color = '#f87171';
                prefix = '[ERROR]';
              }
              return (
                <div key={index} style={{ display: 'flex', gap: '8px', lineHeight: '1.4' }}>
                  <span style={{ color: '#8b949e' }}>{log.time || '--:--:--'}</span>
                  <span style={{ color }}>{prefix}</span>
                  <span style={{ color: log.type === 'error' ? '#f87171' : '#e2e8f0' }}>{log.text}</span>
                </div>
              );
            })}
            
            {isUploading && (
              <div style={{ color: '#fbbf24', display: 'flex', gap: '8px', animation: 'pulse 1.5s infinite' }}>
                <span>{new Date().toLocaleTimeString()}</span>
                <span>[PROCESS]</span>
                <span>Data extraction script is executing... Please wait...</span>
              </div>
            )}
          </div>

          {/* Extraction Audit Log */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <h2 style={{ fontSize: '12pt', fontWeight: '700', color: '#202124', margin: 0 }}>
                Extraction Audit Log
              </h2>
              <button
                onClick={fetchExtractionLog}
                style={{ background: 'none', border: '1px solid #dadce0', borderRadius: '4px', color: '#5f6368', fontSize: '8pt', padding: '4px 10px', cursor: 'pointer' }}
              >
                Refresh
              </button>
            </div>

            {extractionLog.length === 0 ? (
              <div style={{ padding: '20px', textAlign: 'center', color: '#5f6368', fontSize: '9pt', backgroundColor: '#f8f9fa', border: '1px solid #dadce0', borderRadius: '6px' }}>
                No extractions recorded yet.
              </div>
            ) : (
              <div style={{ overflowX: 'auto', border: '1px solid #dadce0', borderRadius: '6px', overflow: 'hidden' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '8.5pt' }}>
                  <thead>
                    <tr style={{ backgroundColor: '#f8f9fa' }}>
                      {['Timestamp', 'Plant', 'Month', 'Source Type', 'File Name', 'Sheet', 'Items'].map(h => (
                        <th key={h} style={{ padding: '8px 12px', textAlign: 'left', color: '#5f6368', fontWeight: '600', borderBottom: '1px solid #dadce0', whiteSpace: 'nowrap' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {extractionLog.map((entry, idx) => (
                      <tr key={entry.id} style={{ backgroundColor: idx % 2 === 0 ? '#ffffff' : '#f8f9fa', borderBottom: '1px solid #f8f9fa' }}>
                        <td style={{ padding: '7px 12px', color: '#5f6368', whiteSpace: 'nowrap' }}>{entry.logged_at}</td>
                        <td style={{ padding: '7px 12px', color: '#1a73e8', fontWeight: '600' }}>{entry.plant_name}</td>
                        <td style={{ padding: '7px 12px', color: '#202124', whiteSpace: 'nowrap' }}>{entry.report_month}</td>
                        <td style={{ padding: '7px 12px' }}>
                          <span style={{
                            padding: '2px 7px', borderRadius: '4px', fontSize: '7.5pt', fontWeight: '600',
                            backgroundColor: entry.source_type?.includes('Monthly') ? 'rgba(16,185,129,0.15)' : entry.source_type?.includes('Morning') ? 'rgba(245,158,11,0.15)' : 'rgba(99,102,241,0.15)',
                            color: entry.source_type?.includes('Monthly') ? '#34d399' : entry.source_type?.includes('Morning') ? '#fbbf24' : '#a5b4fc',
                          }}>
                            {entry.source_type}
                          </span>
                        </td>
                        <td style={{ padding: '7px 12px', color: '#5f6368', maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={entry.file_name}>{entry.file_name}</td>
                        <td style={{ padding: '7px 12px', color: '#5f6368', fontFamily: 'monospace' }}>{entry.sheet_name}</td>
                        <td style={{ padding: '7px 12px', color: '#34d399', textAlign: 'right', fontWeight: '700' }}>{entry.items_extracted}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

        </div>
      </div>
    </main>
    </>
  );
}

export default function UploadPage() {
  return (
    <RequireEditor>
      <UploadPageInner />
    </RequireEditor>
  );
}

