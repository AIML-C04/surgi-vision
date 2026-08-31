/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          600: '#475569', // Slate 600
          900: '#0f172a', // Slate 900
          800: '#1e293b', // Slate 800
          700: '#334155', // Slate 700
        },
        primary: {
          500: '#3b82f6', // Blue 500
          600: '#2563eb', // Blue 600
        },
        accent: {
          500: '#8b5cf6', // Violet 500
        }
      }
    },
  },
  plugins: [],
}
