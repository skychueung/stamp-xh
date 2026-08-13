/**
 * Client-side password change validation.
 *
 * These checks mirror the backend policy so the user gets immediate,
 * Chinese-language feedback without a round-trip.
 */

export interface PasswordChangeValidation {
  valid: boolean;
  message?: string;
}

export function validatePasswordChange(
  currentPassword: string,
  newPassword: string,
  confirmPassword: string,
): PasswordChangeValidation {
  if (!currentPassword) {
    return { valid: false, message: '请输入当前密码。' };
  }
  if (newPassword.length < 8) {
    return { valid: false, message: '新密码长度不能少于 8 个字符。' };
  }
  if (newPassword !== confirmPassword) {
    return { valid: false, message: '两次输入的新密码不一致。' };
  }
  return { valid: true };
}
