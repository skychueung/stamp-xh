/**
 * Unified FastAPI error detail parser.
 *
 * FastAPI may return errors in several shapes:
 *   { detail: "string" }
 *   { detail: [{ msg: "...", loc: [...], type: "..." }] }
 *   { detail: { ... } }
 *
 * This module normalises all of them into a single human-readable string,
 * with i18n-friendly Chinese defaults for common authentication cases.
 */

export interface FastApiValidationError {
  loc?: (string | number)[];
  msg?: string;
  type?: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}

export interface FastApiErrorBody {
  detail?: string | FastApiValidationError[] | Record<string, unknown> | null;
  message?: string;
  [key: string]: unknown;
}

const DEFAULT_MESSAGE = '操作失败，请稍后重试。';

const FIELD_LABELS: Record<string, string> = {
  current_password: '当前密码',
  new_password: '新密码',
  confirm_password: '确认密码',
  password: '密码',
  username: '用户名',
  email: '邮箱',
};

const TYPE_MESSAGES: Record<string, string> = {
  string_too_short: '长度不能少于 {min_length} 个字符',
  string_too_long: '长度不能超过 {max_length} 个字符',
  missing: '不能为空',
  value_error: '格式不正确',
  assertion_error: '校验失败',
};

function interpolate(template: string, ctx: Record<string, unknown>): string {
  return template.replace(/\{(\w+)\}/g, (_, key) => String(ctx[key] ?? ''));
}

function translateValidationError(err: FastApiValidationError): string {
  const field = err.loc && err.loc.length > 0 ? String(err.loc[err.loc.length - 1]) : '';
  const label = FIELD_LABELS[field] || field || '输入';

  if (err.type && err.type in TYPE_MESSAGES) {
    const template = TYPE_MESSAGES[err.type];
    return `${label}${interpolate(template, err.ctx ?? {})}`;
  }

  if (err.msg) {
    return `${label}${err.msg}`;
  }

  return `${label}校验失败`;
}

function translateCommonDetail(detail: string): string {
  const lower = detail.toLowerCase();
  if (lower.includes('current password is incorrect')) {
    return '当前密码错误，请重新输入。';
  }
  if (lower.includes('password must be at least')) {
    return '新密码长度不能少于 8 个字符。';
  }
  if (lower.includes('not authenticated')) {
    return '登录状态已过期，请重新登录。';
  }
  if (lower.includes('csrf')) {
    return '安全校验失败，请刷新页面后重试。';
  }
  return detail;
}

export function parseFastApiError(data: unknown): string {
  if (!data || typeof data !== 'object') {
    return DEFAULT_MESSAGE;
  }

  const body = data as FastApiErrorBody;

  if (typeof body.message === 'string' && body.message) {
    return body.message;
  }

  const detail = body.detail;

  if (typeof detail === 'string') {
    return translateCommonDetail(detail);
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === 'string') return translateCommonDetail(item);
        if (item && typeof item === 'object') return translateValidationError(item as FastApiValidationError);
        return '';
      })
      .filter(Boolean);
    return messages.length > 0 ? messages.join('；') : DEFAULT_MESSAGE;
  }

  if (detail && typeof detail === 'object') {
    return translateCommonDetail(JSON.stringify(detail));
  }

  return DEFAULT_MESSAGE;
}
