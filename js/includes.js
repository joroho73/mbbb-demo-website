// This script dynamically loads the header and footer includes into the page.
async function loadIncludes() {
  const includes = [
    ["#site-header", "/includes/header.html"],
    ["#site-footer", "/includes/footer.html"]
  ];

  try {
    for (const [selector, path] of includes) {
      const placeholder = document.querySelector(selector);

      if (!placeholder) {
        throw new Error(`Placeholder not found: ${selector}`);
      }

      const response = await fetch(path);

      if (!response.ok) {
        throw new Error(`Could not load ${path}: ${response.status}`);
      }

      placeholder.outerHTML = await response.text();
    }
  } catch (error) {
    console.error("Could not load the shared page includes:", error);
  }
}

// Menu toggle functionality
async function setupMenuToggle() {
  const menuToggle = document.querySelector(".menu-toggle");
  const siteHeader = document.querySelector(".site-header");

  if (!menuToggle || !siteHeader) {
    console.error("Menu button or site header not found.");
    return;
  }

  menuToggle.addEventListener("click", () => {
    const isOpen = siteHeader.classList.toggle("menu-open");
    menuToggle.setAttribute("aria-expanded", isOpen);
    menuToggle.setAttribute("aria-label", isOpen ? "Close menu" : "Open menu");
  });
}

loadIncludes().then(setupMenuToggle)
