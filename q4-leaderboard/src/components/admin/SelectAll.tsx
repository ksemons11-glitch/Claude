'use client';

export function SelectAll({ form }: { form: string }) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <input
        type="checkbox"
        className="h-5 w-5 accent-accent"
        onChange={(e) => {
          document
            .querySelectorAll<HTMLInputElement>(`input[type=checkbox][name=ids][form=${form}]`)
            .forEach((cb) => (cb.checked = e.target.checked));
        }}
      />
      Zaznacz wszystkie
    </label>
  );
}
