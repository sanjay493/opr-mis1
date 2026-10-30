'use client';

import { fmtActivityDate } from './uaApi';
import wb from '@/styles/wb.module.css';
import s from './ua.module.css';

// One activity: date, plant / unit, title, paragraph, tags. onTag(tag) makes
// the tags clickable filters; actions (Edit / Delete buttons) go top-right.
export default function ActivityCard({ activity: a, onTag, actions }) {
  const edited = a.updated_at ? ` · edited ${a.updated_at}${a.updated_by ? ` by ${a.updated_by}` : ''}` : '';
  return (
    <article className={s.card}>
      <div className={s.cardHead}>
        <div style={{ minWidth: 0 }}>
          <div className={s.meta}>
            <span className={s.date}>{fmtActivityDate(a.activity_date)}</span>
            {a.plant_code && <span className={`${wb.badge} ${wb.badgeBlue}`}>{a.plant_code}</span>}
            {a.unit_name && <span className={`${wb.badge} ${wb.badgeGrey}`}>{a.unit_name}</span>}
          </div>
          <h3 className={s.title}>{a.title}</h3>
        </div>
        {actions && <div className={s.actions}>{actions}</div>}
      </div>
      <p className={s.text}>{a.description}</p>
      {a.tags.length > 0 && (
        <div className={s.tags}>
          {a.tags.map((t) => (onTag
            ? <button key={t} type="button" className={s.tag} onClick={() => onTag(t)} title={`Show all "${t}" activities`}>#{t}</button>
            : <span key={t} className={s.tag}>#{t}</span>))}
        </div>
      )}
      {(a.created_by || edited) && (
        <div className={s.byline}>Recorded {a.created_at || ''}{a.created_by ? ` by ${a.created_by}` : ''}{edited}</div>
      )}
    </article>
  );
}
