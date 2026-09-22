/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Ledger palette v2 — retuned from a marketing near-black+accent
        // combo to the physical objects this product replaces: columnar
        // ledger paper, thermal receipt ink, a brass date-stamp, a
        // correction-stamp red. See design plan for the full rationale.
        ink: {
          // 'ink' — receipt-print near-black, warm-green cast, not pure black.
          50: '#F4F6F3',
          100: '#E6EBE4',
          200: '#CDD6C9',
          300: '#AFBCA8',
          400: '#8B9A84',
          500: '#6B7A64',
          600: '#525E4C',
          700: '#3D473A',
          800: '#272E24',
          900: '#181A17',
        },
        mist: {
          // 'paper' — pale sage-tinted ledger stock (Boorum & Pease
          // columnar-pad green), deliberately cool, never cream.
          50: '#EAF0E7',
          100: '#DEE7DA',
          200: '#C9D6C4',
          300: '#B0C2A9',
          400: '#96AC8E',
          500: '#7C9373',
          600: '#63795C',
          700: '#4A5C45',
          800: '#33402F',
          900: '#1F2A1C',
        },
        surface: {
          // Card/table surfaces — a hair lighter than the page paper.
          50: '#FEFEFC',
          100: '#F7FAF5',
        },
        border: {
          // 'rule' — the faint printed guideline on ledger paper.
          DEFAULT: '#D5DFD0',
          200: '#C3D0BD',
          300: '#B0C0A9',
        },

        // Functional ledger colors
        teal: {
          // 'confirmed' — money moved. Deliberately a deep forest green,
          // shifted away from M-Pesa's own bright grass-green so it
          // reads as Ledger's color, not a borrowed brand.
          50: '#EAF5EF',
          100: '#CDE8D9',
          200: '#9CD1B5',
          300: '#66B48D',
          400: '#39946C',
          500: '#155E3F',
          600: '#124F35',
          700: '#0F412C',
          800: '#0B3222',
          900: '#082518',
        },
        amber: {
          // Secondary warm accent — pending/in-progress states.
          // Harmonized with 'gold' rather than a generic yellow.
          50: '#FBF4E7',
          100: '#F3E2BC',
          200: '#E7C989',
          300: '#D6AC59',
          400: '#C1953C',
          500: '#B3872E',
          600: '#977224',
          700: '#7A5C1C',
          800: '#5E4715',
          900: '#42320E',
        },
        rust: {
          // 'void' — correction-stamp ink. Brick, not alarm-red.
          50: '#FBEDE9',
          100: '#F2CFC5',
          200: '#E4A797',
          300: '#D27C66',
          400: '#B85843',
          500: '#8C3A2B',
          600: '#763023',
          700: '#5F271C',
          800: '#481D15',
          900: '#33140F',
        },
        gold: {
          // 'stamp' — brass date-stamp / shilling-coin tone. Platform
          // fees, secondary emphasis.
          50: '#FBF4E7',
          100: '#F3E2BC',
          200: '#E7C989',
          300: '#D6AC59',
          400: '#C1953C',
          500: '#A9791F',
          600: '#8E661A',
          700: '#725215',
          800: '#573F10',
          900: '#3D2C0B',
        },
      },

      fontFamily: {
        // UI text — Public Sans: the US government's own open-source
        // type system, built for forms/official documents. On-theme for
        // a product that files KRA returns and keeps an audit log.
        sans: ['var(--font-sans)', '-apple-system', 'BlinkMacSystemFont', 'system-ui', 'Segoe UI', 'Roboto', 'sans-serif'],
        // Display/numerals — Fraunces: wide optical-size range, real
        // oldstyle/tabular figure design. Large KES figures get a
        // typeface built for numbers, not a sans doing double duty.
        serif: ['var(--font-display)', 'Georgia', 'Cambria', 'Times New Roman', 'serif'],
        mono: ['var(--font-mono)', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },

      fontSize: {
        'display-hero': ['3.25rem', { lineHeight: '1.05', letterSpacing: '-0.01em' }],
        'display-kpi': ['1.875rem', { lineHeight: '1.1', letterSpacing: '-0.005em' }],
      },

      // Shared visual primitives
      boxShadow: {
        ledger: '0 1px 3px rgba(24, 26, 23, 0.05), 0 1px 2px rgba(24, 26, 23, 0.03)',
      },
    },
  },
  plugins: [],
}
