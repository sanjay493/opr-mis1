'use client';

import { useEffect, useState, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
import RequireAdmin from '@/components/RequireAdmin';
import { API_BASE_URL } from '@/providers/AuthProvider';
import ui from '@/styles/ui.module.css';

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
  const [elapsed, setElapsed] = useState(0);
  const busy = backingUp || restoringFile !== '';

  // A backup/restore shells out to mysqldump/mysql and can take a couple of
  // minutes with no other feedback — surface elapsed time so it doesn't look
  // hung, and warn before leaving so nobody navigates away thinking it froze
  // (the operation keeps running server-side either way, but the success/
  // error message would never reach anyone still on the page).
  useEffect(() => {
    if (!busy) {
      setElapsed(0);
      return;
    }
    const start = Date.now();
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => clearInterval(id);
  }, [busy]);

  useEffect(() => {
    if (!busy) return;
    const handler = (e) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [busy]);

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
      await doRestore(filename, false);
    } catch (err) {
      setError(err.message);
    } finally {
      setRestoringFile('');
    }
  };

  // confirmDataLoss=false first: the backend checks whether this file would
  // empty any table that currently has data and, if so, 409s with which
  // ones instead of silently doing it (see api_admin_backup.py's
  // _tables_at_risk — added after a restore did exactly that to
  // capital_repair_table on 2026-08-21). A second explicit confirm from the
  // operator re-sends with confirmDataLoss=true to proceed anyway.
  const doRestore = async (filename, confirmDataLoss) => {
    const url = `${API_BASE_URL}/api/admin/backups/${encodeURIComponent(filename)}/restore`
      + (confirmDataLoss ? '?confirm_data_loss=true' : '');
    const res = await fetch(url, { method: 'POST', credentials: 'include' });
    const data = await res.json();
    if (res.status === 409 && !confirmDataLoss) {
      if (confirm(`${data.detail}\n\nRestore anyway?`)) {
        await doRestore(filename, true);
        return;
      }
      throw new Error('Restore cancelled — would have emptied tables that currently have data.');
    }
    if (!res.ok) throw new Error(data.detail || 'Restore failed.');
    setNotice(`Restored from ${data.restored_from}. Pre-restore snapshot saved as ${data.prerestore_snapshot}.`);
    await load();
  };

  return (
    <>
      <GlobalNavbar />
      <main className={ui.page}>
        <div className={ui.pageHeader}>
          <h1 className={ui.pageTitle}>Database Backup &amp; Restore</h1>
          <p className={ui.pageLead}>
            Runs via the app&apos;s own database user (mis_app) — same tool the daily scheduled backup uses.
            Restoring always saves a snapshot of the current data first.
          </p>
        </div>

        <div style={{ marginBottom: 20 }}>
          <button type="button" className={`${ui.btn} ${ui.btnPrimary}`} onClick={backupNow}
                  disabled={busy} aria-busy={backingUp}>
            {backingUp ? `Backing up… (${elapsed}s)` : 'Backup Now'}
          </button>
        </div>

        {busy && (
          <p role="status" className={`${ui.alert} ${ui.alertWarning}`}>
            This can take a couple of minutes — please don&apos;t close or refresh this page.
          </p>
        )}
        {error && <p role="alert" className={`${ui.alert} ${ui.alertError}`}>{error}</p>}
        {notice && <p role="status" className={`${ui.alert} ${ui.alertSuccess}`}>{notice}</p>}

        {loading ? (
          <p className={ui.meta} aria-live="polite">Loading…</p>
        ) : (
          <div className={ui.tableWrap}>
          <table className={ui.table}>
            <thead>
              <tr>
                <th scope="col">Filename</th>
                <th scope="col" className={ui.numeric}>Size</th>
                <th scope="col">Modified (IST)</th>
                <th scope="col"><span className={ui.srOnly}>Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {backups.map((b) => (
                <tr key={b.filename}>
                  <td className={ui.mono}>{b.filename}</td>
                  <td className={`${ui.numeric} ${ui.nowrap}`}>{formatBytes(b.size_bytes)}</td>
                  <td className={`${ui.muted} ${ui.nowrap}`}>
                    {b.modified_at?.replace('T', ' ').slice(0, 19)}
                  </td>
                  <td>
                    <button
                      type="button"
                      className={`${ui.btn} ${ui.btnDanger} ${ui.btnSm}`}
                      aria-label={`Restore ${b.filename}`}
                      onClick={() => restore(b.filename)}
                      disabled={busy} aria-busy={restoringFile === b.filename}
                    >
                      {restoringFile === b.filename ? `Restoring… (${elapsed}s)` : 'Restore'}
                    </button>
                  </td>
                </tr>
              ))}
              {backups.length === 0 && (
                <tr><td colSpan={4} className={ui.emptyCell}>No backups found.</td></tr>
              )}
            </tbody>
          </table>
          </div>
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
