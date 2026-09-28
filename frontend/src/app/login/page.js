'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import GlobalNavbar from '@/components/GlobalNavbar';
import { useAuth, API_BASE_URL } from '@/providers/AuthProvider';
import ui from '@/styles/ui.module.css';

async function postJson(path, body) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  return { res, data };
}

export default function LoginPage() {
  const router = useRouter();
  const { refresh } = useAuth();
  // step 'password' → 'code' (two-step login: a 6-digit code is emailed after
  // the password check; the backend may skip it when LOGIN_2FA=off).
  const [step, setStep] = useState('password');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [challenge, setChallenge] = useState('');
  const [sentTo, setSentTo] = useState('');
  const [code, setCode] = useState('');
  const [resendIn, setResendIn] = useState(0);
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const codeInputRef = useRef(null);

  useEffect(() => {
    if (resendIn <= 0) return;
    const id = setTimeout(() => setResendIn((s) => s - 1), 1000);
    return () => clearTimeout(id);
  }, [resendIn]);

  useEffect(() => {
    if (step === 'code') codeInputRef.current?.focus();
  }, [step]);

  const finish = async () => {
    await refresh();
    router.push('/');
  };

  const handlePassword = async (e) => {
    e.preventDefault();
    setError('');
    setInfo('');
    setSubmitting(true);
    try {
      const { res, data } = await postJson('/api/auth/login', { email, password });
      if (!res.ok) throw new Error(data.detail || 'Login failed.');
      if (data.status === 'code_required') {
        setChallenge(data.challenge);
        setSentTo(data.sent_to);
        setResendIn(data.resend_after_seconds || 0);
        setCode('');
        setInfo(`We emailed a 6-digit sign-in code to ${data.sent_to}. It expires in ${data.expires_in_minutes} minutes.`);
        setStep('code');
        return;
      }
      await finish();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleCode = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const { res, data } = await postJson('/api/auth/login/verify', { challenge, code });
      if (res.status === 401) {
        // Challenge expired — the password step has to be redone.
        backToPassword(data.detail);
        return;
      }
      if (!res.ok) throw new Error(data.detail || 'Verification failed.');
      await finish();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleResend = async () => {
    setError('');
    setInfo('');
    try {
      const { res, data } = await postJson('/api/auth/login/resend', { challenge });
      if (res.status === 401) {
        backToPassword(data.detail);
        return;
      }
      if (!res.ok) throw new Error(data.detail || 'Could not resend the code.');
      setResendIn(data.resend_after_seconds || 60);
      setCode('');
      setInfo(`A new code was sent to ${data.sent_to}. Earlier codes no longer work.`);
      codeInputRef.current?.focus();
    } catch (err) {
      setError(err.message);
    }
  };

  const backToPassword = (message = '') => {
    setStep('password');
    setChallenge('');
    setCode('');
    setPassword('');
    setInfo('');
    setError(message);
  };

  return (
    <>
      <GlobalNavbar />
      <main className={ui.authShell}>
        <div className={ui.authCard}>
          {step === 'password' ? (
            <>
              <div className={ui.pageHeader}>
                <h1 className={ui.pageTitle}>Log In</h1>
                <p className={ui.pageLead}>SAIL MIS Portal</p>
              </div>

              <form onSubmit={handlePassword}>
                <div className={ui.field}>
                  <label htmlFor="login-email" className={ui.label}>Email</label>
                  <input
                    id="login-email" type="email" className="form-control" required
                    value={email} onChange={(e) => setEmail(e.target.value)}
                    autoComplete="username"
                  />
                </div>
                <div className={ui.field}>
                  <label htmlFor="login-password" className={ui.label}>Password</label>
                  <input
                    id="login-password" type="password" className="form-control" required
                    value={password} onChange={(e) => setPassword(e.target.value)}
                    autoComplete="current-password"
                  />
                </div>

                {error && <p role="alert" className={`${ui.alert} ${ui.alertError}`}>{error}</p>}

                <button type="submit" className={`${ui.btn} ${ui.btnPrimary} ${ui.btnBlock}`}
                        disabled={submitting} aria-busy={submitting}>
                  {submitting ? 'Checking…' : 'Continue'}
                </button>
              </form>

              <div className={`${ui.cardFooter} ${ui.linkRow}`}>
                <Link href="/register">Register a new account</Link>
                <Link href="/forgot-password">Forgot password?</Link>
              </div>
            </>
          ) : (
            <>
              <div className={ui.pageHeader}>
                <h1 className={ui.pageTitle}>Check your email</h1>
                <p className={ui.pageLead}>Step 2 of 2 — enter the code sent to {sentTo}.</p>
              </div>

              <form onSubmit={handleCode}>
                {info && <p role="status" className={`${ui.alert} ${ui.alertSuccess}`}>{info}</p>}
                <div className={ui.field}>
                  <label htmlFor="login-code" className={ui.label}>Sign-in code</label>
                  <input
                    id="login-code" ref={codeInputRef} className="form-control" required
                    type="text" inputMode="numeric" pattern="[0-9]{6}" maxLength={6}
                    autoComplete="one-time-code" placeholder="123456"
                    value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
                    style={{ fontSize: 20, letterSpacing: '0.35em', textAlign: 'center' }}
                  />
                </div>

                {error && <p role="alert" className={`${ui.alert} ${ui.alertError}`}>{error}</p>}

                <div className={ui.actions} style={{ flexDirection: 'column' }}>
                  <button type="submit" className={`${ui.btn} ${ui.btnPrimary} ${ui.btnBlock}`}
                          disabled={submitting || code.length !== 6} aria-busy={submitting}>
                    {submitting ? 'Verifying…' : 'Verify & Log In'}
                  </button>
                  <button type="button" className={`${ui.btn} ${ui.btnSecondary} ${ui.btnBlock}`}
                          onClick={handleResend} disabled={resendIn > 0}>
                    {resendIn > 0 ? `Resend code in ${resendIn}s` : 'Resend code'}
                  </button>
                </div>
              </form>

              <div className={ui.cardFooter}>
                <button type="button" className={`${ui.btn} ${ui.btnSecondary} ${ui.btnSm}`}
                        onClick={() => backToPassword()}>
                  Use a different account
                </button>
              </div>
            </>
          )}
        </div>
      </main>
    </>
  );
}
