'use client';

import { useRef, useState } from 'react';

const SIZE = 256;

/** Crops the picked photo to a centred square and scales it to 256×256 in the browser. */
async function resize(file: File): Promise<string> {
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const el = new Image();
      el.onload = () => resolve(el);
      el.onerror = reject;
      el.src = url;
    });
    const side = Math.min(img.naturalWidth, img.naturalHeight);
    const canvas = document.createElement('canvas');
    canvas.width = SIZE;
    canvas.height = SIZE;
    const ctx = canvas.getContext('2d')!;
    ctx.drawImage(img, (img.naturalWidth - side) / 2, (img.naturalHeight - side) / 2, side, side, 0, 0, SIZE, SIZE);
    const webp = canvas.toDataURL('image/webp', 0.85);
    return webp.startsWith('data:image/webp') ? webp : canvas.toDataURL('image/jpeg', 0.85);
  } finally {
    URL.revokeObjectURL(url);
  }
}

export function AvatarPicker({
  presets,
  initialPreset,
  currentUpload,
}: {
  presets: readonly string[];
  initialPreset?: string | null;
  currentUpload?: string | null;
}) {
  const [mode, setMode] = useState<'preset' | 'upload' | 'keep'>(currentUpload ? 'keep' : 'preset');
  const [preset, setPreset] = useState(initialPreset && presets.includes(initialPreset) ? initialPreset : presets[0]);
  const [data, setData] = useState('');
  const [error, setError] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    setError('');
    const file = e.target.files?.[0];
    if (!file) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      setError('Wybierz zdjęcie JPG, PNG lub WEBP.');
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
      setError('Zdjęcie może mieć maksymalnie 8 MB.');
      return;
    }
    try {
      setData(await resize(file));
      setMode('upload');
    } catch {
      setError('Nie udało się wczytać zdjęcia.');
    }
  }

  const preview = mode === 'upload' ? data : mode === 'keep' ? currentUpload! : `/avatars/${preset}.svg`;

  return (
    <fieldset>
      <legend className="label">Awatar</legend>
      <input type="hidden" name="avatar_mode" value={mode} />
      <input type="hidden" name="avatar_preset" value={preset} />
      <input type="hidden" name="avatar_data" value={mode === 'upload' ? data : ''} />

      <div className="flex items-center gap-4">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={preview} alt="Podgląd awatara" width={72} height={72} className="h-[72px] w-[72px] rounded-full bg-line object-cover ring-2 ring-accent" />
        <div className="flex-1">
          <button type="button" className="btn-ghost w-full" onClick={() => fileRef.current?.click()}>
            Prześlij własne zdjęcie
          </button>
          <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={onFile} />
        </div>
      </div>
      {(mode === 'upload' || mode === 'keep') && (
        <p className="alert-info mt-3">
          Uwaga: przesłane zdjęcie będzie widoczne publicznie w rankingu i może ujawnić Twoją tożsamość. Jeśli wolisz zachować
          anonimowość, wybierz gotowy awatar poniżej.
        </p>
      )}
      {error && <p className="alert-error mt-3">{error}</p>}

      <p className="mb-2 mt-4 text-sm text-muted">…albo wybierz gotowy:</p>
      <div className="grid grid-cols-8 gap-2">
        {presets.map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => {
              setPreset(p);
              setMode('preset');
            }}
            aria-label={`Awatar ${p}`}
            aria-pressed={mode === 'preset' && preset === p}
            className={`aspect-square rounded-full p-0.5 transition ${mode === 'preset' && preset === p ? 'ring-2 ring-accent' : 'opacity-70 hover:opacity-100'}`}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={`/avatars/${p}.svg`} alt="" className="h-full w-full rounded-full" />
          </button>
        ))}
      </div>
    </fieldset>
  );
}
