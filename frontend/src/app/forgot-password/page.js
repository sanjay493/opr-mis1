'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import GlobalNavbar from '@/components/GlobalNavbar';
import { API_BASE_URL } from '@/providers/AuthProvider';

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
      <main style={{ maxWidth: '420px', margin: '80px auto', padding: '0 20px' }}>
        <h1 style={{ fontSize: '20pt', marginBottom: '4px' }}>Reset Password</h1>
        <p style={{ color: '#5f6368', marginBottom: '24px' }}>
          Every password change is verified by a passcode emailed to your account.
        </p>

        {step === 'email' ? (
          <form onSubmit={requestOtp}>
            <div className="form-group">
              <label>Email</label>
              <input
                type="email" className="form-control" required
                value={email} onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            {error && <p style={{ color: '#d93025', fontSize: '10pt', marginBottom: '12px' }}>{error}</p>}
            <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={submitting}>
              {submitting ? 'Sending…' : 'Send Passcode'}
            </button>
          </form>
        ) : (
          <form onSubmit={resetPassword}>
            {info && <p style={{ color: '#188038', fontSize: '10pt', marginBottom: '14px' }}>{info}</p>}
            <div className="form-group">
              <label>Passcode</label>
              <input
                type="text" inputMode="numeric" maxLength={6} className="form-control" required
                value={otp} onChange={(e) => setOtp(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label>New password</label>
              <input
                type="password" className="form-control" required minLength={8}
                value={newPassword} onChange={(e) => setNewPassword(e.target.value)}
                autoComplete="new-password"
              />
            </div>
            <div className="form-group">
              <label>Confirm new password</label>
              <input
                type="password" className="form-control" required minLength={8}
                value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
              />
            </div>
            {error && <p style={{ color: '#d93025', fontSize: '10pt', marginBottom: '12px' }}>{error}</p>}
            <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={submitting}>
              {submitting ? 'Resetting…' : 'Reset Password'}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              style={{ width: '100%', marginTop: '8px' }}
              onClick={() => setStep('email')}
            >
              Back
            </button>
          </form>
        )}

        <div style={{ marginTop: '20px', fontSize: '10.5pt' }}>
          <Link href="/login">Back to login</Link>
        </div>
      </main>
    </>
  );
}
