'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { API_BASE_URL } from '@/providers/AuthProvider';
import { AuthPage, IconField, PasswordField, Alert, Icon, ICONS, authStyles as s } from '@/components/auth/AuthUI';

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
    <AuthPage
      icon={ICONS.key}
      title={step === 'email' ? 'Reset your password' : 'Choose a new password'}
      lead={step === 'email'
        ? 'Every password change is verified by a passcode emailed to your account.'
        : <>Step 2 of 2 — enter the passcode sent to <b>{email}</b>.</>}
      footer={<>Remembered it?<Link href="/login" className={s.link}>Back to sign in</Link></>}
    >
      {step === 'email' ? (
        <form className={s.form} onSubmit={requestOtp}>
          <IconField id="reset-email" label="Email" icon={ICONS.mail} type="email" required
                     placeholder="name@sail.in" autoComplete="email"
                     value={email} onChange={(e) => setEmail(e.target.value)} />
          <Alert>{error}</Alert>
          <button type="submit" className={`${s.btn} ${s.btnPrimary}`} disabled={submitting} aria-busy={submitting}>
            {submitting ? 'Sending…' : <>Send Passcode <Icon d={ICONS.arrow} /></>}
          </button>
        </form>
      ) : (
        <form className={s.form} onSubmit={resetPassword}>
          <Alert type="info">{info}</Alert>
          <IconField id="reset-otp" label="Passcode" icon={ICONS.pin} type="text" inputMode="numeric"
                     maxLength={6} required placeholder="6-digit code" autoComplete="one-time-code"
                     value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))} />
          <PasswordField id="reset-password" label="New password" required minLength={8}
                         placeholder="Choose a new password" autoComplete="new-password" hint="At least 8 characters."
                         value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
          <PasswordField id="reset-confirm" label="Confirm new password" required minLength={8}
                         placeholder="Re-enter the new password" autoComplete="new-password"
                         value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
          <Alert>{error}</Alert>
          <div className={s.btnGroup}>
            <button type="submit" className={`${s.btn} ${s.btnPrimary}`} disabled={submitting} aria-busy={submitting}>
              {submitting ? 'Resetting…' : <>Reset Password <Icon d={ICONS.arrow} /></>}
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
