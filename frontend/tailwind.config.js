/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: '#111317',
        card: '#171a20',
        ink: '#eceef3',
        muted: '#9ca3af',
        accent: '#14b8a6',
        accentSoft: '#0f766e',
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(20, 184, 166, 0.2), 0 16px 50px rgba(8, 145, 178, 0.12)',
      },
      keyframes: {
        rise: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        rise: 'rise 240ms ease-out both',
      },
    },
  },
  plugins: [],
}
