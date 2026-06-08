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
        // Tema da vitrine pública: tons de azul escuro, no mesmo tom do rodapé.
        bandeirantes: {
          'primary': '#1f2937',
          'primary-content': '#ffffff',
          'secondary': '#2563eb',
          'secondary-content': '#ffffff',
          'accent': '#3b82f6',
          'accent-content': '#ffffff',
          'neutral': '#1f2937',
          'neutral-content': '#e5e7eb',
          'base-100': '#ffffff',
          'base-200': '#f1f5f9',
          'base-300': '#e2e8f0',
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
      },
      {
        // Variante escura do tema da vitrine pública.
        'bandeirantes-dark': {
          'primary': '#3b82f6',
          'primary-content': '#0b1220',
          'secondary': '#60a5fa',
          'secondary-content': '#0b1220',
          'accent': '#22d3ee',
          'accent-content': '#0b1220',
          'neutral': '#0b1220',
          'neutral-content': '#e5e7eb',
          'base-100': '#1f2937',
          'base-200': '#161f2b',
          'base-300': '#374151',
          'base-content': '#e5e7eb',
          'info': '#0ea5e9',
          'info-content': '#0b1220',
          'success': '#22c55e',
          'success-content': '#0b1220',
          'warning': '#f59e0b',
          'warning-content': '#1c1917',
          'error': '#ef4444',
          'error-content': '#0b1220'
        }
      }
    ]
  }
}
