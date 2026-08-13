import { describe, expect, it } from 'vitest';
import { LOGIN_FORM_MESSAGES, mapLoginError, validateLoginForm } from './loginForm';

describe('validateLoginForm', () => {
  it('requires a username', () => {
    expect(validateLoginForm('   ', 'secret')).toBe(LOGIN_FORM_MESSAGES.usernameRequired);
  });

  it('requires a password', () => {
    expect(validateLoginForm('researcher', '')).toBe(LOGIN_FORM_MESSAGES.passwordRequired);
  });

  it('accepts non-empty credentials', () => {
    expect(validateLoginForm('researcher', 'secret')).toBeNull();
  });
});

describe('mapLoginError', () => {
  it('maps invalid credentials', () => {
    expect(mapLoginError('Invalid username or password.')).toBe(LOGIN_FORM_MESSAGES.invalidCredentials);
  });

  it('maps network failures', () => {
    expect(mapLoginError('Failed to fetch')).toBe(LOGIN_FORM_MESSAGES.networkUnavailable);
  });

  it('maps an account waiting for approval', () => {
    expect(mapLoginError('Account pending approval.')).toBe(LOGIN_FORM_MESSAGES.approvalPending);
  });

  it('maps a disabled account', () => {
    expect(mapLoginError('Account has been disabled. Please contact an administrator.')).toBe(
      LOGIN_FORM_MESSAGES.accountDisabled,
    );
  });

  it('treats the legacy combined status error as disabled instead of showing a false approval wait', () => {
    expect(mapLoginError('Account not approved or disabled.')).toBe(LOGIN_FORM_MESSAGES.accountDisabled);
  });

  it('maps a temporarily locked account', () => {
    expect(mapLoginError('Account temporarily locked due to failed login attempts.')).toBe(
      LOGIN_FORM_MESSAGES.accountLocked,
    );
  });

  it('uses a safe fallback for unknown errors', () => {
    expect(mapLoginError('Unexpected upstream response')).toBe(LOGIN_FORM_MESSAGES.unknown);
  });
});
