import { redirect } from 'next/navigation';
import { AuthShell } from '@/components/AuthShell';
import { LoginForm } from '@/components/forms/LoginForm';
import { getCurrentUser } from '@/lib/auth';

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ haslo?: string }> }) {
  if (await getCurrentUser()) redirect('/konto');
  const { haslo } = await searchParams;
  return (
    <AuthShell title="Zaloguj się">
      {haslo === 'zmienione' && <p className="alert-success mb-4">Hasło zostało zmienione. Zaloguj się nowym hasłem.</p>}
      <LoginForm />
    </AuthShell>
  );
}
