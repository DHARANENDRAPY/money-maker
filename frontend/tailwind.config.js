/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eef6ff',
          100: '#d9ebff',
          500: '#0284c7',
          600: '#0369a1',
          700: '#075985',
          900: '#082f49',
        },
        trade: {
          green: '#10b981',
          'green-bg': 'rgba(16, 185, 129, 0.12)',
          red: '#ef4444',
          'red-bg': 'rgba(239, 68, 68, 0.12)',
          amber: '#f59e0b',
          'amber-bg': 'rgba(245, 158, 11, 0.12)',
          blue: '#38bdf8',
          'blue-bg': 'rgba(56, 189, 248, 0.12)',
          card: '#111827',
          border: '#1f2937',
          hover: '#1e293b'
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      }
    },
  },
  plugins: [],
}
