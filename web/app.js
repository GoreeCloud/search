"use strict";
const form = document.getElementById("search-form");
const queryInput = document.getElementById("query");
const submit = document.getElementById("submit");
const resultList = document.getElementById("result-list");
const status = document.getElementById("status");
const counter = document.getElementById("counter");
const themeButton = document.getElementById("theme");

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
  resultList.replaceChildren();
  status.textContent = "Searching your local collection…";
  counter.textContent = "";
  submit.disabled = true;
  try {
    const response = await fetch("/api/search", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({query}),
      credentials: "omit",
      cache: "no-store",
    });
    if (!response.ok) throw new Error("Search unavailable");
    const data = await response.json();
    data.results.forEach(renderResult);
    counter.textContent = data.count + (data.count === 1 ? " result" : " results");
    status.textContent = data.count ? "" : "No matches in your local collection. Try different keywords.";
  } catch (_err) {
    status.textContent = "The local search index is unavailable. Check its setup and try again.";
  } finally {
    submit.disabled = false;
  }
});
