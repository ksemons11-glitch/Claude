import { CreateBackupForm, MaintenanceForm, RestoreBackupForm, RestoreUploadForm } from '@/components/admin/SafetyForms';
import { listBackups } from '@/lib/backup';
import { getEvent } from '@/lib/data';
import { formatFull } from '@/lib/time';

const kb = (n: number) => `${Math.max(1, Math.round(Number(n) / 1024))} KB`;

export default async function SafetyPage() {
  const [event, backups] = await Promise.all([getEvent(), listBackups()]);
  return (
    <div className="max-w-3xl space-y-8">
      <section>
        <h1 className="text-2xl font-extrabold">Tryb serwisowy</h1>
        <p className="mb-4 mt-1 text-sm text-muted">
          Zamroź stronę na czas zmian (np. korekt, przywracania kopii lub wdrażania nowej wersji). Admini zawsze mają pełny dostęp.
        </p>
        <div className="card p-5">
          <MaintenanceForm mode={event.maintenanceMode} message={event.maintenanceMessage} />
        </div>
      </section>

      <section>
        <h2 className="text-xl font-extrabold">Kopie zapasowe</h2>
        <p className="mb-4 mt-1 text-sm text-muted">
          Kopia raz na dobę robi się sama. Zawiera konta, wyniki, tygodnie, ustawienia, dziennik zmian i zgłoszenia korekt (bez zdjęć
          awatarów). Przechowujemy {40} najnowszych. Raz w tygodniu pobierz kopię na dysk — plik zawiera dane osobowe, trzymaj go bezpiecznie.
        </p>
        <div className="card p-5">
          <CreateBackupForm />
        </div>

        <ul className="card mt-4 divide-y divide-line">
          {backups.length === 0 && <li className="px-4 py-6 text-center text-sm text-muted">Brak kopii — pierwsza powstanie automatycznie.</li>}
          {backups.map((b) => (
            <li key={b.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
              <div className="min-w-0">
                <div className="font-semibold">{formatFull(b.createdAt)}</div>
                <div className="text-xs text-muted">
                  {b.reason}
                  {b.by && <> · {b.by}</>} · {b.summary} · {kb(b.size)}
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <a href={`/api/admin/backup?id=${b.id}`} className="btn-sm border border-line">Pobierz</a>
                <RestoreBackupForm id={b.id} />
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="text-xl font-extrabold">Przywróć z pliku</h2>
        <p className="mb-4 mt-1 text-sm text-muted">Wgraj plik kopii pobrany wcześniej na dysk (.json). Obecne dane zostaną zastąpione.</p>
        <div className="card p-5">
          <RestoreUploadForm />
        </div>
      </section>
    </div>
  );
}
