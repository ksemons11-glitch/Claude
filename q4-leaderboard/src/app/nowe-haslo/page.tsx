import Link from 'next/link';
import { AuthShell } from '@/components/AuthShell';
import { NewPasswordForm } from '@/components/forms/ResetForms';

export default async function NewPasswordPage({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  const { token } = await searchParams;
  return (
    <AuthShell title="Ustaw nowe hasło">
      {token ? (
        <NewPasswordForm token={token} />
      ) : (
        <p className="alert-error">
          Brak tokenu. <Link href="/reset-hasla" className="link">Poproś o nowy link</Link>.
        </p>
      )}
    </AuthShell>
  );
}
