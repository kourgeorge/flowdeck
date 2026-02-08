/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      maxWidth: {
        'layout': '1800px',
      },
      colors: {
        'buy': '#10b981',
        'sell': '#ef4444',
        'hold': '#f59e0b',
      },
    },
  },
  plugins: [],
}

