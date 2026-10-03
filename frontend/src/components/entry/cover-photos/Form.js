'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import RequireEditor from '@/components/RequireEditor';
import PhotoGrid from '@/components/cover/PhotoGrid';
import { coverApi } from '@/components/cover/coverApi';
import { EntryPage, Section, Status, Loading, wb } from '../EntryUI';

function CoverPhotosInner() {
  const [photos, setPhotos] = useState(null);
  const [status, setStatus] = useState(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);

  const load = useCallback(() => (
    coverApi.photos().then(setPhotos).catch((e) => setStatus({ type: 'error', text: e.message }))
  ), []);

  useEffect(() => { load(); }, [load]);

  const upload = async (files) => {
    setUploading(true);
    setStatus(null);
    try {
      const res = await coverApi.upload(files);
      const bad = res.errors.map((x) => `${x.name}: ${x.detail}`).join('; ');
      setStatus(bad
        ? { type: 'error', text: `Added ${res.created.length}. Not added: ${bad}` }
        : { type: 'success', text: `Added ${res.created.length} photo${res.created.length === 1 ? '' : 's'}.` });
    } catch (e) {
      setStatus({ type: 'error', text: e.message });
    } finally {
      setUploading(false);
      load();
    }
  };

  const remove = async (p) => {
    if (p.used_by > 0 && !window.confirm(
      `"${p.original_name}" is the cover photo of ${p.used_by} month${p.used_by === 1 ? '' : 's'}. ` +
      'Those months keep it; it just leaves the library. Remove it?')) return;
    try {
      await coverApi.remove(p.id);
      setStatus({ type: 'success', text: `Removed "${p.original_name}".` });
    } catch (e) {
      setStatus({ type: 'error', text: e.message });
    }
    load();
  };

  return (
    <EntryPage
      title="Cover Photos"
      description="Photos for the report cover designs. The Cover card on the Report page picks one per month, or one at random. JPEG or PNG, up to 10 MB each; large photos are resized automatically."
    >
      <Status status={status} />
      <Section
        title="Library"
        sub={photos ? `${photos.length} photo${photos.length === 1 ? '' : 's'}` : ''}
        actions={(
          <>
            <button type="button" className={`${wb.btn} ${wb.btnPrimary}`} disabled={uploading}
                    onClick={() => fileRef.current?.click()}>
              {uploading ? 'Uploading…' : '⬆ Upload photos'}
            </button>
            <input ref={fileRef} type="file" accept="image/jpeg,image/png" multiple hidden
                   onChange={(e) => { const f = [...e.target.files]; e.target.value = ''; if (f.length) upload(f); }} />
          </>
        )}
        flush={false}
      >
        {photos === null ? <Loading /> : photos.length === 0 ? (
          <div className={wb.empty}>No photos yet. Upload plant photos to use them on report covers.</div>
        ) : (
          <PhotoGrid photos={photos} onRemove={remove} />
        )}
      </Section>
    </EntryPage>
  );
}

export default function CoverPhotosForm() {
  return (
    <RequireEditor>
      <CoverPhotosInner />
    </RequireEditor>
  );
}
