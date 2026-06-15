/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0A0700",
          900: "#0F0900",
          800: "#1A1200",
          700: "#2A1E00",
          600: "#3D2C05",
          500: "#6B4E10",
          400: "#8B6820",
          300: "#C8A050",
          200: "#E8C878",
          100: "#FFFEF0",
        },
        accent: {
          400: "#FFE566",
          500: "#FFD700",
          600: "#C8860A",
        },
        amber: "#FF9500",
        solar: "#FFFEF0",
        kimi:   "#7BBFFF",
        gemma:  "#2DDDB0",
        sage:   "#A78BFA",
        hermes: "#E2E8F0",
      },
      fontFamily: {
        sans:    ['Rajdhani', '"Share Tech Mono"', 'sans-serif'],
        mono:    ['"Share Tech Mono"', 'monospace'],
        display: ['Rajdhani', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
