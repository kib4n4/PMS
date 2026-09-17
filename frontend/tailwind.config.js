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
        // Ledger palette — financial, auditable. Neutrals
        ink: {
          50: '#f5f8f7',
          100: '#e6eee9',
          200: '#cddfda',
          300: '#b3c3bf',
          400: '#97a7a1',
          500: '#7a8a83',
          600: '#62726d',
          700: '#4a5c58',
          800: '#364745',
          900: '#132420',
        },
        mist: {
          50: '#EEF2F0',
          100: '#e3e7e5',
          200: '#cad2cf',
          300: '#b1bbb7',
          400: '#97a39e',
          500: '#7a8982',
          600: '#62726d',
          700: '#4a5c58',
          800: '#364745',
          900: '#223330',
        },
        surface: {
          50: '#ffffff',
          100: '#fafbfb',
        },
        border: {
          DEFAULT: '#DCE3DF',
          200: '#c5cdc9',
          300: '#adb5b0',
        },

        // Functional ledger colors
        teal: {
          50: '#f0fdfb',
          100: '#ccfbf1',
          200: '#99f6e4',
          300: '#5EEAD4',
          400: '#26b3a7',
          500: '#0F6B5C',
          600: '#0d5f4b',
          700: '#0b513f',
          800: '#093f30',
          900: '#072e22',
        },
        amber: {
          50: '#fffbeb',
          100: '#fef3c7',
          200: '#fde68a',
          300: '#fcd34d',
          400: '#fbbf24',
          500: '#C98A2C',
          600: '#b47d24',
          700: '#9d681c',
          800: '#8a5717',
          900: '#733f0f',
        },
        rust: {
          50: '#fff1ee',
          100: '#ffe4dc',
          200: '#ffbfae',
          300: '#ff8779',
          400: '#f85350',
          500: '#B4472A',
          600: '#a03e25',
          700: '#8a341f',
          800: '#722a19',
          900: '#5a2013',
        },
        gold: {
          50: '#fffbeb',
          100: '#fef9db',
          200: '#feebc8',
          300: '#fdd297',
          400: '#fbc35b',
          500: '#D9A441',
          600: '#c3913a',
          700: '#a87b31',
          800: '#8a6328',
          900: '#6d4e1f',
        },
      },

      fontFamily: {
        sans: ['var(--font-sans)', '-apple-system', 'BlinkMacSystemFont', 'system-ui', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['var(--font-mono)', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },

      // Shared visual primitives
      boxShadow: {
        ledger: '0 1px 3px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.02)',
      },
    },
  },
  plugins: [],
}
