module.exports = {
  content: [
    "./src/why/web/templates/**/*.html",
  ],
  safelist: [
    // Disposition pill classes — must be safelisted because they are
    // constructed dynamically by the disposition_classes() macro.
    'bg-blue-100', 'text-blue-700', 'dark:bg-blue-900/40', 'dark:text-blue-300', 'border-blue-200', 'dark:border-blue-800',
    'bg-emerald-100', 'text-emerald-700', 'dark:bg-emerald-900/40', 'dark:text-emerald-300', 'border-emerald-200', 'dark:border-emerald-800',
    'bg-amber-100', 'text-amber-700', 'dark:bg-amber-900/40', 'dark:text-amber-300', 'border-amber-200', 'dark:border-amber-800',
    'bg-rose-100', 'text-rose-700', 'dark:bg-rose-900/40', 'dark:text-rose-300', 'border-rose-200', 'dark:border-rose-800',
    'bg-zinc-100', 'text-zinc-600', 'dark:bg-zinc-800', 'dark:text-zinc-400', 'border-zinc-200', 'dark:border-zinc-700',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
    },
  },
  darkMode: 'media',
};
