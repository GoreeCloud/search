// GoreeCloud private Search: preserve a submit button's native POST destination.
// Upstream SearXNG search.ts intercepts all form submits and calls form.submit(),
// which discards submitter.formAction and submitter name/value. The bridge
// handles only private preview and homepage single-provider submitters.
const searchForm = document.getElementById('search');
if (searchForm) {
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
    // Do not preventDefault: let the browser honor formaction and formmethod.
    // Capture runs before SearXNG's form-level submit listener.
    event.stopPropagation();
  }, {capture: true});
}
