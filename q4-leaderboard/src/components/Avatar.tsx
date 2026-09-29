export function Avatar({ src, size = 40, className = '' }: { src: string; size?: number; className?: string }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt=""
      width={size}
      height={size}
      loading="lazy"
      decoding="async"
      className={`shrink-0 rounded-full bg-line object-cover ${className}`}
      style={{ width: size, height: size }}
    />
  );
}
