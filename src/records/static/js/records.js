function primarySearch() {
  return document.querySelector("[data-primary-search]");
}

function firstResultLink() {
  return document.querySelector(".archive-result .entry-title");
}

document.addEventListener("keydown", (event) => {
  const active = document.activeElement;
  const isTyping = active instanceof HTMLInputElement || active instanceof HTMLTextAreaElement || active instanceof HTMLSelectElement;
  const search = primarySearch();

  if (event.key === "/" && !isTyping && search) {
    event.preventDefault();
    search.focus();
    search.select();
    return;
  }

  if (event.key === "Escape" && active === search) {
    search.value = "";
    search.dispatchEvent(new Event("search", { bubbles: true }));
    return;
  }

  if (event.key === "Enter" && active === search && search.value.trim()) {
    const link = firstResultLink();
    if (link) {
      event.preventDefault();
      link.click();
    }
  }
});
