// GoreeCloud private Search: POST-only provider preview and native source actions.
//
// Upstream search scripts may swallow empty searches or turn every submitter
// into a generic form.submit(), dropping the distinct /preview destination.
// A dedicated same-origin form keeps this local, no-egress preview reliable.
const searchForm = document.getElementById('search');
if (searchForm) {
  const syncCategories = () => {
    const categories = document.getElementById('selected-categories');
    if (categories) {
      categories.value = Array.from(document.querySelectorAll('#categories_container button.category.selected'))
        .map(button => button.name.replace(/^category_/, ''))
        .join(',');
    }
  };

  document.addEventListener('click', (event) => {
    const preview = event.target.closest?.('.goreecloud-preview-trigger');
    if (!preview || preview.form !== searchForm) return;

    event.preventDefault();
    event.stopImmediatePropagation();
    const destination = new URL(preview.formAction, location.href);
    if (destination.origin !== location.origin || !destination.pathname.endsWith('/preview') ||
        destination.search || destination.hash) {
      return;
    }

    syncCategories();
    const submission = document.createElement('form');
    submission.method = 'post';
    submission.action = destination.href;
    submission.hidden = true;
    for (const [name, value] of new FormData(searchForm)) {
      if (typeof value !== 'string') continue;
      const field = document.createElement('input');
      field.type = 'hidden';
      field.name = name;
      field.value = value;
      submission.append(field);
    }
    document.body.append(submission);
    // No search-provider dispatch. Bypass upstream submit handlers only to
    // post to our own guarded /preview route, preserving user form choices.
    HTMLFormElement.prototype.submit.call(submission);
  }, {capture: true});

  document.addEventListener('submit', (event) => {
    const submitter = event.submitter;
    if (event.target !== searchForm || !submitter ||
        !(submitter.classList.contains('goreecloud-preview-trigger') ||
          submitter.classList.contains('goreecloud-home-source'))) return;
    syncCategories();
    event.stopPropagation();
  }, {capture: true});
}
