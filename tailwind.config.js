/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './accounts/templates/**/*.html',
    './core/templates/**/*.html',
    './communications/templates/**/*.html',
    './stock/templates/**/*.html',
    './operations/templates/**/*.html',
    './website/templates/**/*.html',
    './static/js/**/*.js',
    './**/*.py'
  ],
  theme: {
    extend: {}
  },
  plugins: [require('daisyui')],
  daisyui: {
    themes: [
      'light',
      'dark',
      'cupcake',
      {
        // Tema da vitrine pública, inspirado no logo verde da oficina.
        bandeirantes: {
          'primary': '#15803d',
          'primary-content': '#ffffff',
          'secondary': '#f59e0b',
          'secondary-content': '#1c1917',
          'accent': '#22c55e',
          'accent-content': '#052e16',
          'neutral': '#1f2937',
          'neutral-content': '#e5e7eb',
          'base-100': '#ffffff',
          'base-200': '#f3f4f6',
          'base-300': '#e5e7eb',
          'base-content': '#1f2937',
          'info': '#0ea5e9',
          'info-content': '#ffffff',
          'success': '#16a34a',
          'success-content': '#ffffff',
          'warning': '#f59e0b',
          'warning-content': '#1c1917',
          'error': '#dc2626',
          'error-content': '#ffffff'
        }
      }
    ]
  }
}
