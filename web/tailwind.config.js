/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html","./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50:"#E9F5FF",100:"#CCE9FF",200:"#99D2FF",300:"#66BCFF",400:"#33A5FF",
          500:"#0D8FFF",600:"#0074DB",700:"#0059A8",800:"#003E75",900:"#002542"
        }
      },
      fontFamily: {
        display: ["Orbitron","ui-sans-serif","system-ui"],
        body: ["Inter","ui-sans-serif","system-ui"]
      }
    }
  },
  plugins: []
}
