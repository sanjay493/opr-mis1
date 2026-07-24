'use client';

import { useEffect, useState, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
import RequireAdmin from '@/components/RequireAdmin';
import { API_BASE_URL } from '@/providers/AuthProvider';

function formatBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function BackupRestoreInner() {
  const [backups, setBackups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [backingUp, setBackingUp] = useState(false);
  const [restoringFile, setRestoringFile] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/backups`, { credentials: 'include' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not load backups.');
      setBackups(data.backups);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const backupNow = async () => {
    setError('');
    setNotice('');
    setBackingUp(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/backups`, {
        method: 'POST',
        credentials: 'include',
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Backup failed.');
      setNotice(`Backup created: ${data.filename}`);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBackingUp(false);
    }
  };

  const restore = async (filename) => {
    if (!confirm(
      `Restore "${filename}"?\n\nThis REPLACES ALL current data in mis_reports with what's in this file. ` +
      `A safety snapshot of the current data is taken automatically first, but anything entered after ` +
      `that snapshot and not in this backup will be gone until someone restores it back.\n\n` +
      `This cannot be undone from this page — proceed?`
    )) return;
    const typed = prompt(`To confirm, type the filename exactly:\n${filename}`);
    if (typed !== filename) {
      if (typed !== null) alert('Filename did not match — restore cancelled.');
      return;
    }

    setError('');
    setNotice('');
    setRestoringFile(filename);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/backups/${encodeURIComponent(filename)}/restore`, {
        method: 'POST',
        credentials: 'include',
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Restore failed.');
      setNotice(`Restored from ${data.restored_from}. Pre-restore snapshot saved as ${data.prerestore_snapshot}.`);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setRestoringFile('');
    }
  };

  return (
    <>
      <GlobalNavbar />
      <main style={{ maxWidth: '900px', margin: '40px auto', padding: '0 20px' }}>
        <h1 style={{ fontSize: '20pt', marginBottom: '4px' }}>Database Backup & Restore</h1>
        <p style={{ color: '#5f6368', marginBottom: '24px' }}>
          Runs via the app&apos;s own database user (mis_app) — same tool the daily scheduled backup uses.
          Restoring always saves a snapshot of the current data first.
        </p>

        <button className="btn btn-primary" onClick={backupNow} disabled={backingUp} style={{ marginBottom: '20px' }}>
          {backingUp ? 'Backing up…' : 'Backup Now'}
        </button>

        {error && <p style={{ color: '#d93025', marginBottom: '12px' }}>{error}</p>}
        {notice && <p style={{ color: '#188038', marginBottom: '12px' }}>{notice}</p>}

        {loading ? (
          <p>Loading…</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ textAlign: 'left', borderBottom: '2px solid #dadce0' }}>
                <th style={{ padding: '8px' }}>Filename</th>
                <th style={{ padding: '8px' }}>Size</th>
                <th style={{ padding: '8px' }}>Modified</th>
                <th style={{ padding: '8px' }}></th>
              </tr>
            </thead>
            <tbody>
              {backups.map((b) => (
                <tr key={b.filename} style={{ borderBottom: '1px solid #e8eaed' }}>
                  <td style={{ padding: '8px', fontFamily: 'monospace', fontSize: '9.5pt' }}>{b.filename}</td>
                  <td style={{ padding: '8px' }}>{formatBytes(b.size_bytes)}</td>
                  <td style={{ padding: '8px', fontSize: '9.5pt', color: '#5f6368' }}>
                    {b.modified_at?.replace('T', ' ').slice(0, 19)}
                  </td>
                  <td style={{ padding: '8px' }}>
                    <button
                      className="btn btn-secondary"
                      style={{ color: '#c5221f', borderColor: '#c5221f' }}
                      onClick={() => restore(b.filename)}
                      disabled={restoringFile !== ''}
                    >
                      {restoringFile === b.filename ? 'Restoring…' : 'Restore'}
                    </button>
                  </td>
                </tr>
              ))}
              {backups.length === 0 && (
                <tr><td colSpan={4} style={{ padding: '20px', textAlign: 'center', color: '#5f6368' }}>No backups found.</td></tr>
              )}
            </tbody>
          </table>
        )}
      </main>
    </>
  );
}

export default function BackupRestorePage() {
  return (
    <RequireAdmin>
      <BackupRestoreInner />
    </RequireAdmin>
  );
}
