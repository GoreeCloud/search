// GoreeCloud private Search: native, POST-only submitter destinations.
//
// Upstream SearXNG's search handler can suppress an empty search field and,
// for nonempty forms, replace native submitter actions with form.submit().
// Keep preview and single-provider actions independent of that interception.
const searchForm = document.getElementById('search');
if (searchForm) {
  document.addEventListener('click', (event) => {
    const preview = event.target.closest?.('.goreecloud-preview-trigger');
    if (!preview || preview.form !== searchForm || typeof searchForm.requestSubmit !== 'function') {
      return;
    }
    // Previewing with a blank query is allowed; this submits to the private
    // no-egress /preview endpoint, never directly to a search provider.
    event.preventDefault();
    event.stopPropagation();
    searchForm.requestSubmit(preview);
  }, {capture: true});

  document.addEventListener('submit', (event) => {
    const submitter = event.submitter;
    if (event.target !== searchForm || !submitter ||
        !(submitter.classList.contains('goreecloud-preview-trigger') ||
          submitter.classList.contains('goreecloud-home-source'))) {
      return;
    }
    const categories = document.getElementById('selected-categories');
    if (categories) {
      categories.value = Array.from(document.querySelectorAll('#categories_container button.category.selected'))
        .map(button => button.name.replace(/^category_/, ''))
        .join(',');
    }
    // Preserve native formaction/formmethod, blocking upstream submit routing.
    event.stopPropagation();
  }, {capture: true});
}
