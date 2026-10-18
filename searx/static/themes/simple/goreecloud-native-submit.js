// An explicit native-only POST must not be intercepted by upstream search JS.
// The regular Web/Images/Videos/News submit path remains untouched.
const nativeAction = document.querySelector('form#search button[name="native_source"]');
if (nativeAction) {
  nativeAction.addEventListener('click', (event) => {
    const input = document.querySelector('form#search input[name="q"]');
    if (!input) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const query = input.value.trim();
    if (!query) {
      input.focus();
      return;
    }
    const destination = new URL(nativeAction.getAttribute('formaction'), location.href);
    if (destination.origin !== location.origin || destination.pathname !== '/native-search') return;
    const form = document.createElement('form');
    form.method = 'post';
    form.action = destination.href;
    form.hidden = true;
    for (const [name, value] of [
      ['q', query],
      ['native_source', 'goreecloud-native-index'],
      ['category_general', '1'],
    ]) {
      const field = document.createElement('input');
      field.type = 'hidden';
      field.name = name;
      field.value = value;
      form.appendChild(field);
    }
    document.body.appendChild(form);
    HTMLFormElement.prototype.submit.call(form);
  }, {capture: true});
}
