// GoreeCloud Development image results: on-demand, bounded thumbnail loading.
// Only image URLs already signed by the server's same-origin image proxy are used.
// No external browser tracking requests, background crawling or prefetch on Web pages.
const gallery = document.querySelector("#urls.goreecloud-image-results");
if (gallery) {
  const thumbnails = Array.from(gallery.querySelectorAll("article.result-images img.image_thumbnail"));
  for (const image of thumbnails) {
    const card = image.closest("article.result-images");
    image.addEventListener("error", () => card?.classList.add("goreecloud-thumbnail-unavailable"));
    image.addEventListener("load", () => card?.classList.remove("goreecloud-thumbnail-unavailable"));
    if (image.complete && image.currentSrc && image.naturalWidth === 0) {
      card?.classList.add("goreecloud-thumbnail-unavailable");
    }
  }

  const button = document.getElementById("goreecloud-image-load-all");
  const status = document.getElementById("goreecloud-image-load-status");
  if (button && status) {
    button.addEventListener("click", () => {
      const remaining = thumbnails.filter(
        (image) => image.loading === "lazy" && !image.complete
      );
      // Previews must be served through the existing signed, same-origin proxy.
      const eligible = remaining.filter((image) => {
        try {
          const src = new URL(image.currentSrc || image.src, location.href);
          return src.origin === location.origin && src.pathname === "/image_proxy";
        } catch {
          return false;
        }
      });
      button.disabled = true;
      button.textContent = "Loading previews…";
      let cursor = 0;
      let active = 0;
      let finished = 0;
      const update = () => {
        status.textContent = finished + " of " + eligible.length + " additional previews checked.";
        if (finished === eligible.length) {
          button.textContent = "Previews requested";
        }
      };
      const pump = () => {
        while (active < 4 && cursor < eligible.length) {
          const image = eligible[cursor++];
          active++;
          let done = false;
          const complete = () => {
            if (done) return;
            done = true;
            active--;
            finished++;
            update();
            pump();
          };
          image.addEventListener("load", complete, { once: true });
          image.addEventListener("error", complete, { once: true });
          image.loading = "eager";
          if (image.complete) complete();
          // A denied or stalled provider must never wedge the control indefinitely.
          else setTimeout(complete, 20000);
        }
        update();
      };
      pump();
    }, { once: true });
  }
}
