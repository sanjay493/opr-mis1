'use client';

// Shared layout for the sign-in pages (/login, /register, /forgot-password):
// the Stitch "Secure Enterprise Login" card — emblem, title, icon inputs,
// show/hide password and the authorized-use notice. Styles in auth.module.css.

import { useState } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
import s from './auth.module.css';

export { s as authStyles };

// Inline icons (Material Symbols outlines)
export const Icon = ({ d, size = 18 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d={d} /></svg>
);
export const ICONS = {
  bank: 'M4 10v7h3v-7H4zm6 0v7h3v-7h-3zM2 22h19v-3H2v3zm14-12v7h3v-7h-3zm-4.5-9L2 6v2h19V6l-9.5-5z',
  mail: 'M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4-8 5-8-5V6l8 5 8-5v2z',
  lock: 'M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zM9 6c0-1.66 1.34-3 3-3s3 1.34 3 3v2H9V6zm9 14H6V10h12v10zm-6-3c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2z',
  eye: 'M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z',
  eyeOff: 'M12 7c2.76 0 5 2.24 5 5 0 .65-.13 1.26-.36 1.83l2.92 2.92c1.51-1.26 2.7-2.89 3.43-4.75-1.73-4.39-6-7.5-11-7.5-1.4 0-2.74.25-3.98.7l2.16 2.16C10.74 7.13 11.35 7 12 7zM2 4.27l2.28 2.28.46.46C3.08 8.3 1.78 10.02 1 12c1.73 4.39 6 7.5 11 7.5 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 9.8l1.55 1.55c-.05.21-.08.43-.08.65 0 1.66 1.34 3 3 3 .22 0 .44-.03.65-.08l1.55 1.55c-.67.33-1.41.53-2.2.53-2.76 0-5-2.24-5-5 0-.79.2-1.53.53-2.2zm4.31-.78 3.15 3.15.02-.16c0-1.66-1.34-3-3-3l-.17.01z',
  arrow: 'M12 4l-1.41 1.41L16.17 11H4v2h12.17l-5.58 5.59L12 20l8-8z',
  policy: 'M12 1 3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z',
  person: 'M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z',
  personAdd: 'M15 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm-9-2V7H4v3H1v2h3v3h2v-3h3v-2H6zm9 4c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z',
  key: 'M12.65 10A5.99 5.99 0 0 0 7 6c-3.31 0-6 2.69-6 6s2.69 6 6 6a5.99 5.99 0 0 0 5.65-4H17v4h4v-4h2v-4H12.65zM7 14c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2z',
  pin: 'M12 17c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm6-9h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6h2c0-1.66 1.34-3 3-3s3 1.34 3 3v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm0 12H6V10h12v10z',
};

// Page frame: navbar + dotted background + centred card + notice.
export function AuthPage({ icon, iconSize = 26, title, lead, footer, children }) {
  return (
    <>
      <GlobalNavbar />
      <main className={s.shell}>
        <div className={s.column}>
          <div className={s.card}>
            <div className={s.head}>
              <div className={s.emblem}><Icon d={icon} size={iconSize} /></div>
              <h1 className={s.title}>{title}</h1>
              {lead && <p className={s.lead}>{lead}</p>}
            </div>
            {children}
            {footer && <div className={s.foot}>{footer}</div>}
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

// Labelled input with a leading icon; extra props go to the <input>.
export function IconField({ id, label, icon, hint, ...inputProps }) {
  return (
    <div>
      <label htmlFor={id} className={s.label}>{label}</label>
      <div className={s.inputWrap}>
        <span className={s.inputIcon}><Icon d={icon} /></span>
        <input id={id} className={s.input} aria-describedby={hint ? `${id}-hint` : undefined} {...inputProps} />
      </div>
      {hint && <div id={`${id}-hint`} className={s.hint}>{hint}</div>}
    </div>
  );
}

// Password input with the lock icon and a show/hide toggle.
export function PasswordField({ id, label, hint, ...inputProps }) {
  const [show, setShow] = useState(false);
  return (
    <div>
      <label htmlFor={id} className={s.label}>{label}</label>
      <div className={s.inputWrap}>
        <span className={s.inputIcon}><Icon d={ICONS.lock} /></span>
        <input id={id} type={show ? 'text' : 'password'} className={`${s.input} ${s.inputPw}`}
               aria-describedby={hint ? `${id}-hint` : undefined} {...inputProps} />
        <button type="button" className={s.eye} onClick={() => setShow((v) => !v)}
                aria-label={show ? 'Hide password' : 'Show password'} title={show ? 'Hide password' : 'Show password'}>
          <Icon d={show ? ICONS.eyeOff : ICONS.eye} size={19} />
        </button>
      </div>
      {hint && <div id={`${id}-hint`} className={s.hint}>{hint}</div>}
    </div>
  );
}

export function Alert({ type = 'error', children }) {
  if (!children) return null;
  return (
    <p role={type === 'error' ? 'alert' : 'status'} className={`${s.alert} ${type === 'error' ? s.alertError : s.alertInfo}`}>
      {children}
    </p>
  );
}
