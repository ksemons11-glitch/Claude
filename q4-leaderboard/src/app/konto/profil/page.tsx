import Link from 'next/link';
import { Header } from '@/components/Header';
import { DeletionForm, PasswordForm, ProfileForm } from '@/components/forms/ProfileForms';
import { requireUser } from '@/lib/auth';
import { config } from '@/lib/config';
import { AVATAR_PRESETS } from '@/lib/data';

export default async function ProfilePage() {
  const user = await requireUser();
  return (
    <>
      <Header />
      <main className="mx-auto max-w-xl space-y-6 px-4 pb-16 pt-6">
        <section className="card p-5">
          <h1 className="mb-5 text-xl font-extrabold">Profil</h1>
          <p className="mb-5 text-sm text-muted">
            E-mail: <span className="text-white">{user.email}</span> (widoczny tylko dla Ciebie i organizatora)
          </p>
          <ProfileForm
            nickname={user.publicNickname}
            discord={user.discordNickname}
            presets={AVATAR_PRESETS}
            avatarPreset={user.avatarPreset}
            currentUpload={user.avatarFile ? `/api/avatar/${user.avatarFile}` : null}
          />
        </section>
        <section className="card p-5">
          <h2 className="mb-4 text-lg font-bold">Zmiana hasła</h2>
          <PasswordForm />
        </section>
        <section className="card p-5">
          <h2 className="mb-2 text-lg font-bold">Twoje dane</h2>
          <p className="mb-4 text-sm text-muted">
            Publicznie pokazujemy wyłącznie Twój nick rankingowy, awatar i deklarowane wyniki. Szczegóły w{' '}
            <a href={config.privacyUrl} target="_blank" rel="noopener noreferrer" className="link">polityce prywatności</a>
            {config.dataController && <> (administrator danych: {config.dataController})</>}.
          </p>
          <DeletionForm requested={Boolean(user.deletionRequestedAt)} />
        </section>
        <Link href="/konto" className="btn-ghost w-full">← Wróć</Link>
      </main>
    </>
  );
}
