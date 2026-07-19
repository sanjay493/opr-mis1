'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import GlobalNavbar from '@/components/GlobalNavbar';
import { useAuth, API_BASE_URL } from '@/providers/AuthProvider';

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
      <main style={{ maxWidth: '420px', margin: '80px auto', padding: '0 20px' }}>
        <h1 style={{ fontSize: '20pt', marginBottom: '4px' }}>Register</h1>
        <p style={{ color: '#5f6368', marginBottom: '24px' }}>
          Your email must be pre-approved by an administrator. A new account starts
          with view-only access until an administrator assigns you a role.
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
          <form onSubmit={completeRegistration}>
            {info && <p style={{ color: '#188038', fontSize: '10pt', marginBottom: '14px' }}>{info}</p>}
            <div className="form-group">
              <label>Passcode</label>
              <input
                type="text" inputMode="numeric" maxLength={6} className="form-control" required
                value={otp} onChange={(e) => setOtp(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label>Your name</label>
              <input
                type="text" className="form-control"
                value={name} onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label>Password</label>
              <input
                type="password" className="form-control" required minLength={8}
                value={password} onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
              />
            </div>
            <div className="form-group">
              <label>Confirm password</label>
              <input
                type="password" className="form-control" required minLength={8}
                value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
              />
            </div>
            {error && <p style={{ color: '#d93025', fontSize: '10pt', marginBottom: '12px' }}>{error}</p>}
            <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={submitting}>
              {submitting ? 'Creating account…' : 'Create Account'}
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
          <Link href="/login">Already have an account? Log in</Link>
        </div>
      </main>
    </>
  );
}
