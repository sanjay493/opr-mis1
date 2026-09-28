'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import GlobalNavbar from '@/components/GlobalNavbar';
import { API_BASE_URL } from '@/providers/AuthProvider';
import ui from '@/styles/ui.module.css';

export default function ForgotPasswordPage() {
  const router = useRouter();
  const [step, setStep] = useState('email');
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const requestOtp = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/auth/password/request-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not send passcode.');
      setInfo(`A 6-digit passcode was sent to ${email}. It expires in 10 minutes.`);
      setStep('verify');
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const resetPassword = async (e) => {
    e.preventDefault();
    setError('');
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/auth/password/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, otp, new_password: newPassword }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not reset password.');
      router.push('/login');
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <GlobalNavbar />
      <main className={ui.authShell}>
        <div className={ui.authCard}>
          <div className={ui.pageHeader}>
            <h1 className={ui.pageTitle}>Reset Password</h1>
            <p className={ui.pageLead}>
              Every password change is verified by a passcode emailed to your account.
            </p>
          </div>

          {step === 'email' ? (
            <form onSubmit={requestOtp}>
              <div className={ui.field}>
                <label htmlFor="reset-email" className={ui.label}>Email</label>
                <input
                  id="reset-email" type="email" className="form-control" required
                  value={email} onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                />
              </div>
              {error && <p role="alert" className={`${ui.alert} ${ui.alertError}`}>{error}</p>}
              <button type="submit" className={`${ui.btn} ${ui.btnPrimary} ${ui.btnBlock}`}
                      disabled={submitting} aria-busy={submitting}>
                {submitting ? 'Sending…' : 'Send Passcode'}
              </button>
            </form>
          ) : (
            <form onSubmit={resetPassword}>
              {info && <p role="status" className={`${ui.alert} ${ui.alertSuccess}`}>{info}</p>}
              <div className={ui.field}>
                <label htmlFor="reset-otp" className={ui.label}>Passcode</label>
                <input
                  id="reset-otp" type="text" inputMode="numeric" maxLength={6} className="form-control" required
                  value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
                  autoComplete="one-time-code"
                />
              </div>
              <div className={ui.field}>
                <label htmlFor="reset-password" className={ui.label}>New password</label>
                <input
                  id="reset-password" type="password" className="form-control" required minLength={8}
                  value={newPassword} onChange={(e) => setNewPassword(e.target.value)}
                  autoComplete="new-password" aria-describedby="reset-password-hint"
                />
                <p id="reset-password-hint" className={ui.hint}>At least 8 characters.</p>
              </div>
              <div className={ui.field}>
                <label htmlFor="reset-confirm" className={ui.label}>Confirm new password</label>
                <input
                  id="reset-confirm" type="password" className="form-control" required minLength={8}
                  value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
                  autoComplete="new-password"
                />
              </div>
              {error && <p role="alert" className={`${ui.alert} ${ui.alertError}`}>{error}</p>}
              <div className={ui.actions} style={{ flexDirection: 'column' }}>
                <button type="submit" className={`${ui.btn} ${ui.btnPrimary} ${ui.btnBlock}`}
                        disabled={submitting} aria-busy={submitting}>
                  {submitting ? 'Resetting…' : 'Reset Password'}
                </button>
                <button type="button" className={`${ui.btn} ${ui.btnSecondary} ${ui.btnBlock}`}
                        onClick={() => setStep('email')}>
                  Back
                </button>
              </div>
            </form>
          )}

          <div className={ui.cardFooter}>
            <Link href="/login">Back to login</Link>
          </div>
        </div>
      </main>
    </>
  );
}
