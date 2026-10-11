// GoreeCloud private Search: preserve a submit button's native POST destination.
// Upstream SearXNG search.ts intercepts all form submits and calls form.submit(),
// which discards submitter.formAction. Limit this bridge to the preview button.
const searchForm = document.getElementById('search');
if (searchForm) {
  document.addEventListener('submit', (event) => {
    if (event.target !== searchForm || !event.submitter?.classList.contains('goreecloud-preview-trigger')) {
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
