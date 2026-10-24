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
    if (image.complete && image.getAttribute("src") && image.naturalWidth === 0) {
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
      let loaded = 0;
      let unavailable = 0;
      const update = () => {
        status.textContent = finished + " of " + eligible.length + " additional previews checked (" +
          loaded + " loaded, " + unavailable + " unavailable).";
        if (finished === eligible.length) {
          button.textContent = "Previews requested";
        }
      };
      const pump = () => {
        while (active < 4 && cursor < eligible.length) {
          const image = eligible[cursor++];
          active++;
          let done = false;
          let timer;
          const complete = (success) => {
            if (done) return;
            done = true;
            clearTimeout(timer);
            if (success) loaded++;
            else unavailable++;
            active--;
            finished++;
            update();
            pump();
          };
          image.addEventListener("load", () => complete(true), { once: true });
          image.addEventListener("error", () => complete(false), { once: true });
          image.loading = "eager";
          if (image.complete) complete(image.naturalWidth > 0);
          else {
            // A stalled proxy response is not a completed request. Abort the
            // browser image load before releasing its bounded concurrency slot.
            timer = setTimeout(() => {
              image.removeAttribute("src");
              image.closest("article.result-images")?.classList.add("goreecloud-thumbnail-unavailable");
              complete(false);
            }, 20000);
          }
        }
        update();
      };
      pump();
    }, { once: true });
  }
}
