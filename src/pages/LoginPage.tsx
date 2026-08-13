import { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router';
import {
  AlertCircle,
  Dna,
  Eye,
  EyeOff,
  LoaderCircle,
  LockKeyhole,
  ShieldCheck,
  UserRound,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useAuth } from '@/contexts/AuthContext';
import { mapLoginError, validateLoginForm } from '@/lib/loginForm';

const REMEMBERED_USERNAME_KEY = 'stamp_login_remembered_username';

function getRememberedUsername(): string {
  try {
    return localStorage.getItem(REMEMBERED_USERNAME_KEY) ?? '';
  } catch {
    return '';
  }
}

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  const [username, setUsername] = useState(getRememberedUsername);
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(() => Boolean(getRememberedUsername()));
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname || '/';

  const clearError = () => {
    if (error) setError('');
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (loading) return;

    const validationError = validateLoginForm(username, password);
    if (validationError) {
      setError(validationError);
      return;
    }

    setError('');
    setLoading(true);

    try {
      const result = await login(username.trim(), password);
      if (!result.ok) {
        setError(mapLoginError(result.message));
        return;
      }

      try {
        if (rememberMe) {
          localStorage.setItem(REMEMBERED_USERNAME_KEY, username.trim());
        } else {
          localStorage.removeItem(REMEMBERED_USERNAME_KEY);
        }
      } catch {
        // Remember me is optional and must never block authentication.
      }

      if (result.mustChangePassword) {
        navigate('/change-password', { state: { from } });
      } else {
        navigate(from, { replace: true });
      }
    } catch (loginError) {
      setError(mapLoginError(loginError instanceof Error ? loginError.message : 'Network error'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="relative flex min-h-[100dvh] items-center justify-center overflow-x-hidden bg-gradient-to-br from-slate-50 via-sky-50/80 to-blue-100/70 px-4 py-8 sm:px-6">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -left-24 top-[-7rem] h-72 w-72 rounded-full bg-sky-300/25 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-28 right-[-5rem] h-80 w-80 rounded-full bg-blue-300/25 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-[0.22] [background-image:linear-gradient(rgba(21,107,152,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(21,107,152,0.08)_1px,transparent_1px)] [background-size:40px_40px]"
      />

      <Card className="relative z-10 w-full max-w-[460px] overflow-hidden rounded-[28px] border border-white/80 bg-white/95 shadow-[0_24px_70px_-24px_rgba(15,56,82,0.35)] backdrop-blur">
        <div className="h-1.5 bg-gradient-to-r from-[#156B98] via-sky-500 to-cyan-400" />
        <CardHeader className="space-y-5 px-6 pb-5 pt-8 text-center sm:px-9 sm:pt-10">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[#156B98] text-white shadow-lg shadow-sky-900/20">
            <Dna className="h-7 w-7" aria-hidden="true" />
          </div>
          <div className="space-y-1">
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#156B98]">STAMP Platform</p>
            <p className="text-xs font-medium tracking-wide text-slate-500">Targeted Peptide Design Platform</p>
          </div>
          <div className="space-y-2 pt-1">
            <CardTitle className="text-3xl font-semibold tracking-tight text-slate-900">Welcome back</CardTitle>
            <CardDescription className="text-sm leading-6 text-slate-500">
              Sign in to continue to your research workspace.
            </CardDescription>
          </div>
        </CardHeader>

        <CardContent className="px-6 pb-8 sm:px-9 sm:pb-10">
          <form onSubmit={handleSubmit} noValidate className="space-y-5">
            {error && (
              <Alert
                variant="destructive"
                aria-live="polite"
                className="border-red-200 bg-red-50/90 text-red-900 shadow-none"
              >
                <AlertCircle aria-hidden="true" />
                <AlertDescription className="text-red-800">{error}</AlertDescription>
              </Alert>
            )}

            <fieldset disabled={loading} className="space-y-4 disabled:opacity-75">
              <div className="space-y-2">
                <Label htmlFor="username" className="text-sm font-medium text-slate-700">
                  Username
                </Label>
                <div className="relative">
                  <UserRound
                    aria-hidden="true"
                    className="pointer-events-none absolute left-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400"
                  />
                  <Input
                    id="username"
                    name="username"
                    value={username}
                    onChange={(event) => {
                      setUsername(event.target.value);
                      clearError();
                    }}
                    placeholder="Username"
                    autoComplete="username"
                    autoFocus
                    aria-invalid={Boolean(error)}
                    className="h-12 rounded-xl border-slate-200 bg-white pl-10 text-slate-900 shadow-sm transition focus-visible:border-[#156B98] focus-visible:ring-[#156B98]/20"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="password" className="text-sm font-medium text-slate-700">
                  Password
                </Label>
                <div className="relative">
                  <LockKeyhole
                    aria-hidden="true"
                    className="pointer-events-none absolute left-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400"
                  />
                  <Input
                    id="password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(event) => {
                      setPassword(event.target.value);
                      clearError();
                    }}
                    placeholder="Password"
                    autoComplete="current-password"
                    aria-invalid={Boolean(error)}
                    className="h-12 rounded-xl border-slate-200 bg-white px-10 text-slate-900 shadow-sm transition focus-visible:border-[#156B98] focus-visible:ring-[#156B98]/20"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((visible) => !visible)}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    aria-pressed={showPassword}
                    className="absolute right-2 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-lg text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#156B98]/30"
                  >
                    {showPassword ? (
                      <EyeOff className="h-5 w-5" aria-hidden="true" />
                    ) : (
                      <Eye className="h-5 w-5" aria-hidden="true" />
                    )}
                  </button>
                </div>
              </div>

              <div className="flex items-center gap-2.5 pt-0.5">
                <Checkbox
                  id="remember-me"
                  checked={rememberMe}
                  onCheckedChange={(checked) => setRememberMe(checked === true)}
                  className="border-slate-300 data-[state=checked]:border-[#156B98] data-[state=checked]:bg-[#156B98]"
                />
                <Label htmlFor="remember-me" className="cursor-pointer text-sm font-normal text-slate-600">
                  Remember me
                </Label>
              </div>
            </fieldset>

            <Button
              type="submit"
              disabled={loading}
              className="h-12 w-full rounded-xl bg-[#156B98] text-sm font-semibold text-white shadow-lg shadow-sky-900/15 transition hover:bg-[#105b82] focus-visible:ring-[#156B98]/30"
            >
              {loading ? (
                <>
                  <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" />
                  Signing in...
                </>
              ) : (
                'Sign in to STAMP'
              )}
            </Button>
          </form>

          <div className="my-6 flex items-center gap-3" aria-hidden="true">
            <div className="h-px flex-1 bg-slate-200" />
            <span className="text-xs font-medium uppercase tracking-wider text-slate-400">New to STAMP?</span>
            <div className="h-px flex-1 bg-slate-200" />
          </div>

          <Button asChild variant="outline" className="h-11 w-full rounded-xl border-slate-200 bg-white text-slate-700 shadow-sm hover:border-sky-200 hover:bg-sky-50 hover:text-[#156B98]">
            <Link to="/register">Register an account</Link>
          </Button>

          <div className="mt-6 flex items-center justify-center gap-2 text-xs text-slate-400">
            <ShieldCheck className="h-4 w-4 text-[#156B98]" aria-hidden="true" />
            <span>Secure access to the STAMP research platform</span>
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
