'use client';

import { useEffect, useRef, useState } from 'react';
import s from '@/app/report/report.module.css';
import PhotoGrid from './PhotoGrid';
import { apiUrl, coverApi } from './coverApi';
import c from './cover.module.css';

const pickRandom = (photos, notId) => {
  const pool = photos.filter((p) => p.id !== notId);
  const from = pool.length ? pool : photos;
  return from.length ? from[Math.floor(Math.random() * from.length)].id : null;
};

const sameChoice = (a, b) =>
  a && b && a.design === b.design &&
  (a.design === 'classic' || (a.photo_mode === b.photo_mode && a.photo_id === b.photo_id));

/**
 * Report Engine sidebar card: pick the month's cover design and photo.
 * Changes preview immediately (onPreview); "Save cover" stores them and the
 * PDF export always uses the saved choice. Shuffle saves straight away.
 */
export default function CoverCard({ month, canEdit, onPreview }) {
  const [designs, setDesigns] = useState([]);
  const [photos, setPhotos] = useState([]);
  const [saved, setSaved] = useState(null);
  const [draft, setDraft] = useState(null);
  const [picker, setPicker] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const fileRef = useRef(null);

  useEffect(() => {
    let alive = true;
    Promise.all([coverApi.designs(), coverApi.settings(month), coverApi.photos()])
      .then(([d, st, ph]) => {
        if (!alive) return;
        setDesigns(d);
        setPhotos(ph);
        setSaved(st);
        setDraft({ design: st.design, photo_mode: st.photo_mode, photo_id: st.photo_id });
        setPicker(false);
        setError(null);
      })
      .catch((e) => alive && setError(e.message));
    return () => { alive = false; };
  }, [month]);

  const show = (next) => {
    setDraft(next);
    onPreview({ design: next.design, photo_id: next.photo_id, report_month: month });
  };

  const choose = (patch) => {
    const next = { ...draft, ...patch };
    if (next.design !== 'classic' && next.photo_mode === 'random' && next.photo_id == null) {
      next.photo_id = pickRandom(photos, null);
    }
    show(next);
  };

  const applySaved = (st) => {
    setSaved(st);
    show({ design: st.design, photo_mode: st.photo_mode, photo_id: st.photo_id });
  };

  const run = async (fn) => {
    setBusy(true);
    setError(null);
    try { await fn(); } catch (e) { setError(e.message); } finally { setBusy(false); }
  };

  const save = () => run(async () => applySaved(await coverApi.save({ month, ...draft })));
  const shuffle = () => run(async () => applySaved(await coverApi.shuffle(month, draft.design)));
  const upload = (files) => run(async () => {
    const res = await coverApi.upload(files);
    setPhotos(await coverApi.photos());
    if (res.created.length) choose({ photo_mode: 'library', photo_id: res.created[0].id });
    if (res.errors.length) setError(res.errors.map((x) => `${x.name}: ${x.detail}`).join('; '));
  });

  if (!draft) {
    return (
      <section className={s.card}>
        <div className={s.cardHead}><h2 className={s.cardTitle}>Cover</h2></div>
        {error ? <div className={c.error}>{error}</div> : <div className={c.current}>Loading…</div>}
      </section>
    );
  }

  const label = designs.find((d) => d.id === draft.design)?.label || draft.design;
  const shownPhoto = photos.find((p) => p.id === draft.photo_id);
  const dirty = canEdit && !sameChoice(draft, saved);

  return (
    <section className={s.card}>
      <div className={s.cardHead}>
        <h2 className={s.cardTitle}>Cover</h2>
        <span className={s.count}>{label}</span>
      </div>

      <div className={c.designs} role="group" aria-label="Cover design">
        {designs.map((d) => (
          <button key={d.id} type="button" disabled={!canEdit}
                  className={`${c.design} ${d.id === draft.design ? c.designActive : ''}`}
                  aria-pressed={d.id === draft.design} onClick={() => choose({ design: d.id })}>
            {/* eslint-disable-next-line @next/next/no-img-element -- small static thumbnail */}
            <img src={d.thumb_url} alt="" />
            <span>{d.label}</span>
          </button>
        ))}
      </div>

      {draft.design !== 'classic' && (
        <>
          {canEdit && (
            <div className={s.seg} role="group" aria-label="Cover photo">
              {[['random', 'Random'], ['library', 'Choose from library']].map(([mode, text]) => (
                <button key={mode} type="button"
                        className={`${s.segBtn} ${draft.photo_mode === mode ? s.segActive : ''}`}
                        aria-pressed={draft.photo_mode === mode}
                        onClick={() => { choose({ photo_mode: mode }); setPicker(mode === 'library'); }}>
                  {text}
                </button>
              ))}
            </div>
          )}

          <div className={c.current}>
            {shownPhoto ? (
              <>
                {/* eslint-disable-next-line @next/next/no-img-element -- API image */}
                <img src={apiUrl(shownPhoto.thumb_url)} alt="" />
                <span>{shownPhoto.original_name}</span>
              </>
            ) : photos.length === 0 ? (
              <span>
                The photo library is empty, so the cover uses the built-in photo.{' '}
                <a href="/data-entry/reference?tab=cover-photos">Add photos</a>
              </span>
            ) : (
              <span>No photo chosen yet.</span>
            )}
          </div>

          {canEdit && draft.photo_mode === 'random' && photos.length > 1 && (
            <div className={s.row}>
              <button type="button" className={s.btn} onClick={shuffle} disabled={busy}
                      title="Pick and save another random photo for this month">🔀 Shuffle</button>
            </div>
          )}

          {canEdit && draft.photo_mode === 'library' && (
            <>
              {!picker && (
                <button type="button" className={s.linkBtn} onClick={() => setPicker(true)}>Change photo…</button>
              )}
              {picker && (
                <PhotoGrid compact photos={photos} selectedId={draft.photo_id}
                           onSelect={(p) => choose({ photo_id: p.id })}
                           uploadTile={(
                             <button type="button" className={c.uploadTile} onClick={() => fileRef.current?.click()} disabled={busy}>
                               + Upload new photo
                             </button>
                           )} />
              )}
              <input ref={fileRef} type="file" accept="image/jpeg,image/png" multiple hidden
                     onChange={(e) => { const f = [...e.target.files]; e.target.value = ''; if (f.length) upload(f); }} />
            </>
          )}
        </>
      )}

      {canEdit && (
        <div className={s.row} style={{ marginTop: 8 }}>
          <button type="button" className={s.btn} onClick={save} disabled={busy || !dirty}>
            {busy ? 'Saving…' : 'Save cover'}
          </button>
        </div>
      )}
      {dirty && <div className={c.note}>Not saved. The PDF uses the saved cover.</div>}
      {error && <div className={c.error}>{error}</div>}
    </section>
  );
}
