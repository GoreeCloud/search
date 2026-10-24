// GoreeCloud Development image results: on-demand, bounded thumbnail loading.
// Only image URLs already signed by the server's same-origin image proxy are used.
// No external browser tracking requests, background crawling or prefetch on Web pages.
const gallery = document.querySelector("#urls.goreecloud-image-results");
if (gallery) {
  const isSignedProxyImage = (image) => {
    // A previously selected currentSrc is not proof of what the browser will
    // fetch next. This is only a syntax gate: the server validates the HMAC.
    // Verify the actual src and reject srcset overrides entirely.
    const source = image.getAttribute("src");
    if (!source || image.hasAttribute("srcset")) return false;
    try {
      const url = new URL(source, location.href);
      return url.origin === location.origin && url.pathname === "/image_proxy" &&
        !!url.searchParams.get("url") && !!url.searchParams.get("h");
    } catch {
      return false;
    }
  };
  const thumbnails = Array.from(gallery.querySelectorAll("article.result-images img.image_thumbnail"));
  for (const image of thumbnails) {
    const card = image.closest("article.result-images");
    if (!isSignedProxyImage(image)) {
      // Never leave an unintended browser-direct image URL in a private
      // results gallery, including a card with an empty proxy src.
      image.removeAttribute("src");
      card?.classList.add("goreecloud-thumbnail-unavailable");
    }
    image.addEventListener("error", () => card?.classList.add("goreecloud-thumbnail-unavailable"));
    // A stale load event can arrive after the 20-second timeout removed src.
    // In that case the unavailable tile must remain visibly labeled.
    image.addEventListener("load", () => {
      if (isSignedProxyImage(image) && image.naturalWidth > 0) {
        card?.classList.remove("goreecloud-thumbnail-unavailable");
      }
    });
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
      const eligible = remaining.filter(isSignedProxyImage);
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
          if (!isSignedProxyImage(image)) {
            // The DOM can change between selection and dispatch. Never set
            // eager on a source that no longer has a signed local proxy URL.
            image.removeAttribute("src");
            image.closest("article.result-images")?.classList.add("goreecloud-thumbnail-unavailable");
            unavailable++;
            finished++;
            continue;
          }
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
