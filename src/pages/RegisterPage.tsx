import { useState } from 'react';
import { Link } from 'react-router';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useAuth } from '@/contexts/AuthContext';

export default function RegisterPage() {
  const { register } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [registrationStatus, setRegistrationStatus] = useState<'pending' | 'active' | 'disabled' | undefined>();
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (password !== confirm) {
      setError('Passwords do not match.');
      return;
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }
    setLoading(true);
    try {
      const result = await register(username, password, email || undefined);
      if (result.ok) {
        setSuccessMessage(result.message);
        setRegistrationStatus(result.status);
      } else {
        setError(result.message);
      }
    } catch {
      setError('Unable to connect to the server. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  if (successMessage) {
    const canSignIn = registrationStatus !== 'pending';
    return (
      <div className="min-h-screen flex items-center justify-center bg-xh-bg p-4">
        <Card className="w-full max-w-md shadow-lg border-xh-border">
          <CardHeader>
            <CardTitle className="text-2xl font-semibold text-xh-text-primary">Registration successful</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Alert>
              <AlertDescription>{successMessage}</AlertDescription>
            </Alert>
            <p className="text-sm text-xh-text-secondary">
              {canSignIn
                ? 'Your account is active. Continue to the login page to access your workspace.'
                : 'Approval mode is enabled. You will be able to sign in after an administrator approves your account.'}
            </p>
            <Button asChild className="w-full">
              <Link to="/login">Go to login</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-xh-bg p-4">
      <Card className="w-full max-w-md shadow-lg border-xh-border">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl font-semibold text-xh-text-primary">Register</CardTitle>
          <CardDescription className="text-xh-text-secondary">
            Create a new account for the STAMP platform.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="3-32 chars, alphanumeric, - or _"
                autoComplete="username"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email (optional)</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="user@example.com"
                autoComplete="email"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 8 characters"
                autoComplete="new-password"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm">Confirm password</Label>
              <Input
                id="confirm"
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="At least 8 characters"
                autoComplete="new-password"
                required
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? 'Registering…' : 'Register'}
            </Button>
          </form>
          <p className="mt-4 text-center text-sm text-xh-text-secondary">
            Already have an account?{' '}
            <Link to="/login" className="text-xh-primary hover:underline">
              Log in
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
