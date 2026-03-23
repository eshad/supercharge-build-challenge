/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          dark: '#0D2137',
          teal: '#00B5CC',
          gold: '#F5A623',
        },
      },
    },
  },
  plugins: [],
}
