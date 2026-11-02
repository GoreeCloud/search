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
const INITIAL_STATUS = "Enter a query to search your local collection.";

async function checkCatalogReadiness() {
  try {
    const response = await fetch("/readyz", {cache: "no-store", credentials: "omit"});
    // Never overwrite user input, a live search, or a later search result.
    if (response.status === 503 && status.textContent === INITIAL_STATUS) {
      status.textContent = "Your private local catalog is unavailable. Initialize it before searching local documents.";
    }
  } catch (_) {
    // Readiness is advisory: keep existing local behavior without extra egress.
  }
}
void checkCatalogReadiness();

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
  if (!entry || typeof entry !== "object") return false;
  if (typeof entry.url !== "string" || typeof entry.title !== "string") return false;
  let url;
  try {
    url = new URL(entry.url);
  } catch (_) {
    return false;
  }
  if (url.protocol !== "https:" || url.username || url.password) return false;
  const article = document.createElement("article");
  article.className = "result-card";
  const label = document.createElement("p");
  label.className = "source";
  label.textContent = typeof entry.source === "string" ? entry.source : "Local";
  const title = document.createElement("h3");
  const link = document.createElement("a");
  link.href = url.href;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = entry.title;
  title.append(link);
  const text = document.createElement("p");
  text.className = "snippet";
  text.textContent = typeof entry.description === "string" ? entry.description : "";
  article.append(label, title, text);
  resultList.append(article);
  return true;
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
  resultList.setAttribute("aria-busy", "true");
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
    if (!Array.isArray(data.results)) throw new Error("Invalid search result format");
    const displayed = data.results.reduce((total, item) => total + Number(renderResult(item)), 0);
    counter.textContent = displayed + (displayed === 1 ? " result" : " results");
    const knownProviders = new Set(["brave", "searxng", "local"]);
    const warnings = Array.isArray(data.warnings) ? data.warnings : [];
    const failed = warnings
      .map(w => w && knownProviders.has(w.provider) ? w.provider : "")
      .filter(Boolean).join(", ");
    const summary = displayed
      ? displayed + (displayed === 1 ? " result found." : " results found.")
      : "No matches found. Try a different query or source.";
    status.textContent = failed ? summary + " Some selected sources were unavailable: " + failed + "." : summary;
  } catch (_err) {
    status.textContent = "Search is unavailable. Check the local service and source configuration.";
  } finally {
    resultList.setAttribute("aria-busy", "false");
    shareQuery.checked = false;
    sourceSelect.value = "local";
    sourceSelect.disabled = false;
    shareQuery.disabled = false;
    submit.disabled = false;
  }
});
