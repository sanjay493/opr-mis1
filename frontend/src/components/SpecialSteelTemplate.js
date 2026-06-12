'use client';

// ── shared style tokens ───────────────────────────────────────────────────────
const CELL = { padding: '1.5px 3px', border: '1px solid #cbd5e1', lineHeight: 1.2, fontSize: '0.68rem' };
const NUM  = { ...CELL, textAlign: 'right' };
const LBL  = { ...CELL, textAlign: 'left' };
const TH_S = {
  backgroundColor: '#1e3a5f', color: '#fff', padding: '2px 3px',
  textAlign: 'center', verticalAlign: 'middle',
  border: '1px solid #334155', fontSize: '0.63rem', lineHeight: 1.2, fontWeight: 600,
};
const TH_C = { ...TH_S, backgroundColor: '#2d5016' }; // darker green for cumulative header

const ROW_STYLES = {
  grade:           { backgroundColor: '#f8fafc' },
  'product-total': { backgroundColor: '#fef9c3', fontWeight: 700 },
  subtotal:        { backgroundColor: '#fed7aa', fontWeight: 700 },
  'grand-total':   { backgroundColor: '#dcfce7', fontWeight: 700 },
  plant:           { backgroundColor: '#f8fafc' },
  'sail-total':    { backgroundColor: '#dcfce7', fontWeight: 700 },
};


// ── plant_detail / isp_summary table (pages 19-23) ───────────────────────────
// 11 columns: Quality/Grade | Order | Actual | %Ful | CPLY | %Gr | CumOrd | CumAct | %Ful | CumCPLY | %Gr

function DetailRow({ row }) {
  if (row.type === 'separator') {
    return <tr style={{ height: 2 }}><td colSpan={11} style={{ border: 'none', padding: 0 }} /></tr>;
  }
  if (row.type === 'product-hdr') {
    return (
      <tr>
        <td colSpan={11} style={{
          ...LBL, backgroundColor: '#1e3a5f', color: '#fff',
          fontWeight: 700, padding: '2px 5px', border: '1px solid #334155',
        }}>
          {row.label}
        </td>
      </tr>
    );
  }
  const s = ROW_STYLES[row.type] || {};
  return (
    <tr style={s}>
      <td style={{ ...LBL, ...s, paddingLeft: row.type === 'grade' ? '10px' : '3px' }}>{row.label}</td>
      <td style={{ ...NUM, ...s }}>{row.orders}</td>
      <td style={{ ...NUM, ...s }}>{row.actual}</td>
      <td style={{ ...NUM, ...s }}>{row.pct_ful}</td>
      <td style={{ ...NUM, ...s }}>{row.cply}</td>
      <td style={{ ...NUM, ...s }}>{row.pct_growth}</td>
      <td style={{ ...NUM, ...s }}>{row.cum_orders}</td>
      <td style={{ ...NUM, ...s }}>{row.cum_actual}</td>
      <td style={{ ...NUM, ...s }}>{row.cum_pct_ful}</td>
      <td style={{ ...NUM, ...s }}>{row.cum_cply}</td>
      <td style={{ ...NUM, ...s }}>{row.cum_pct_growth}</td>
    </tr>
  );
}

function DetailTable({ data }) {
  const {
    title, unit = 'Tonnes', rows = [],
    saleable_production = {}, special_pct = {},
    month_label = '', cply_label = '',
    cum_label = '', cum_cply_label = '',
  } = data;

  return (
    <div style={{ padding: '6px', fontFamily: 'Arial, sans-serif' }}>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '0.88rem', marginBottom: 4 }}>
        {title}
      </div>
      <div style={{ textAlign: 'right', fontSize: '0.65rem', marginBottom: 3 }}>Unit: {unit}</div>

      <table style={{ width: '100%', borderCollapse: 'collapse', border: '2px solid #1e293b',
                      tableLayout: 'fixed', fontSize: '0.68rem' }}>
        <colgroup>
          <col style={{ width: '20%' }} />
          {/* Monthly */}
          <col style={{ width: '8%' }} /><col style={{ width: '8%' }} /><col style={{ width: '6%' }} />
          <col style={{ width: '6.5%' }} /><col style={{ width: '5.5%' }} />
          {/* Cumulative */}
          <col style={{ width: '8%' }} /><col style={{ width: '8%' }} /><col style={{ width: '6%' }} />
          <col style={{ width: '6.5%' }} /><col style={{ width: '5.5%' }} />
        </colgroup>
        <thead>
          <tr>
            <th rowSpan={2} style={{ ...TH_S, textAlign: 'left' }}>Quality / Grade</th>
            <th colSpan={3} style={TH_S}>{month_label}</th>
            <th rowSpan={2} style={TH_S}>{cply_label}<br/>Actual</th>
            <th rowSpan={2} style={TH_S}>%Gr<br/>{cply_label}</th>
            <th colSpan={3} style={TH_C}>{cum_label}</th>
            <th rowSpan={2} style={TH_C}>{cum_cply_label}<br/>Actual</th>
            <th rowSpan={2} style={TH_C}>%Gr<br/>{cum_cply_label}</th>
          </tr>
          <tr>
            <th style={TH_S}>Order</th>
            <th style={TH_S}>Actual</th>
            <th style={TH_S}>%Ful</th>
            <th style={TH_C}>Order</th>
            <th style={TH_C}>Actual</th>
            <th style={TH_C}>%Ful</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => <DetailRow key={i} row={row} />)}

          <tr style={{ height: 3 }}><td colSpan={11} style={{ border: 'none', padding: 0 }} /></tr>
          <tr style={{ backgroundColor: '#e0f2fe' }}>
            <td style={{ ...LBL, fontWeight: 600 }}>Saleable Steel Production</td>
            <td style={NUM} colSpan={2}>{saleable_production.current}</td>
            <td style={NUM}></td>
            <td style={NUM}>{saleable_production.cply}</td>
            <td style={NUM}></td>
            <td style={NUM} colSpan={2}>{saleable_production.cum_current}</td>
            <td style={NUM}></td>
            <td style={NUM}>{saleable_production.cum_cply}</td>
            <td style={NUM}>{saleable_production.cum_pct_growth}</td>
          </tr>
          <tr style={{ backgroundColor: '#e0f2fe' }}>
            <td style={{ ...LBL, fontWeight: 600 }}>Special Steel % of Saleable Steel</td>
            <td style={NUM} colSpan={2}>{special_pct.current}</td>
            <td style={NUM}></td>
            <td style={NUM}>{special_pct.cply}</td>
            <td style={NUM}></td>
            <td style={NUM} colSpan={2}>{special_pct.cum_current}</td>
            <td style={NUM}></td>
            <td style={NUM}>{special_pct.cum_cply}</td>
            <td style={NUM}></td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}


// ── sail_summary table (page 24) ──────────────────────────────────────────────
// 12 cols: Plants | ABP | Orders | Actual | %Ful | CPLY | %Gr | CumOrd | CumAct | %Ful | CumCPLY | %Gr

function SailRow({ row }) {
  const s = ROW_STYLES[row.type] || {};
  return (
    <tr style={s}>
      <td style={{ ...LBL, ...s, fontWeight: row.type === 'sail-total' ? 700 : 'inherit' }}>{row.label}</td>
      <td style={{ ...NUM, ...s }}>{row.abp}</td>
      <td style={{ ...NUM, ...s }}>{row.orders}</td>
      <td style={{ ...NUM, ...s }}>{row.actual}</td>
      <td style={{ ...NUM, ...s }}>{row.pct_ful}</td>
      <td style={{ ...NUM, ...s }}>{row.cply}</td>
      <td style={{ ...NUM, ...s }}>{row.pct_growth}</td>
      <td style={{ ...NUM, ...s }}>{row.cum_orders}</td>
      <td style={{ ...NUM, ...s }}>{row.cum_actual}</td>
      <td style={{ ...NUM, ...s }}>{row.cum_pct_ful}</td>
      <td style={{ ...NUM, ...s }}>{row.cum_cply}</td>
      <td style={{ ...NUM, ...s }}>{row.cum_pct_growth}</td>
    </tr>
  );
}

function SailTable({ data }) {
  const {
    title, unit = 'Tonnes', rows = [],
    saleable_production = {}, special_pct = {},
    month_label = '', cply_label = '',
    cum_label = '', cum_cply_label = '',
  } = data;

  return (
    <div style={{ padding: '6px', fontFamily: 'Arial, sans-serif' }}>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '0.88rem', marginBottom: 4 }}>
        {title}
      </div>
      <div style={{ textAlign: 'center', fontWeight: 600, fontSize: '0.75rem', marginBottom: 4 }}>
        {month_label}
      </div>
      <div style={{ textAlign: 'right', fontSize: '0.65rem', marginBottom: 3 }}>Unit: Tonnes</div>

      <table style={{ width: '100%', borderCollapse: 'collapse', border: '2px solid #1e293b',
                      tableLayout: 'fixed', fontSize: '0.68rem' }}>
        <colgroup>
          <col style={{ width: '13%' }} />
          <col style={{ width: '8%' }} />
          {/* Monthly */}
          <col style={{ width: '7%' }} /><col style={{ width: '7%' }} /><col style={{ width: '5.5%' }} />
          <col style={{ width: '6%' }} /><col style={{ width: '5%' }} />
          {/* Cumulative */}
          <col style={{ width: '7%' }} /><col style={{ width: '7%' }} /><col style={{ width: '5.5%' }} />
          <col style={{ width: '6%' }} /><col style={{ width: '5%' }} />
        </colgroup>
        <thead>
          <tr>
            <th rowSpan={2} style={{ ...TH_S, textAlign: 'left' }}>Plants</th>
            <th rowSpan={2} style={TH_S}>ABP<br/>26-27</th>
            <th colSpan={3} style={TH_S}>{month_label}</th>
            <th rowSpan={2} style={TH_S}>{cply_label}<br/>Actual</th>
            <th rowSpan={2} style={TH_S}>%Gr<br/>{cply_label}</th>
            <th colSpan={3} style={TH_C}>{cum_label}</th>
            <th rowSpan={2} style={TH_C}>{cum_cply_label}<br/>Actual</th>
            <th rowSpan={2} style={TH_C}>%Gr<br/>{cum_cply_label}</th>
          </tr>
          <tr>
            <th style={TH_S}>Orders</th>
            <th style={TH_S}>Actual</th>
            <th style={TH_S}>%Ful</th>
            <th style={TH_C}>Orders</th>
            <th style={TH_C}>Actual</th>
            <th style={TH_C}>%Ful</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => <SailRow key={i} row={row} />)}

          <tr style={{ height: 3 }}><td colSpan={12} style={{ border: 'none', padding: 0 }} /></tr>
          <tr style={{ backgroundColor: '#e0f2fe' }}>
            <td style={{ ...LBL, fontWeight: 600 }}>Saleable Steel production</td>
            <td style={NUM}>{saleable_production.abp}</td>
            <td style={NUM}></td>
            <td style={NUM}>{saleable_production.current}</td>
            <td style={NUM}></td>
            <td style={NUM}>{saleable_production.cply}</td>
            <td style={NUM}>{saleable_production.pct_growth}</td>
            <td style={NUM}></td>
            <td style={NUM}>{saleable_production.cum_current}</td>
            <td style={NUM}></td>
            <td style={NUM}>{saleable_production.cum_cply}</td>
            <td style={NUM}>{saleable_production.cum_pct_growth}</td>
          </tr>
          <tr style={{ backgroundColor: '#e0f2fe' }}>
            <td style={{ ...LBL, fontWeight: 600 }}>Special Steel % of Saleable Steel</td>
            <td style={NUM}></td>
            <td style={NUM}></td>
            <td style={NUM}>{special_pct.current}</td>
            <td style={NUM}></td>
            <td style={NUM}>{special_pct.cply}</td>
            <td style={NUM}></td>
            <td style={NUM}></td>
            <td style={NUM}>{special_pct.cum_current}</td>
            <td style={NUM}></td>
            <td style={NUM}>{special_pct.cum_cply}</td>
            <td style={NUM}></td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}


// ── default export ────────────────────────────────────────────────────────────

export default function SpecialSteelTemplate({ data }) {
  if (!data) return null;
  if (data.variant === 'sail_summary') return <SailTable data={data} />;
  return <DetailTable data={data} />;
}
