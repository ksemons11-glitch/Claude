'use client';

import { useActionState } from 'react';
import { changePasswordAction, requestDeletionAction, updateProfileAction } from '@/app/actions/participant';
import { AvatarPicker } from '../AvatarPicker';
import { FormMessage } from '../FormMessage';
import { SubmitButton } from '../SubmitButton';

export function ProfileForm({
  nickname,
  discord,
  presets,
  avatarPreset,
  currentUpload,
}: {
  nickname: string;
  discord: string;
  presets: readonly string[];
  avatarPreset: string | null;
  currentUpload: string | null;
}) {
  const [state, action] = useActionState(updateProfileAction, undefined);
  return (
    <form action={action} className="space-y-5">
      <div>
        <label htmlFor="nickname" className="label">Publiczny nick rankingowy</label>
        <input id="nickname" name="nickname" required minLength={3} maxLength={24} className="input" defaultValue={state?.fields?.nickname ?? nickname} />
      </div>
      <div>
        <label htmlFor="discord" className="label">Nick z Discorda (prywatny)</label>
        <input id="discord" name="discord" required maxLength={40} className="input" defaultValue={state?.fields?.discord ?? discord} />
      </div>
      <AvatarPicker presets={presets} initialPreset={avatarPreset} currentUpload={currentUpload} />
      <FormMessage state={state} />
      <SubmitButton>Zapisz profil</SubmitButton>
    </form>
  );
}

export function PasswordForm() {
  const [state, action] = useActionState(changePasswordAction, undefined);
  return (
    <form action={action} className="space-y-4">
      <div>
        <label htmlFor="current" className="label">Obecne hasło</label>
        <input id="current" name="current" type="password" autoComplete="current-password" required className="input" />
      </div>
      <div>
        <label htmlFor="new-password" className="label">Nowe hasło (min. 8 znaków)</label>
        <input id="new-password" name="password" type="password" autoComplete="new-password" minLength={8} required className="input" />
      </div>
      <div>
        <label htmlFor="new-password2" className="label">Powtórz nowe hasło</label>
        <input id="new-password2" name="password2" type="password" autoComplete="new-password" minLength={8} required className="input" />
      </div>
      <FormMessage state={state} />
      <SubmitButton className="btn-ghost w-full">Zmień hasło</SubmitButton>
    </form>
  );
}

export function DeletionForm({ requested }: { requested: boolean }) {
  const [state, action] = useActionState(requestDeletionAction, undefined);
  if (requested || state?.success) {
    return <p className="alert-info">Prośba o usunięcie konta została wysłana. Organizator usunie Twoje dane.</p>;
  }
  return (
    <form
      action={action}
      onSubmit={(e) => {
        if (!confirm('Na pewno chcesz poprosić o usunięcie konta? Twoje wyniki znikną z rankingu.')) e.preventDefault();
      }}
    >
      <FormMessage state={state} />
      <SubmitButton className="btn-ghost w-full border-red-500/40 text-red-300" pendingText="Wysyłanie…">
        Poproś o usunięcie konta
      </SubmitButton>
    </form>
  );
}
