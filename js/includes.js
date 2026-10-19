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

loadIncludes();