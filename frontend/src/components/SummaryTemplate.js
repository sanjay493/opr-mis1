'use client';
import React from 'react';

// ---------------------------------------------------------------------------
// Bar chart colours  (match screenshot palette)
// ---------------------------------------------------------------------------
const C_FY      = '#FFC000';  // gold   – past FY actuals
const C_TARGET  = '#70AD47';  // green  – current FY target
const C_MONTHLY = '#4472C4';  // blue   – current FY month(s)
const SEP_W = 4;              // px gap between bar groups

function fmtBarVal(v) {
  const a = Math.abs(v);
  if (a >= 100) return String(Math.round(v));
  if (a >= 10)  return v.toFixed(1).replace(/\.?0+$/, '');
  if (a >= 1)   return v.toFixed(2).replace(/\.?0+$/, '');
  return v.toFixed(3).replace(/\.?0+$/, '');
}

function ParamBarChart({ paramData }) {
  const { name = '', unit = '', fy_bars = [], target_bar = {}, monthly_bars = [] } = paramData || {};

  const vw = 290, vh = 165;
  const mt = 28, mb = 32, ml = 5, mr = 5;
  const cw = vw - ml - mr;
  const ch = vh - mt - mb;

  const bars = [
    ...fy_bars.map(b => ({ label: b.label, value: b.value, color: C_FY })),
    { sep: true },
    { label: target_bar.label || '', value: target_bar.value ?? null, color: C_TARGET },
    { sep: true },
    ...monthly_bars.map(b => ({ label: b.label, value: b.value, color: C_MONTHLY })),
  ];

  const valid = bars.filter(e => !e.sep && e.value != null).map(e => e.value);
  if (!valid.length) {
    return (
      <svg viewBox={`0 0 ${vw} ${vh}`} style={{ width: '100%' }}>
        <rect width={vw} height={vh} fill="#f8fafc" rx="3" />
        <text x={vw / 2} y={vh / 2} textAnchor="middle" fontSize="9" fill="#94a3b8">{name} – no data</text>
      </svg>
    );
  }

  const yloV = Math.min(...valid), yhiV = Math.max(...valid);
  const rng = yhiV - yloV;
  const padLo = rng > 0 ? rng * 0.66 : Math.max(Math.abs(yhiV) * 0.1, 0.5);
  const padHi = rng > 0 ? rng * 0.23 : Math.max(Math.abs(yhiV) * 0.05, 0.2);
  const ylo = yloV - padLo, yhi = yhiV + padHi;
  const yspan = yhi - ylo;

  const ys = v => mt + ch * (1 - (v - ylo) / yspan);

  const nSeps = bars.filter(e => e.sep).length;
  const nBars = bars.length - nSeps;
  const many = nBars > 7;
  const slotW = (cw - nSeps * SEP_W) / Math.max(nBars, 1);
  const barW = Math.max(5, slotW * 0.78);

  const elements = [];
  let x = ml;

  bars.forEach((e, idx) => {
    if (e.sep) { x += SEP_W; return; }
    const bx = x + (slotW - barW) / 2;
    const v = e.value;

    if (v != null) {
      const bh = Math.max(1, (v - ylo) / yspan * ch);
      const by = ys(v);
      elements.push(
        <rect key={`bar-${idx}`} x={bx.toFixed(1)} y={by.toFixed(1)}
          width={barW.toFixed(1)} height={bh.toFixed(1)}
          fill={e.color} rx="1.5" />
      );
      // Value label above bar
      elements.push(
        <text key={`val-${idx}`}
          x={(bx + barW / 2).toFixed(1)} y={(by - 3).toFixed(1)}
          textAnchor="middle" fontSize="7" fontWeight="bold" fill={e.color}>
          {fmtBarVal(v)}
        </text>
      );
    }

    // X-axis label
    const lbl = e.label || '';
    const lx = bx + barW / 2;
    const parts = lbl.split('\n');
    if (parts.length === 1) {
      if (many) {
        const ly = mt + ch + 7;
        elements.push(
          <text key={`lbl-${idx}`} x={lx.toFixed(1)} y={ly.toFixed(1)}
            textAnchor="end" fontSize="6" fill="#374151"
            transform={`rotate(-40,${lx.toFixed(1)},${ly.toFixed(1)})`}>
            {lbl}
          </text>
        );
      } else {
        elements.push(
          <text key={`lbl-${idx}`} x={lx.toFixed(1)} y={(mt + ch + 10).toFixed(1)}
            textAnchor="middle" fontSize="6.5" fill="#374151">
            {lbl}
          </text>
        );
      }
    } else {
      // Two-line label (target bar)
      elements.push(
        <text key={`lbl1-${idx}`} x={lx.toFixed(1)} y={(mt + ch + 10).toFixed(1)}
          textAnchor="middle" fontSize="6.5" fill="#374151">{parts[0]}</text>
      );
      elements.push(
        <text key={`lbl2-${idx}`} x={lx.toFixed(1)} y={(mt + ch + 19).toFixed(1)}
          textAnchor="middle" fontSize="6.5" fill="#374151">{parts[1]}</text>
      );
    }
    x += slotW;
  });

  return (
    <svg viewBox={`0 0 ${vw} ${vh}`} style={{ width: '100%' }}>
      {/* Chart title */}
      <text x={vw / 2} y={13} textAnchor="middle" fontSize="8.5" fontWeight="bold" fill="#1e293b">
        {name} ({unit})
      </text>
      {/* Baseline */}
      <line x1={ml} y1={(mt + ch).toFixed(1)} x2={vw - mr} y2={(mt + ch).toFixed(1)}
        stroke="#374151" strokeWidth="0.6" />
      {elements}
    </svg>
  );
}

function ChartGrid({ chartData }) {
  const params = chartData?.params || [];
  if (params.length < 4) return null;

  return (
    <div style={{ marginTop: '6px' }}>
      {[0, 2].map(rowStart => (
        <div key={rowStart} style={{ display: 'flex', gap: '4px', marginBottom: '3px' }}>
          {[0, 1].map(col => (
            <div key={col} style={{
              flex: 1, border: '0.5px solid #e2e8f0', borderRadius: '3px', padding: '2px'
            }}>
              <ParamBarChart paramData={params[rowStart + col]} />
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main template
// ---------------------------------------------------------------------------
export default function SummaryTemplate({ data, onCellChange, selectedMonth }) {
  const {
    production_table = [],
    te_table = [],
    highlights = [],
    chart_data,
    production_narrative = '',
  } = data || {};

  const monthsOrder = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
  ];

  const _def = new Date(Date.now() - 45 * 24 * 60 * 60 * 1000);
  let monthName = monthsOrder[_def.getMonth()];
  let yearStr   = _def.getFullYear().toString();
  if (selectedMonth && /^\d{4}-\d{2}$/.test(selectedMonth)) {
    yearStr   = selectedMonth.substring(0, 4);
    monthName = monthsOrder[parseInt(selectedMonth.substring(5, 7), 10) - 1] || monthName;
  }

  const shortMonth    = monthName.substring(0, 3);
  const prevYear      = (Number(yearStr) - 1).toString();
  const shortYear     = yearStr.substring(2);
  const shortPrevYear = prevYear.substring(2);
  const monthIndex    = monthsOrder.indexOf(monthName);
  const isApril       = monthName === 'April';

  let targetYearStart = Number(yearStr);
  if (monthIndex >= 0 && monthIndex < 3) targetYearStart -= 1;
  const targetYearEnd = (targetYearStart + 1) % 100;
  const targetHeader  = `Target ${targetYearStart}-${targetYearEnd.toString().padStart(2, '0')}`;

  // -- handlers --
  const handleProdChange = (rowIndex, valIndex, newVal) => {
    const updatedProd = [...production_table];
    updatedProd[rowIndex] = { ...updatedProd[rowIndex] };
    updatedProd[rowIndex].values = [...updatedProd[rowIndex].values];
    updatedProd[rowIndex].values[valIndex] = newVal;
    onCellChange({ ...data, production_table: updatedProd });
  };

  const handleTeChange = (rowIndex, valIndex, newVal) => {
    const updatedTe = [...te_table];
    updatedTe[rowIndex] = { ...updatedTe[rowIndex] };
    updatedTe[rowIndex].values = [...updatedTe[rowIndex].values];
    updatedTe[rowIndex].values[valIndex] = newVal;
    onCellChange({ ...data, te_table: updatedTe });
  };

  const handleNarrativeChange = (newVal) =>
    onCellChange({ ...data, production_narrative: newVal });

  const handleHighlightsChange = (newVal) =>
    onCellChange({ ...data, highlights: newVal.split('\n') });

  const highlightsText = Array.isArray(highlights) ? highlights.join('\n') : (highlights || '');

  const textareaStyle = {
    width: '100%',
    border: 'none',
    borderBottom: '1px dashed #cbd5e1',
    background: 'transparent',
    resize: 'none',
    fontFamily: 'inherit',
    fontSize: 'inherit',
    lineHeight: '1.4',
    color: '#1e293b',
    outline: 'none',
    padding: '1px 0',
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>

      {/* ── Production narrative (editable) ── */}
      <div>
        <div style={{ fontWeight: '700', fontSize: '0.95em' }}>Production:</div>
        <div style={{ fontWeight: '700', fontSize: '0.9em' }}>{shortMonth}&#39;{shortYear}:</div>
        <textarea
          style={{ ...textareaStyle, marginTop: '2px' }}
          rows={3}
          value={production_narrative}
          onChange={e => handleNarrativeChange(e.target.value)}
          placeholder="Enter production narrative..."
        />
      </div>

      {/* ── Production table ── */}
      <div>
        <div style={{ textAlign: 'right', fontSize: '0.78em', fontStyle: 'italic', marginBottom: '2px' }}>
          Unit: &#39;000 T
        </div>
        <table className="report-table" style={{ tableLayout: 'fixed', width: '100%', fontSize: '0.82em' }}>
          {isApril ? (
            <colgroup>
              <col style={{ width: '22%' }} />
              <col style={{ width: '10%' }} /><col style={{ width: '10%' }} />
              <col style={{ width: '10%' }} /><col style={{ width: '10%' }} />
              <col style={{ width: '19%' }} /><col style={{ width: '19%' }} />
            </colgroup>
          ) : (
            <colgroup>
              <col style={{ width: '16%' }} />
              <col style={{ width: '6%' }} /><col style={{ width: '6%' }} />
              <col style={{ width: '6%' }} /><col style={{ width: '6%' }} />
              <col style={{ width: '6%' }} /><col style={{ width: '5%' }} />
              <col style={{ width: '6%' }} /><col style={{ width: '6%' }} />
              <col style={{ width: '6%' }} /><col style={{ width: '6%' }} />
              <col style={{ width: '7%' }} /><col style={{ width: '6%' }} />
            </colgroup>
          )}
          <thead style={{ fontSize: '0.78em', lineHeight: 1.1 }}>
            {isApril ? (
              <>
                <tr>
                  <th rowSpan="2" style={{ textAlign: 'left', verticalAlign: 'middle' }}>Item</th>
                  <th colSpan="4" style={{ textAlign: 'center' }}>{shortMonth}&#39;{shortYear}</th>
                  <th rowSpan="2" style={{ textAlign: 'center', whiteSpace: 'normal' }}>
                    {shortMonth}&#39;{shortPrevYear}<br/>ACT
                  </th>
                  <th rowSpan="2" style={{ textAlign: 'center', whiteSpace: 'normal' }}>
                    %GR.<br/>{shortMonth}&#39;{shortPrevYear}
                  </th>
                </tr>
                <tr>
                  <th style={{ textAlign: 'center' }}>APP</th>
                  <th style={{ textAlign: 'center' }}>ACT</th>
                  <th style={{ textAlign: 'center' }}>VAR</th>
                  <th style={{ textAlign: 'center' }}>%FUL.</th>
                </tr>
              </>
            ) : (
              <>
                <tr>
                  <th rowSpan="2" style={{ textAlign: 'left', verticalAlign: 'middle' }}>Item</th>
                  <th colSpan="4" style={{ textAlign: 'center' }}>{shortMonth}&#39;{shortYear}</th>
                  <th rowSpan="2" style={{ textAlign: 'center', whiteSpace: 'normal' }}>
                    {shortMonth}&#39;{shortPrevYear}<br/>ACT
                  </th>
                  <th rowSpan="2" style={{ textAlign: 'center', whiteSpace: 'normal' }}>
                    %GR.<br/>{shortMonth}&#39;{shortPrevYear}
                  </th>
                  <th colSpan="4" style={{ textAlign: 'center' }}>Apr-{shortMonth}&#39;{shortYear}</th>
                  <th rowSpan="2" style={{ textAlign: 'center', whiteSpace: 'normal' }}>
                    Apr-{shortMonth}&#39;{shortPrevYear}<br/>ACT
                  </th>
                  <th rowSpan="2" style={{ textAlign: 'center', whiteSpace: 'normal' }}>
                    %GR.<br/>Apr-{shortMonth}&#39;{shortPrevYear}
                  </th>
                </tr>
                <tr>
                  <th style={{ textAlign: 'center' }}>APP</th>
                  <th style={{ textAlign: 'center' }}>ACT</th>
                  <th style={{ textAlign: 'center' }}>VAR</th>
                  <th style={{ textAlign: 'center' }}>%FUL.</th>
                  <th style={{ textAlign: 'center' }}>APP</th>
                  <th style={{ textAlign: 'center' }}>ACT</th>
                  <th style={{ textAlign: 'center' }}>VAR</th>
                  <th style={{ textAlign: 'center' }}>%FUL.</th>
                </tr>
              </>
            )}
          </thead>
          <tbody>
            {production_table.map((row, rIdx) => (
              <tr key={rIdx}>
                <td className="label-cell">{row.item}</td>
                {(isApril ? [0, 1, 2, 3, 4, 5] : [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]).map(vIdx => (
                  <td key={vIdx} style={{ textAlign: 'right' }}>
                    <input type="text" className="editor-input"
                      style={{ color: 'black', textAlign: 'right', fontWeight: (vIdx === 1 || vIdx === 7) ? '700' : '400' }}
                      value={(row.values || [])[vIdx] ?? ''}
                      onChange={e => handleProdChange(rIdx, vIdx, e.target.value)}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        <div style={{ fontSize: '0.75em', fontStyle: 'italic', marginTop: '2px', color: '#475569' }}>
          *includes conversion
        </div>
      </div>

      {/* ── Highlights (editable textarea) ── */}
      <div>
        <div style={{ fontWeight: '700', fontSize: '0.95em' }}>Highlights:</div>
        <textarea
          style={{ ...textareaStyle, marginTop: '2px' }}
          rows={4}
          value={highlightsText}
          onChange={e => handleHighlightsChange(e.target.value)}
          placeholder="Enter highlights..."
        />
      </div>

      {/* ── SAIL Performance Summary Table ── */}
      <div>
        <div style={{ fontWeight: '700', fontSize: '0.95em', marginBottom: '3px' }}>
          SAIL Performance Summary - Key BF Parameters:
          {data.sail_is_user_supplied && (
            <span style={{ marginLeft: '12px', fontSize: '0.85em', color: '#059669', fontWeight: '600' }}>
              ✏️ (User-supplied values)
            </span>
          )}
        </div>
        <table className="report-table" style={{ tableLayout: 'fixed', width: '100%', fontSize: '0.82em' }}>
          <thead style={{ fontSize: '0.78em', lineHeight: 1.1 }}>
            <tr>
              <th style={{ width: '20%', textAlign: 'left' }}>Parameter</th>
              <th style={{ width: '8%', textAlign: 'center' }}>Unit</th>
              <th style={{ width: '11%', textAlign: 'center', whiteSpace: 'normal' }}>{targetHeader}</th>
              <th style={{ width: '11%', textAlign: 'center', whiteSpace: 'normal' }}>{shortMonth}&#39;{shortYear}<br/>(Report)</th>
              <th style={{ width: '11%', textAlign: 'center', whiteSpace: 'normal' }}>{shortMonth}&#39;{shortPrevYear}<br/>(CPLY)</th>
              <th style={{ width: '13%', textAlign: 'center', whiteSpace: 'normal' }}>Apr-{shortMonth}&#39;{shortYear}<br/>(YTD)</th>
              <th style={{ width: '13%', textAlign: 'center', whiteSpace: 'normal' }}>Apr-{shortMonth}&#39;{shortPrevYear}<br/>(CPLY YTD)</th>
            </tr>
          </thead>
          <tbody>
            {te_table.map((row, rIdx) => (
              <tr key={rIdx}>
                <td className="label-cell" style={{ fontWeight: '600' }}>{row.parameter}</td>
                <td className="label-cell" style={{ fontStyle: 'italic', color: '#475569', textAlign: 'center' }}>{row.unit}</td>
                {[0, 1, 2, 3, 4].map(vIdx => (
                  <td key={vIdx} style={{ textAlign: 'right' }}>
                    <input type="text" className="editor-input"
                      style={{ color: 'black', textAlign: 'right', fontWeight: vIdx === 1 ? '700' : '400' }}
                      value={(row.values || [])[vIdx] ?? ''}
                      onChange={e => handleTeChange(rIdx, vIdx, e.target.value)}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── SAIL Bar Charts 2×2: Coke Rate, CDI, BF Productivity, S.E.C. ── */}
      {chart_data?.params?.length > 0 && (
        <div style={{ marginTop: '12px' }}>
          <div style={{ fontWeight: '700', fontSize: '0.95em', marginBottom: '6px' }}>
            Historical Performance &amp; Trends (Last 3 FY + Plan + Current Month):
          </div>
          <ChartGrid chartData={chart_data} />
        </div>
      )}

    </div>
  );
}
