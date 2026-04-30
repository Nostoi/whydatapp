module.exports = {
  content: [
    "./src/why/web/templates/**/*.html",
  ],
  safelist: [
    // Pill tone classes — dynamically constructed as `pill-{{ tone }}` in pill.html
    // and `pill-{{ d }}` in filter_bar.html; Tailwind v3 purges @layer components too.
    'pill-doc', 'pill-setup', 'pill-experimental', 'pill-remove', 'pill-ignore',
    'pill-brand', 'pill-accent', 'pill-neutral',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      colors: {
        brand: {
          DEFAULT: 'var(--color-brand)',
          deep:    'var(--color-brand-deep)',
          soft:    'var(--color-brand-soft)',
          fg:      'var(--color-brand-fg)',
        },
        accent: {
          DEFAULT: 'var(--color-accent)',
          soft:    'var(--color-accent-soft)',
          fg:      'var(--color-accent-fg)',
        },
        surface: {
          bg:       'var(--color-bg)',
          muted:    'var(--color-bg-muted)',
          elevated: 'var(--color-bg-elevated)',
        },
        content: {
          DEFAULT: 'var(--color-fg)',
          muted:   'var(--color-fg-muted)',
          faint:   'var(--color-fg-faint)',
        },
        border: {
          DEFAULT: 'var(--color-border)',
          strong:  'var(--color-border-strong)',
        },
      },
    },
  },
  darkMode: 'media',
};
