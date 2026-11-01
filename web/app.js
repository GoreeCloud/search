"use strict";
const form = document.getElementById("search-form");
const queryInput = document.getElementById("query");
const submit = document.getElementById("submit");
const resultList = document.getElementById("result-list");
const status = document.getElementById("status");
const counter = document.getElementById("counter");
const themeButton = document.getElementById("theme");
const sourceSelect = document.getElementById("source-select");
const shareQuery = document.getElementById("share-query");

async function discoverProviders() {
  try {
    const response = await fetch("/api/providers", {cache: "no-store", credentials: "omit"});
    if (!response.ok) return;
    const data = await response.json();
    for (const option of sourceSelect.options) {
      if (option.value === "local") continue;
      option.disabled = data.available?.[option.value] !== true;
      option.textContent = option.value === "brave"
        ? (option.disabled ? "Brave Search API — not configured" : "Brave Search API")
        : (option.disabled ? "Self-hosted SearXNG — not configured" : "Self-hosted SearXNG");
    }
  } catch (_) {
    // Failure never enables an external provider.
  }
}
void discoverProviders();
sourceSelect.addEventListener("change", () => {
  shareQuery.checked = false;
});

function setTheme(mode) {
  const safe = mode === "dark" ? "dark" : "light";
  document.documentElement.dataset.mode = safe;
  themeButton.textContent = safe === "dark" ? "Light mode" : "Dark mode";
  themeButton.setAttribute("aria-label", "Switch to " + (safe === "dark" ? "light" : "dark") + " theme");
}
setTheme(window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
themeButton.addEventListener("click", () => {
  setTheme(document.documentElement.dataset.mode === "dark" ? "light" : "dark");
});

function renderResult(entry) {
  const url = new URL(entry.url);
  if (url.protocol !== "https:" || url.username || url.password) return;
  const article = document.createElement("article");
  article.className = "result-card";
  const label = document.createElement("p");
  label.className = "source";
  label.textContent = entry.source;
  const title = document.createElement("h3");
  const link = document.createElement("a");
  link.href = url.href;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = entry.title;
  title.append(link);
  const text = document.createElement("p");
  text.className = "snippet";
  text.textContent = entry.description;
  article.append(label, title, text);
  resultList.append(article);
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  const query = queryInput.value.trim();
  if (!query) return;
  const chosen = sourceSelect.value;
  const external = chosen !== "local";
  if (external && !shareQuery.checked) {
    status.textContent = "Consent is required before sending a query to an external provider.";
    shareQuery.focus();
    return;
  }
  const request = {
    query,
    providers: external ? ["local", chosen] : ["local"],
    share_query: external && shareQuery.checked,
  };
  resultList.replaceChildren();
  status.textContent = external ? "Searching selected sources…" : "Searching your local collection…";
  counter.textContent = "";
  submit.disabled = true;
  sourceSelect.disabled = true;
  shareQuery.disabled = true;
  try {
    const response = await fetch("/api/search", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(request),
      credentials: "omit",
      cache: "no-store",
    });
    if (!response.ok) throw new Error("Search unavailable");
    const data = await response.json();
    data.results.forEach(renderResult);
    counter.textContent = data.count + (data.count === 1 ? " result" : " results");
    const failed = (data.warnings || []).map(w => w.provider).join(", ");
    status.textContent = failed ? "Some selected sources were unavailable: " + failed + "." :
      (data.count ? "" : "No matches found. Try a different query or source.");
  } catch (_err) {
    status.textContent = "Search is unavailable. Check the local service and source configuration.";
  } finally {
    shareQuery.checked = false;
    sourceSelect.value = "local";
    sourceSelect.disabled = false;
    shareQuery.disabled = false;
    submit.disabled = false;
  }
});
