'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth, API_BASE_URL } from '@/providers/AuthProvider';
import { AuthPage, IconField, PasswordField, Alert, Icon, ICONS, authStyles as s } from '@/components/auth/AuthUI';

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
    <AuthPage
      icon={ICONS.personAdd}
      title={step === 'email' ? 'Register for Operations Portal' : 'Complete your registration'}
      lead={step === 'email'
        ? <>Your email must be pre-approved by an administrator. A new account starts with
            view-only access until an administrator assigns you a role.</>
        : <>Step 2 of 2 — enter the passcode sent to <b>{email}</b> and choose a password.</>}
      footer={<>Already have an account?<Link href="/login" className={s.link}>Sign in</Link></>}
    >
      {step === 'email' ? (
        <form className={s.form} onSubmit={requestOtp}>
          <IconField id="register-email" label="Email" icon={ICONS.mail} type="email" required
                     placeholder="name@sail.in" autoComplete="email"
                     value={email} onChange={(e) => setEmail(e.target.value)} />
          <Alert>{error}</Alert>
          <button type="submit" className={`${s.btn} ${s.btnPrimary}`} disabled={submitting} aria-busy={submitting}>
            {submitting ? 'Sending…' : <>Send Passcode <Icon d={ICONS.arrow} /></>}
          </button>
        </form>
      ) : (
        <form className={s.form} onSubmit={completeRegistration}>
          <Alert type="info">{info}</Alert>
          <IconField id="register-otp" label="Passcode" icon={ICONS.pin} type="text" inputMode="numeric"
                     maxLength={6} required placeholder="6-digit code" autoComplete="one-time-code"
                     value={otp} onChange={(e) => setOtp(e.target.value)} />
          <IconField id="register-name" label="Your name" icon={ICONS.person} type="text"
                     placeholder="Full name" autoComplete="name"
                     value={name} onChange={(e) => setName(e.target.value)} />
          <PasswordField id="register-password" label="Password" required minLength={8}
                         placeholder="Choose a password" autoComplete="new-password" hint="At least 8 characters."
                         value={password} onChange={(e) => setPassword(e.target.value)} />
          <PasswordField id="register-confirm" label="Confirm password" required minLength={8}
                         placeholder="Re-enter the password" autoComplete="new-password"
                         value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
          <Alert>{error}</Alert>
          <div className={s.btnGroup}>
            <button type="submit" className={`${s.btn} ${s.btnPrimary}`} disabled={submitting} aria-busy={submitting}>
              {submitting ? 'Creating account…' : <>Create Account <Icon d={ICONS.arrow} /></>}
            </button>
            <button type="button" className={`${s.btn} ${s.btnSecondary}`} onClick={() => setStep('email')}>
              Back
            </button>
          </div>
        </form>
      )}
    </AuthPage>
  );
}
