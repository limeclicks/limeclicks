module.exports = {
  content: [
    "./templates/**/*.{html,js}",
    "./*/templates/**/*.{html,js}",  // Include app templates
    "./static/**/*.{html,js}",
    "./staticfiles/**/*.{html,js}",
    "./accounts/templates/**/*.{html,js}",
    "./services/templates/**/*.{html,js}",
    "./site_audit/templates/**/*.{html,js}",
    "./keywords/templates/**/*.{html,js}",
  ],
  theme: {
    extend: {},
  },
  plugins: [require("daisyui")],
  daisyui: {
    themes: ["light", "dark", "cupcake", "corporate", "business"],
    darkTheme: "dark",
    base: true,
    styled: true,
    utils: true,
    prefix: "",
    logs: true,
    themeRoot: ":root",
  },
}