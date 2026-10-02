'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import GlobalNavbar from '@/components/GlobalNavbar';
import { useAuth, API_BASE_URL } from '@/providers/AuthProvider';
import { Icon, ICONS, authStyles as s } from '@/components/auth/AuthUI';

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
  const [showPw, setShowPw] = useState(false);
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
    const id = setTimeout(() => setResendIn((n) => n - 1), 1000);
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
      <main className={s.shell}>
        <div className={s.column}>
          <div className={s.card}>
            {step === 'password' ? (
              <>
                <div className={s.head}>
                  <div className={s.emblem}><Icon d={ICONS.bank} size={26} /></div>
                  <h1 className={s.title}>Sign In to Operations Portal</h1>
                  <p className={s.lead}>
                    SAIL Operations Monthly Informatics — Corporate Office, Integrated Steel Plants
                    (<b>BSP, DSP, RSP, BSL, ISP</b>) and Units
                  </p>
                </div>

                <form className={s.form} onSubmit={handlePassword}>
                  <div>
                    <label htmlFor="login-email" className={s.label}>Email</label>
                    <div className={s.inputWrap}>
                      <span className={s.inputIcon}><Icon d={ICONS.mail} /></span>
                      <input
                        id="login-email" type="email" className={s.input} required
                        placeholder="name@sail.in"
                        value={email} onChange={(e) => setEmail(e.target.value)}
                        autoComplete="username"
                      />
                    </div>
                  </div>
                  <div>
                    <label htmlFor="login-password" className={s.label}>Password</label>
                    <div className={s.inputWrap}>
                      <span className={s.inputIcon}><Icon d={ICONS.lock} /></span>
                      <input
                        id="login-password" type={showPw ? 'text' : 'password'}
                        className={`${s.input} ${s.inputPw}`} required
                        placeholder="Enter your portal password"
                        value={password} onChange={(e) => setPassword(e.target.value)}
                        autoComplete="current-password"
                      />
                      <button type="button" className={s.eye} onClick={() => setShowPw((v) => !v)}
                              aria-label={showPw ? 'Hide password' : 'Show password'}
                              title={showPw ? 'Hide password' : 'Show password'}>
                        <Icon d={showPw ? ICONS.eyeOff : ICONS.eye} size={19} />
                      </button>
                    </div>
                  </div>
                  <div className={s.row}>
                    <Link href="/forgot-password" className={s.link}>Forgot password?</Link>
                  </div>

                  {error && <p role="alert" className={`${s.alert} ${s.alertError}`}>{error}</p>}

                  <button type="submit" className={`${s.btn} ${s.btnPrimary}`}
                          disabled={submitting} aria-busy={submitting}>
                    {submitting ? 'Checking…' : <>Sign In <Icon d={ICONS.arrow} /></>}
                  </button>
                </form>

                <div className={s.foot}>
                  Need access or first-time registration?
                  <Link href="/register" className={s.link}>Register a new account</Link>
                </div>
              </>
            ) : (
              <>
                <div className={s.head}>
                  <div className={s.emblem}><Icon d={ICONS.mail} size={24} /></div>
                  <h1 className={s.title}>Check your email</h1>
                  <p className={s.lead}>Step 2 of 2 — enter the code sent to <b>{sentTo}</b>.</p>
                </div>

                <form className={s.form} onSubmit={handleCode}>
                  {info && <p role="status" className={`${s.alert} ${s.alertInfo}`}>{info}</p>}
                  <div>
                    <label htmlFor="login-code" className={s.label}>Sign-in code</label>
                    <input
                      id="login-code" ref={codeInputRef} className={`${s.input} ${s.inputCode}`} required
                      type="text" inputMode="numeric" pattern="[0-9]{6}" maxLength={6}
                      autoComplete="one-time-code" placeholder="123456"
                      value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
                    />
                  </div>

                  {error && <p role="alert" className={`${s.alert} ${s.alertError}`}>{error}</p>}

                  <div className={s.btnGroup}>
                    <button type="submit" className={`${s.btn} ${s.btnPrimary}`}
                            disabled={submitting || code.length !== 6} aria-busy={submitting}>
                      {submitting ? 'Verifying…' : <>Verify &amp; Sign In <Icon d={ICONS.arrow} /></>}
                    </button>
                    <button type="button" className={`${s.btn} ${s.btnSecondary}`}
                            onClick={handleResend} disabled={resendIn > 0}>
                      {resendIn > 0 ? `Resend code in ${resendIn}s` : 'Resend code'}
                    </button>
                  </div>
                </form>

                <div className={s.foot}>
                  Wrong account?
                  <button type="button" className={`${s.link} ${s.textBtn}`} onClick={() => backToPassword()}>
                    Use a different account
                  </button>
                </div>
              </>
            )}
          </div>

          <div className={s.notice}>
            <Icon d={ICONS.policy} />
            <div>
              <b>Authorized use only.</b> This system is restricted to authorized Steel Authority of India
              Limited personnel.
            </div>
          </div>
        </div>
      </main>
    </>
  );
}
