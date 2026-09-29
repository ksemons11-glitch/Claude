import type { Config } from 'tailwindcss';

export default {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0b0f1a',
        card: '#131a2a',
        line: '#222c42',
        muted: '#8b97b3',
        accent: '#7cf29c',
        gold: '#f5c542',
        silver: '#c7d0dd',
        bronze: '#d98b52',
      },
    },
  },
  plugins: [],
} satisfies Config;
