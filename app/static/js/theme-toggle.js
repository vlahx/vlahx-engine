(() => {
  const themeToggle = document.getElementById("theme-toggle");
  const themeIcon = document.getElementById("theme-icon");
  const storedTheme = localStorage.getItem("siteTheme");
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const theme = storedTheme || (prefersDark ? "dark" : "light");
  document.documentElement.setAttribute("data-bs-theme", theme);

  const updateThemeButton = (next) => {
    if (!themeIcon) return;
    themeIcon.textContent = next === "dark" ? "☀️" : "🌙";
  };
  updateThemeButton(theme);

  if (!themeToggle) return;
  themeToggle.addEventListener("click", () => {
    const next =
      document.documentElement.getAttribute("data-bs-theme") === "dark"
        ? "light"
        : "dark";
    document.documentElement.setAttribute("data-bs-theme", next);
    localStorage.setItem("siteTheme", next);
    updateThemeButton(next);
  });
})();

