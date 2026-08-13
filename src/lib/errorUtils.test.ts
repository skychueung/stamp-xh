import { describe, it, expect } from 'vitest';
import { parseFastApiError } from './errorUtils';

describe('parseFastApiError', () => {
  it('returns a Chinese message for string detail', () => {
    expect(parseFastApiError({ detail: 'Current password is incorrect.' })).toBe(
      '当前密码错误，请重新输入。',
    );
  });

  it('returns a Chinese message for a validation error array', () => {
    expect(
      parseFastApiError({
        detail: [
          {
            type: 'string_too_short',
            loc: ['body', 'new_password'],
            msg: 'String should have at least 8 characters',
            input: 'short',
            ctx: { min_length: 8 },
          },
        ],
      }),
    ).toBe('新密码长度不能少于 8 个字符');
  });

  it('joins multiple validation errors with a semicolon', () => {
    expect(
      parseFastApiError({
        detail: [
          {
            type: 'missing',
            loc: ['body', 'new_password'],
            msg: 'Field required',
            input: undefined,
          },
          {
            type: 'string_too_short',
            loc: ['body', 'current_password'],
            msg: 'String should have at least 1 character',
            input: '',
            ctx: { min_length: 1 },
          },
        ],
      }),
    ).toBe('新密码不能为空；当前密码长度不能少于 1 个字符');
  });

  it('returns a default message for an object detail', () => {
    expect(parseFastApiError({ detail: { code: 'invalid_state' } })).toContain('invalid_state');
  });

  it('returns a default message for null data', () => {
    expect(parseFastApiError(null)).toBe('操作失败，请稍后重试。');
  });

  it('returns a default message for non-object data', () => {
    expect(parseFastApiError('plain text')).toBe('操作失败，请稍后重试。');
  });

  it('prefers the top-level message field if present', () => {
    expect(parseFastApiError({ message: '服务暂时不可用，请稍后重试。' })).toBe(
      '服务暂时不可用，请稍后重试。',
    );
  });
});
