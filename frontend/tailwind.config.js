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
        // NAVONMESH - deep forest green / teal government-tech palette.
        // Not a monochrome-green UI: slate neutrals carry the surfaces and
        // body text, green/teal is reserved for brand, active, GIS status and
        // success signalling.
        background: "#0B1F1A",
        surface: "#102A23",
        "surface-raised": "#12352D",
        "surface-card": "#0F2A24",
        "surface-border": "#1D453A",
        "surface-border-subtle": "#16362E",
        brand: {
          50: '#ecfdf5',
          400: '#34d399',
          500: '#10b981',
          600: '#059669',
          700: '#047857',
        },
        // The former indigo scale is retained as a token name so the existing
        // components keep working, but every shade now resolves to teal.
        indigo: {
          200: '#99F6E4',
          300: '#5EEAD4',
          400: '#2DD4BF',
          500: '#14B8A6',
          600: '#0D9488',
          700: '#0F766E',
          950: '#042F2E',
        },
        cyan: {
          400: '#5EEAD4',
          500: '#14B8A6',
          600: '#0D9488',
        },
        // Muted steel blue. Retained deliberately for data-layer identity
        // (legacy cadastre vs AI-corrected layer) so the map does not become
        // an undifferentiated green wash, but desaturated so it sits inside
        // the NAVONMESH palette instead of fighting it.
        blue: {
          300: '#9DB6C4',
          400: '#7397AC',
          500: '#547D95',
        },
        amber: {
          400: '#fbbf24',
          500: '#f59e0b',
        },
        rose: {
          400: '#fb7185',
          500: '#f43f5e',
          600: '#e11d48',
        }
      },
      fontFamily: {
        sans: ['Inter', 'Outfit', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'pulse-subtle': 'pulseSubtle 2.5s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        pulseSubtle: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.6' },
        }
      }
    },
  },
  plugins: [],
}
