/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './accounts/templates/**/*.html',
    './core/templates/**/*.html',
    './communications/templates/**/*.html',
    './stock/templates/**/*.html',
    './operations/templates/**/*.html',
    './static/js/**/*.js',
    './**/*.py'
  ],
  theme: {
    extend: {}
  },
  plugins: [require('daisyui')],
  daisyui: {
    themes: ['light', 'dark', 'cupcake']
  }
}
