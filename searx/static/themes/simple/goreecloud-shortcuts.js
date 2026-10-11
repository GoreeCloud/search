// Private local UI keyboard shortcut. Never stores terms or sends requests.
(() => {
  document.addEventListener('keydown', (event) => {
    if (event.key !== '/' || event.defaultPrevented || event.isComposing ||
        event.ctrlKey || event.metaKey || event.altKey || event.repeat) return;
    const origin = event.target;
    if (origin?.isContentEditable || origin?.closest?.('input, textarea, select, [contenteditable], [role="textbox"]')) return;
    const input = document.querySelector('form#search input#q');
    if (!input || input.disabled || !input.isConnected) return;
    event.preventDefault();
    input.focus();
    input.select();
  });
})();
