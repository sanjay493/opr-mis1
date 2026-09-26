'use client';

import React, { useState, useEffect, useMemo } from 'react';
import {
  API_BASE, MONTH_NAMES_FULL, MONTH_NUM, YEARS, FY_END_YEARS, CURRENT_FY_END_YEAR,
  getDefaultPeriod, fmtNum as fmtNum3, cell, selStyle, th, pillStyle, SegmentedToggle,
  ErrorBox, EmptyState, TabIntro, ExportButtons, downloadFile,
} from './shared';

const fmtNum = (v) => fmtNum3(v, 2);

export default function TechnoBfFurnaceView() {
  const def = getDefaultPeriod();
  const [meta, setMeta] = useState(null);
  const [metaError, setMetaError] = useState(null);
  const [selectedFurnaces, setSelectedFurnaces] = useState([]);
  const [selectedParams, setSelectedParams] = useState([]);
  const [mode, setMode] = useState('month_till'); // 'range' | 'month_till' | 'annual'
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState(null);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);

  // Duration inputs
  const [startMonthName, setStartMonthName] = useState(def.monthName);
  const [startYear, setStartYear] = useState(def.year);
  const [endMonthName, setEndMonthName] = useState(def.monthName);
  const [endYear, setEndYear] = useState(def.year);
  const [monthName, setMonthName] = useState(def.monthName);
  const [year, setYear] = useState(def.year);
  const [fyEndYear, setFyEndYear] = useState(String(CURRENT_FY_END_YEAR));

  useEffect(() => {
    fetch(`${API_BASE}/api/techno-bf-furnace/meta`)
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((d) => {
        setMeta(d);
        setSelectedFurnaces(d.furnace_keys || []);
        setSelectedParams((d.params || []).map((p) => p.key));
      })
      .catch((e) => setMetaError(`Failed to load furnace/parameter list: ${e.message}`));
  }, []);

  const toggleFurnace = (key) => setSelectedFurnaces((prev) =>
    prev.includes(key) ? prev.filter((x) => x !== key) : [...prev, key]);
  const toggleParam = (key) => setSelectedParams((prev) =>
    prev.includes(key) ? prev.filter((x) => x !== key) : [...prev, key]);

  const allFurnaceKeys = meta?.furnace_keys || [];
  const allParamKeys = useMemo(() => (meta?.params || []).map((p) => p.key), [meta]);

  const buildBody = () => {
    const body = {
      furnaces: selectedFurnaces,
      params: selectedParams.length === allParamKeys.length ? null : selectedParams,
      mode,
    };
    if (mode === 'range') {
      body.start_month = `${startYear}-${MONTH_NUM[startMonthName]}`;
      body.end_month = `${endYear}-${MONTH_NUM[endMonthName]}`;
    } else if (mode === 'month_till') {
      body.month = `${year}-${MONTH_NUM[monthName]}`;
    } else if (mode === 'annual') {
      body.fy_end_year = parseInt(fyEndYear, 10);
    }
    return body;
  };

  // Hide a generated table once its inputs change, so the table on screen
  // and the Excel/PDF export (built from the current inputs) always match.
  const inputsKey = JSON.stringify(buildBody());
  const [dataKey, setDataKey] = useState(null);
  const current = dataKey === inputsKey ? data : null;

  const fetchReport = () => {
    if (selectedFurnaces.length === 0) { setError('Select at least one furnace.'); return; }
    setLoading(true);
    setError(null);
    fetch(`${API_BASE}/api/techno-bf-furnace/report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildBody()),
    })
      .then(async (r) => {
        if (!r.ok) { const b = await r.json().catch(() => ({})); throw new Error(b.detail || `HTTP ${r.status}`); }
        return r.json();
      })
      .then((d) => { setData(d); setDataKey(inputsKey); })
      .catch((e) => setError(`Failed to load data: ${e.message}`))
      .finally(() => setLoading(false));
  };

  const handleDownload = async (kind) => {
    setDownloading(kind);
    try {
      await downloadFile(
        `${API_BASE}/api/techno-bf-furnace/${kind}`,
        buildBody(),
        `BF_Techno_Report.${kind === 'excel' ? 'xlsx' : 'pdf'}`
      );
    } catch (e) {
      setError(`Download failed: ${e.message}`);
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div>
      <TabIntro>
        Furnace-wise techno-economic parameters for any SAIL blast furnace — a custom month range
        (weighted average, harmonic mean, or sum, whichever the parameter uses, weighted by that
        furnace&apos;s own production during exactly that range), a single month alongside its
        April-to-that-month cumulative, or a full financial year (April-March).
      </TabIntro>

      <ErrorBox>{metaError}</ErrorBox>

      {meta && (
        <div style={{
          padding: '16px 20px', border: '1px solid #dadce0', borderRadius: '8px',
          backgroundColor: '#f8f9fa', marginBottom: '20px',
        }}>
          {/* Furnace picker, grouped by plant */}
          <div style={{ marginBottom: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
              <span style={{ fontSize: '11pt', fontWeight: 600, color: '#202124' }}>Furnaces</span>
              <button onClick={() => setSelectedFurnaces(allFurnaceKeys)} style={{ ...pillStyle(false), padding: '3px 10px', fontSize: '9pt' }}>All</button>
              <button onClick={() => setSelectedFurnaces([])} style={{ ...pillStyle(false), padding: '3px 10px', fontSize: '9pt' }}>None</button>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '18px' }}>
              {Object.entries(meta.furnaces_by_plant || {}).map(([plant, units]) => (
                <div key={plant}>
                  <div style={{ fontSize: '9.5pt', fontWeight: 700, color: '#174ea6', marginBottom: '4px' }}>{plant}</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {units.map((u) => {
                      const key = `${plant}:${u}`;
                      return (
                        <button key={key} onClick={() => toggleFurnace(key)} style={{ ...pillStyle(selectedFurnaces.includes(key)), padding: '5px 12px', fontSize: '9.5pt' }}>
                          {u}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Parameter picker */}
          <div style={{ marginBottom: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
              <span style={{ fontSize: '11pt', fontWeight: 600, color: '#202124' }}>Parameters</span>
              <button onClick={() => setSelectedParams(allParamKeys)} style={{ ...pillStyle(false), padding: '3px 10px', fontSize: '9pt' }}>All</button>
              <button onClick={() => setSelectedParams([])} style={{ ...pillStyle(false), padding: '3px 10px', fontSize: '9pt' }}>None</button>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 18px', maxHeight: '140px', overflowY: 'auto', border: '1px solid #dadce0', borderRadius: '6px', padding: '10px', backgroundColor: '#ffffff' }}>
              {(meta.params || []).map((p) => (
                <label key={p.key} style={{
                  display: 'inline-flex', alignItems: 'center', gap: '6px',
                  fontSize: '10pt', color: '#202124', cursor: 'pointer', padding: '3px 0',
                }}>
                  <input type="checkbox" checked={selectedParams.includes(p.key)} onChange={() => toggleParam(p.key)} style={{ cursor: 'pointer' }} />
                  {p.label}{p.unit ? ` (${p.unit})` : ''}
                </label>
              ))}
            </div>
          </div>

          {/* Duration mode */}
          <div style={{ marginBottom: '10px' }}>
            <div style={{ fontSize: '11pt', fontWeight: 600, color: '#202124', marginBottom: '8px' }}>Duration</div>
            <div style={{ marginBottom: '12px' }}>
              <SegmentedToggle
                options={[['range', 'Start - End Month'], ['month_till', 'Month + Till-Month'], ['annual', 'Annual (Apr-Mar)']]}
                value={mode} onChange={setMode}
              />
            </div>

            {mode === 'range' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <label style={{ fontSize: '10.5pt', fontWeight: 600 }}>From</label>
                  <select value={startMonthName} onChange={(e) => setStartMonthName(e.target.value)} style={selStyle}>
                    {MONTH_NAMES_FULL.map((m) => <option key={m}>{m}</option>)}
                  </select>
                  <select value={startYear} onChange={(e) => setStartYear(e.target.value)} style={selStyle}>
                    {YEARS.map((y) => <option key={y}>{y}</option>)}
                  </select>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <label style={{ fontSize: '10.5pt', fontWeight: 600 }}>To</label>
                  <select value={endMonthName} onChange={(e) => setEndMonthName(e.target.value)} style={selStyle}>
                    {MONTH_NAMES_FULL.map((m) => <option key={m}>{m}</option>)}
                  </select>
                  <select value={endYear} onChange={(e) => setEndYear(e.target.value)} style={selStyle}>
                    {YEARS.map((y) => <option key={y}>{y}</option>)}
                  </select>
                </div>
              </div>
            )}

            {mode === 'month_till' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <label style={{ fontSize: '10.5pt', fontWeight: 600 }}>Month</label>
                <select value={monthName} onChange={(e) => setMonthName(e.target.value)} style={selStyle}>
                  {MONTH_NAMES_FULL.map((m) => <option key={m}>{m}</option>)}
                </select>
                <select value={year} onChange={(e) => setYear(e.target.value)} style={selStyle}>
                  {YEARS.map((y) => <option key={y}>{y}</option>)}
                </select>
                <span style={{ fontSize: '9.5pt', color: '#5f6368' }}>
                  → shows this month&apos;s own figure and the Apr-to-this-month cumulative, side by side.
                </span>
              </div>
            )}

            {mode === 'annual' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <label style={{ fontSize: '10.5pt', fontWeight: 600 }}>Financial Year ending March</label>
                <select value={fyEndYear} onChange={(e) => setFyEndYear(e.target.value)} style={selStyle}>
                  {FY_END_YEARS.map((y) => <option key={y} value={y}>{y} (FY {y - 1}-{String(y % 100).padStart(2, '0')})</option>)}
                </select>
              </div>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginTop: '16px' }}>
            <button
              onClick={fetchReport}
              disabled={selectedFurnaces.length === 0 || loading}
              style={{
                padding: '9px 28px', fontSize: '11pt', fontWeight: 700, border: 'none', borderRadius: '6px',
                cursor: selectedFurnaces.length === 0 || loading ? 'not-allowed' : 'pointer',
                backgroundColor: selectedFurnaces.length === 0 || loading ? '#dadce0' : '#1a73e8',
                color: '#ffffff',
              }}
            >
              {loading ? 'Generating…' : 'Generate Report'}
            </button>
            {current && (
              <ExportButtons onDownload={handleDownload} downloading={downloading} disabled={selectedFurnaces.length === 0} />
            )}
          </div>
        </div>
      )}

      <ErrorBox>{error}</ErrorBox>

      {current && current.sections?.length > 0 && (
        <div style={{
          border: '1px solid #dadce0', borderRadius: '8px',
          overflowX: 'auto', maxHeight: 'calc(100vh - 480px)', overflowY: 'auto',
        }}>
          <table style={{ borderCollapse: 'separate', borderSpacing: 0, width: '100%' }}>
            <thead>
              <tr>
                <th style={th({ textAlign: 'left', minWidth: '120px' })}>Furnace</th>
                {current.periods.map((label) => (
                  <th key={label} style={th({ minWidth: '110px' })}>{label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {current.sections.map((sec) => (
                <React.Fragment key={sec.parameter}>
                  <tr>
                    <td colSpan={1 + current.periods.length} style={{
                      ...cell, backgroundColor: '#1a73e8', color: '#ffffff',
                      fontWeight: 800, fontSize: '11pt', letterSpacing: '0.02em',
                    }}>
                      {sec.parameter}{sec.unit ? ` (${sec.unit})` : ''}
                    </td>
                  </tr>
                  {sec.rows.map((r, i) => {
                    const zebra = i % 2 === 1 ? '#f8f9fa' : '#ffffff';
                    return (
                      <tr key={r.furnace} style={{ backgroundColor: zebra }}>
                        <td style={{ ...cell, fontWeight: 600 }}>{r.furnace}</td>
                        {current.periods.map((label) => {
                          const cd = r.values?.[label] || {};
                          const fellBack = cd.method_used === 'average' && (cd.warnings || []).length > 0;
                          const computed = cd.value != null && (cd.warnings || []).some((w) => w.startsWith('No stored cumulative'));
                          return (
                            <td key={label} style={{ ...cell, textAlign: 'right', fontWeight: 700 }}
                              title={(cd.warnings || []).length ? cd.warnings.join(' ') : undefined}>
                              {cd.display !== undefined && cd.display !== '' ? cd.display : fmtNum(cd.value)}{fellBack ? '*' : ''}{computed ? '†' : ''}
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </React.Fragment>
              ))}
            </tbody>
          </table>
          <div style={{ padding: '8px 12px', fontSize: '9pt', color: '#5f6368', borderTop: '1px solid #e8eaed' }}>
            * production-weight data was incomplete for one or more months in that range — a simple average is shown instead of the weighted/harmonic figure (hover the cell for detail).
            <br />† no stored cumulative for this furnace — computed from its monthly values instead.
          </div>
        </div>
      )}

      {current && current.sections?.length === 0 && (
        <EmptyState>No data for the selected furnaces/parameters in this period.</EmptyState>
      )}
    </div>
  );
}
