import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useAuth } from '@/contexts/AuthContext';

interface AdminUser {
  id: string;
  username: string;
  email: string | null;
  role: string;
  status: 'pending' | 'active' | 'disabled';
  must_change_password: boolean;
  failed_login_attempts: number;
  locked_until: string | null;
  created_at: string;
  approved_at: string | null;
  approved_by: string | null;
}

const API_BASE = '/api/v1';

async function apiFetch(path: string, options: RequestInit = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  return { res, data };
}

function getCsrfCookie(): string | null {
  const match = document.cookie.match(/(^| )stamp_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[2]) : null;
}

export default function AdminUsersPage() {
  const navigate = useNavigate();
  const { user, isAdmin, isLoading } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    if (isLoading) return;
    if (!user) {
      navigate('/login', { state: { from: { pathname: '/admin/users' } } });
      return;
    }
    if (!isAdmin) {
      navigate('/403');
      return;
    }
    loadUsers();
  }, [user, isAdmin, isLoading, navigate]);

  const loadUsers = async () => {
    setError('');
    const { res, data } = await apiFetch('/admin/users');
    if (res.ok && data?.data) {
      setUsers(data.data.items);
    } else {
      setError(data?.detail || 'Failed to load users.');
      if (res.status === 401) navigate('/login');
      if (res.status === 403) navigate('/403');
    }
  };

  const act = async (userId: string, action: 'approve' | 'disable') => {
    setBusyId(userId);
    setError('');
    setMessage('');
    const token = getCsrfCookie();
    const { res, data } = await apiFetch(`/admin/users/${userId}/${action}`, {
      method: 'POST',
      headers: token ? { 'X-CSRF-Token': token } : {},
    });
    setBusyId(null);
    if (res.ok) {
      setMessage(`User ${action === 'approve' ? 'approved' : 'disabled'} successfully.`);
      await loadUsers();
    } else {
      setError(data?.detail || `Failed to ${action} user.`);
      if (res.status === 401) navigate('/login');
      if (res.status === 403) navigate('/403');
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-xh-bg ml-[260px]">
        <div className="w-8 h-8 border-2 border-xh-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-xh-bg p-6">
      <Card className="border-xh-border shadow-sm">
        <CardHeader>
          <CardTitle className="text-xl font-semibold text-xh-text-primary">User management</CardTitle>
          <CardDescription className="text-xh-text-secondary">
            Approve pending users or disable accounts.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          {message && (
            <Alert>
              <AlertDescription>{message}</AlertDescription>
            </Alert>
          )}
          <div className="overflow-x-auto rounded border border-xh-border">
            <table className="min-w-full text-sm">
              <thead className="bg-xh-bg-gray text-xh-text-secondary">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">Username</th>
                  <th className="px-4 py-2 text-left font-medium">Role</th>
                  <th className="px-4 py-2 text-left font-medium">Status</th>
                  <th className="px-4 py-2 text-left font-medium">Created</th>
                  <th className="px-4 py-2 text-left font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-xh-border">
                {users.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-6 text-center text-xh-text-secondary">
                      No users found.
                    </td>
                  </tr>
                )}
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-xh-bg-gray/50">
                    <td className="px-4 py-3 font-medium text-xh-text-primary">
                      {u.username}
                      {u.must_change_password && (
                        <Badge variant="outline" className="ml-2 text-[10px]">
                          must change password
                        </Badge>
                      )}
                    </td>
                    <td className="px-4 py-3 capitalize text-xh-text-secondary">{u.role}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={u.status} />
                    </td>
                    <td className="px-4 py-3 text-xh-text-secondary">
                      {new Date(u.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        {u.status === 'pending' && (
                          <Button
                            size="sm"
                            onClick={() => act(u.id, 'approve')}
                            disabled={busyId === u.id}
                          >
                            {busyId === u.id ? '…' : 'Approve'}
                          </Button>
                        )}
                        {u.status === 'active' && u.role !== 'admin' && (
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => act(u.id, 'disable')}
                            disabled={busyId === u.id}
                          >
                            {busyId === u.id ? '…' : 'Disable'}
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function StatusBadge({ status }: { status: AdminUser['status'] }) {
  const variants: Record<AdminUser['status'], string> = {
    pending: 'bg-amber-100 text-amber-800 border-amber-200',
    active: 'bg-emerald-100 text-emerald-800 border-emerald-200',
    disabled: 'bg-red-100 text-red-800 border-red-200',
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${variants[status]}`}>
      {status}
    </span>
  );
}
