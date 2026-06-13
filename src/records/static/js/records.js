function primarySearch() {
  return document.querySelector("[data-primary-search]");
}

function firstResultLink() {
  return document.querySelector(".command-search-results .picker-row, .search-picker .picker-row, .archive-result .entry-title");
}

function searchModal() {
  return document.querySelector("[data-search-modal]");
}

function searchResults() {
  return document.querySelector(".command-search-results");
}

function colorModeButtons() {
  return Array.from(document.querySelectorAll("[data-theme-mode-option]"));
}

const supportedThemes = ["default", "tokyonight", "gruvbox", "ravelry", "miasma", "zen"];

const themeColors = {
  default: { dark: "#151925", light: "#f4f7fb" },
  tokyonight: { dark: "#24283b", light: "#dfe7f5" },
  gruvbox: { dark: "#282828", light: "#fbf1c7" },
  ravelry: { dark: "#191c27", light: "#f3f4f0" },
  miasma: { dark: "#1c1c1c", light: "#ded8c2" },
  zen: { dark: "#000000", light: "#ffffff" },
};

function readPreference(key, fallback = "") {
  try {
    return localStorage.getItem(key) || fallback;
  } catch {
    return fallback;
  }
}

function writePreference(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Preferences are optional; the current page can still update without storage.
  }
}

function currentColorMode() {
  return document.documentElement.dataset.colorMode === "light" ? "light" : "dark";
}

function currentTheme() {
  const theme = document.documentElement.dataset.theme || readPreference("records-theme", "default");
  return supportedThemes.includes(theme) ? theme : "default";
}

function setThemePreferences({ mode = currentColorMode(), theme = currentTheme() } = {}) {
  const nextMode = mode === "light" ? "light" : "dark";
  const nextTheme = supportedThemes.includes(theme) ? theme : "default";
  document.documentElement.dataset.theme = nextTheme;
  document.documentElement.dataset.colorMode = nextMode;
  writePreference("records-color-mode", nextMode);
  writePreference("records-theme", nextTheme);
  colorModeButtons().forEach((button) => {
    const isActive = button.getAttribute("data-theme-mode-option") === nextMode;
    button.setAttribute("aria-pressed", String(isActive));
  });
  const schemeSelect = document.querySelector("[data-theme-scheme]");
  if (schemeSelect) {
    schemeSelect.value = nextTheme;
  }
  const themeMeta = document.querySelector("meta[name='theme-color']");
  if (themeMeta) {
    themeMeta.setAttribute("content", themeColors[nextTheme][nextMode]);
  }
}

function floatingActions() {
  return document.querySelector("[data-floating-actions]");
}

function setFloatingActionsOpen(isOpen) {
  const actions = floatingActions();
  const toggle = document.querySelector("[data-floating-actions-toggle]");
  if (!actions || !toggle) return;
  actions.classList.toggle("open", isOpen);
  toggle.setAttribute("aria-expanded", String(isOpen));
  toggle.setAttribute("aria-label", isOpen ? "Close quick actions" : "Open quick actions");
}

function setMenuOpen(isOpen) {
  const menu = document.querySelector("[data-menu]");
  const menuToggle = document.querySelector("[data-menu-toggle]");
  const menuBackdrop = document.querySelector("[data-menu-backdrop]");
  if (!menu || !menuToggle) return;
  menu.classList.toggle("open", isOpen);
  menuToggle.setAttribute("aria-expanded", String(isOpen));
  if (menuBackdrop) {
    menuBackdrop.classList.toggle("open", isOpen);
  }
}

function closeSearchModal({ clear = false } = {}) {
  const modal = searchModal();
  const search = primarySearch();
  const results = searchResults();
  if (!modal) return;

  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("search-modal-open");

  if (clear && search) {
    search.value = "";
  }
  if (clear && results) {
    results.innerHTML = "";
  }
}

function openSearchModal({ selectQuery = true } = {}) {
  const modal = searchModal();
  const search = primarySearch();
  if (!modal || !search) return;

  const wasOpen = modal.classList.contains("open");
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("search-modal-open");

  if (!wasOpen || document.activeElement !== search) {
    window.setTimeout(() => {
      search.focus();
      if (selectQuery) {
        search.select();
      }
      if (search.value.trim()) {
        search.dispatchEvent(new Event("input", { bubbles: true }));
      }
    }, 0);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const menuToggle = document.querySelector("[data-menu-toggle]");
  const menu = document.querySelector("[data-menu]");
  const menuBackdrop = document.querySelector("[data-menu-backdrop]");
  const search = primarySearch();

  setThemePreferences();

  if (menuToggle && menu) {
    menuToggle.addEventListener("click", () => {
      setMenuOpen(!menu.classList.contains("open"));
    });

    if (menuBackdrop) {
      menuBackdrop.addEventListener("click", () => setMenuOpen(false));
    }

    menu.addEventListener("click", (event) => {
      const themeModeButton = event.target.closest("[data-theme-mode-option]");
      if (themeModeButton) {
        event.preventDefault();
        setThemePreferences({ mode: themeModeButton.getAttribute("data-theme-mode-option") });
        return;
      }

      const themeSchemeSelect = event.target.closest("[data-theme-scheme]");
      if (themeSchemeSelect) {
        return;
      }

      const searchLink = event.target.closest("[data-open-search]");
      if (searchLink) {
        event.preventDefault();
        setMenuOpen(false);
        openSearchModal();
        return;
      }
      if (event.target.closest("a, button")) {
        setMenuOpen(false);
      }
    });
  }

  const schemeSelect = document.querySelector("[data-theme-scheme]");
  if (schemeSelect) {
    schemeSelect.addEventListener("change", () => {
      setThemePreferences({ theme: schemeSelect.value });
    });
  }

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;

    const searchTrigger = target.closest("[data-open-search]");
    if (searchTrigger) {
      event.preventDefault();
      setMenuOpen(false);
      setFloatingActionsOpen(false);
      openSearchModal();
      return;
    }

    const floatingToggle = target.closest("[data-floating-actions-toggle]");
    if (floatingToggle) {
      event.preventDefault();
      const actions = floatingActions();
      setFloatingActionsOpen(!actions || !actions.classList.contains("open"));
      return;
    }

    const floatingAction = target.closest(".floating-action-item");
    if (floatingAction) {
      setFloatingActionsOpen(false);
      return;
    }

    const actions = floatingActions();
    if (actions && actions.classList.contains("open") && !target.closest("[data-floating-actions]")) {
      setFloatingActionsOpen(false);
      return;
    }

    if (target.closest("[data-close-search]")) {
      closeSearchModal({ clear: true });
      return;
    }

    const lookupResult = target.closest("[data-lookup-source-url]");
    if (lookupResult) {
      const sourceInput = document.querySelector("#source-url");
      const imageInput = document.querySelector("#image-url");
      const sourceUrl = lookupResult.getAttribute("data-lookup-source-url") || "";
      const imageUrl = lookupResult.getAttribute("data-lookup-image-url") || "";
      if (sourceInput) {
        sourceInput.value = sourceUrl;
        sourceInput.dispatchEvent(new Event("input", { bubbles: true }));
      }
      if (imageInput && imageUrl) {
        imageInput.value = imageUrl;
        imageInput.dispatchEvent(new Event("input", { bubbles: true }));
      }
    }
  });

  if (search) {
    search.addEventListener(
      "search",
      (event) => {
        const modal = searchModal();
        if (modal && modal.classList.contains("open") && !search.value.trim()) {
          event.stopPropagation();
          closeSearchModal({ clear: true });
        }
      },
      true
    );
  }
});

document.addEventListener("htmx:afterSwap", (event) => {
  if (event.target && event.target.matches && event.target.matches(".command-search-results")) {
    openSearchModal({ selectQuery: false });
  }
});

document.addEventListener("keydown", (event) => {
  const active = document.activeElement;
  const search = primarySearch();
  const modal = searchModal();
  const modalIsOpen = Boolean(modal && modal.classList.contains("open"));

  if (event.key === "Escape" && modalIsOpen) {
    event.preventDefault();
    event.stopPropagation();
    closeSearchModal({ clear: true });
    setFloatingActionsOpen(false);
    return;
  }

  if (event.key === "Escape") {
    setMenuOpen(false);
    setFloatingActionsOpen(false);
  }

  if (event.key === "Enter" && active === search && modalIsOpen && search.value.trim()) {
    const link = firstResultLink();
    if (link) {
      event.preventDefault();
      link.click();
    }
  }
}, true);
