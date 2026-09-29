import Link from 'next/link';
import { redirect } from 'next/navigation';
import { AuthShell } from '@/components/AuthShell';
import { RegisterForm } from '@/components/forms/RegisterForm';
import { getCurrentUser } from '@/lib/auth';
import { config } from '@/lib/config';
import { AVATAR_PRESETS, getEvent } from '@/lib/data';

export default async function RegisterPage() {
  if (await getCurrentUser()) redirect('/konto');
  const event = await getEvent();
  return (
    <AuthShell
      title="Dołącz do rankingu"
      subtitle={
        <>
          Masz już konto? <Link href="/logowanie" className="link">Zaloguj się</Link>
        </>
      }
    >
      {event.registrationOpen ? (
        <RegisterForm
          presets={AVATAR_PRESETS}
          codeRequired={event.accessCodeRequired && Boolean(event.accessCodeHash)}
          termsUrl={config.termsUrl}
          privacyUrl={config.privacyUrl}
        />
      ) : (
        <p className="alert-info">Rejestracja jest obecnie zamknięta.</p>
      )}
    </AuthShell>
  );
}
