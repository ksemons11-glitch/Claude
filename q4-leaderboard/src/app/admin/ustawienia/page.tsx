import { SettingsForm } from '@/components/admin/SettingsForm';
import { getEvent } from '@/lib/data';

export default async function SettingsPage() {
  const e = await getEvent();
  return (
    <div className="max-w-xl">
      <h1 className="mb-4 text-2xl font-extrabold">Ustawienia eventu</h1>
      <div className="card p-5">
        <SettingsForm
          name={e.name}
          motivationText={e.motivationText}
          accessCodeRequired={e.accessCodeRequired}
          hasCode={Boolean(e.accessCodeHash)}
          registrationOpen={e.registrationOpen}
          isPublicLeaderboard={e.isPublicLeaderboard}
        />
      </div>
    </div>
  );
}
