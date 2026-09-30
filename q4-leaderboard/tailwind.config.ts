import type { Config } from 'tailwindcss';

// Brand colours live as CSS variables in src/app/globals.css (":root" block) —
// change them there to re-theme the whole app.
const v = (name: string) => `rgb(var(--c-${name}) / <alpha-value>)`;

export default {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: v('bg'),
        card: v('card'),
        line: v('line'),
        muted: v('muted'),
        fg: v('fg'),
        accent: v('accent'),
        'accent-2': v('accent-2'),
        header: v('header'),
        'header-fg': v('header-fg'),
        'accent-fg': v('accent-fg'),
        gold: v('gold'),
        silver: v('silver'),
        bronze: v('bronze'),
      },
      fontFamily: {
        sans: ['var(--font-body)', 'system-ui', 'sans-serif'],
        display: ['var(--font-display)', 'var(--font-body)', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
} satisfies Config;
