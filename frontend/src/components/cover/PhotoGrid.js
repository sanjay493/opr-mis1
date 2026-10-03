'use client';

import { apiUrl } from './coverApi';
import c from './cover.module.css';

/** Thumbnails of library photos. `compact` = the small picker in the Cover
 *  card; otherwise the full grid with name/uploader/date/usage and Remove. */
export default function PhotoGrid({ photos, selectedId, onSelect, onRemove, compact = false, uploadTile = null }) {
  return (
    <div className={`${c.grid} ${compact ? c.gridCompact : ''}`}>
      {uploadTile}
      {photos.map((p) => (
        <div key={p.id}>
          <button type="button" className={`${c.tile} ${p.id === selectedId ? c.tileActive : ''}`}
                  aria-pressed={onSelect ? p.id === selectedId : undefined} title={p.original_name}
                  onClick={onSelect ? () => onSelect(p) : undefined} disabled={!onSelect}>
            {/* eslint-disable-next-line @next/next/no-img-element -- API image, not a static asset */}
            <img src={apiUrl(p.thumb_url)} alt={p.original_name} loading="lazy" />
            {!compact && (
              <div className={c.meta}>
                <b>{p.original_name}</b>
                {p.uploaded_by} · {String(p.uploaded_at || '').slice(0, 10)}<br />
                {p.used_by ? `Used by ${p.used_by} month${p.used_by === 1 ? '' : 's'}` : 'Not used yet'}
              </div>
            )}
          </button>
          {onRemove && (
            <button type="button" className={c.remove} onClick={() => onRemove(p)}>Remove</button>
          )}
        </div>
      ))}
    </div>
  );
}
