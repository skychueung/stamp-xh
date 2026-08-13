import { describe, it, expect } from 'vitest';
import { validatePasswordChange } from './passwordPolicy';

describe('validatePasswordChange', () => {
  it('accepts matching new passwords of at least 8 characters', () => {
    expect(validatePasswordChange('old-password', 'new-password', 'new-password')).toEqual({
      valid: true,
    });
  });

  it('rejects empty current password', () => {
    expect(validatePasswordChange('', 'new-password', 'new-password')).toEqual({
      valid: false,
      message: '请输入当前密码。',
    });
  });

  it('rejects new passwords shorter than 8 characters', () => {
    expect(validatePasswordChange('old-password', 'short', 'short')).toEqual({
      valid: false,
      message: '新密码长度不能少于 8 个字符。',
    });
  });

  it('rejects mismatched confirmation password', () => {
    expect(validatePasswordChange('old-password', 'new-password', 'different-password')).toEqual({
      valid: false,
      message: '两次输入的新密码不一致。',
    });
  });
});
