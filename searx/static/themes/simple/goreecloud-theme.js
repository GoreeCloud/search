// Local UI-only appearance override. No remote requests or user identity.
const html = document.documentElement;
const button = document.querySelector('.goreecloud-theme-toggle');
const key = 'goreecloud-search-theme';
let override = null;
try {
  const stored = sessionStorage.getItem(key);
  if (stored === 'light' || stored === 'dark') override = stored;
} catch (_) { /* Continue without storage in restricted/private browsers. */ }
function darkActive() {
  if (override) return override === 'dark';
  if (html.classList.contains('theme-dark') || html.classList.contains('theme-black')) return true;
  if (html.classList.contains('theme-light')) return false;
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}
function apply() {
  if (override) {
    html.classList.remove('theme-dark', 'theme-black', 'theme-light', 'theme-auto');
    html.classList.add('theme-' + override);
  }
  // GC UI Foundations v1.0.1 resolves semantic colors on :root[data-gc-mode].
  // Keep that contract aligned with the existing private Search appearance and OS preference.
  const active = darkActive();
  html.setAttribute('data-gc-mode', active ? 'dark' : 'light');
  if (button) {
    button.setAttribute('aria-pressed', String(active));
    button.setAttribute('aria-label', active ? 'Switch to light mode' : 'Switch to dark mode');
    button.title = active ? 'Switch to light appearance' : 'Switch to dark appearance';
  }
}
apply();
if (button) button.addEventListener('click', () => {
  override = darkActive() ? 'light' : 'dark';
  try { sessionStorage.setItem(key, override); } catch (_) { /* Session only, best effort. */ }
  apply();
});
try { window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', apply); } catch (_) { /* Older browsers. */ }
