import { Link } from 'react-router';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function ForbiddenPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-xh-bg p-4 ml-[260px]">
      <Card className="w-full max-w-md shadow-lg border-xh-border text-center">
        <CardHeader>
          <CardTitle className="text-3xl font-semibold text-xh-text-primary">403</CardTitle>
          <CardDescription className="text-xh-text-secondary">Access denied</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-xh-text-secondary">
            You do not have permission to view this page. If you believe this is an error, contact an administrator.
          </p>
          <Button asChild className="w-full">
            <Link to="/">Go home</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
