export const LOGIN_FORM_MESSAGES = {
  usernameRequired: 'Please enter your username.',
  passwordRequired: 'Please enter your password.',
  invalidCredentials: 'The username or password is incorrect.',
  approvalPending: 'Your account is waiting for administrator approval.',
  accountDisabled: 'Your account has been disabled. Please contact an administrator.',
  accountLocked: 'Your account is temporarily locked. Please try again later.',
  networkUnavailable: 'Unable to connect to the server. Please try again later.',
  unknown: 'Sign in failed. Please try again.',
} as const;

export function validateLoginForm(username: string, password: string): string | null {
  if (!username.trim()) return LOGIN_FORM_MESSAGES.usernameRequired;
  if (!password) return LOGIN_FORM_MESSAGES.passwordRequired;
  return null;
}

export function mapLoginError(message: string | null | undefined): string {
  if (!message) return LOGIN_FORM_MESSAGES.unknown;

  const normalized = message.trim().toLowerCase();

  if (
    normalized.includes('invalid username or password') ||
    normalized.includes('incorrect username or password') ||
    normalized.includes('invalid credentials')
  ) {
    return LOGIN_FORM_MESSAGES.invalidCredentials;
  }

  if (normalized.includes('temporarily locked') || normalized.includes('account locked')) {
    return LOGIN_FORM_MESSAGES.accountLocked;
  }

  if (normalized.includes('not approved or disabled')) {
    return LOGIN_FORM_MESSAGES.accountDisabled;
  }

  if (
    normalized.includes('waiting for administrator approval') ||
    normalized.includes('pending approval') ||
    normalized.includes('not approved')
  ) {
    return LOGIN_FORM_MESSAGES.approvalPending;
  }

  if (normalized.includes('disabled')) {
    return LOGIN_FORM_MESSAGES.accountDisabled;
  }

  if (
    normalized.includes('failed to fetch') ||
    normalized.includes('network error') ||
    normalized.includes('networkerror') ||
    normalized.includes('load failed') ||
    normalized.includes('unable to connect') ||
    normalized.includes('connection refused') ||
    normalized.includes('timed out') ||
    normalized.includes('timeout')
  ) {
    return LOGIN_FORM_MESSAGES.networkUnavailable;
  }

  return LOGIN_FORM_MESSAGES.unknown;
}
