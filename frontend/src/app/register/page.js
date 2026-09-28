'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import GlobalNavbar from '@/components/GlobalNavbar';
import { useAuth, API_BASE_URL } from '@/providers/AuthProvider';
import ui from '@/styles/ui.module.css';

export default function RegisterPage() {
  const router = useRouter();
  const { refresh } = useAuth();
  const [step, setStep] = useState('email'); // 'email' | 'verify'
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const requestOtp = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/auth/register/request-otp`, {
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

  const completeRegistration = async (e) => {
    e.preventDefault();
    setError('');
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/auth/register/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, otp, name, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Registration failed.');
      await refresh();
      router.push('/');
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
            <h1 className={ui.pageTitle}>Register</h1>
            <p className={ui.pageLead}>
              Your email must be pre-approved by an administrator. A new account starts
              with view-only access until an administrator assigns you a role.
            </p>
          </div>

          {step === 'email' ? (
            <form onSubmit={requestOtp}>
              <div className={ui.field}>
                <label htmlFor="register-email" className={ui.label}>Email</label>
                <input
                  id="register-email" type="email" className="form-control" required
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
            <form onSubmit={completeRegistration}>
              {info && <p role="status" className={`${ui.alert} ${ui.alertSuccess}`}>{info}</p>}
              <div className={ui.field}>
                <label htmlFor="register-otp" className={ui.label}>Passcode</label>
                <input
                  id="register-otp" type="text" inputMode="numeric" maxLength={6} className="form-control" required
                  value={otp} onChange={(e) => setOtp(e.target.value)}
                  autoComplete="one-time-code"
                />
              </div>
              <div className={ui.field}>
                <label htmlFor="register-name" className={ui.label}>Your name</label>
                <input
                  id="register-name" type="text" className="form-control"
                  value={name} onChange={(e) => setName(e.target.value)}
                  autoComplete="name"
                />
              </div>
              <div className={ui.field}>
                <label htmlFor="register-password" className={ui.label}>Password</label>
                <input
                  id="register-password" type="password" className="form-control" required minLength={8}
                  value={password} onChange={(e) => setPassword(e.target.value)}
                  autoComplete="new-password" aria-describedby="register-password-hint"
                />
                <p id="register-password-hint" className={ui.hint}>At least 8 characters.</p>
              </div>
              <div className={ui.field}>
                <label htmlFor="register-confirm" className={ui.label}>Confirm password</label>
                <input
                  id="register-confirm" type="password" className="form-control" required minLength={8}
                  value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
                  autoComplete="new-password"
                />
              </div>
              {error && <p role="alert" className={`${ui.alert} ${ui.alertError}`}>{error}</p>}
              <div className={ui.actions} style={{ flexDirection: 'column' }}>
                <button type="submit" className={`${ui.btn} ${ui.btnPrimary} ${ui.btnBlock}`}
                        disabled={submitting} aria-busy={submitting}>
                  {submitting ? 'Creating account…' : 'Create Account'}
                </button>
                <button type="button" className={`${ui.btn} ${ui.btnSecondary} ${ui.btnBlock}`}
                        onClick={() => setStep('email')}>
                  Back
                </button>
              </div>
            </form>
          )}

          <div className={ui.cardFooter}>
            <Link href="/login">Already have an account? Log in</Link>
          </div>
        </div>
      </main>
    </>
  );
}
