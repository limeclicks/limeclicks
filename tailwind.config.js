module.exports = {
  content: [
    "./templates/**/*.html",
    "./templates/**/*.js",
    "./static/src/**/*.js",
    "./*/templates/**/*.html",  // Include app templates
  ],
  theme: {
    extend: {},
  },
  plugins: [require("daisyui")],
  daisyui: {
    themes: ["light", "dark", "cupcake", "corporate"],
  },
}