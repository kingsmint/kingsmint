// Dark mode as the system's, on the app's page and in Fava (the server adds this script to Fava's pages): Web Awesome's
// class, and Fava's own switch for its colors that fava.css does not map
const km_scheme = matchMedia("(prefers-color-scheme: dark)");
const km_applyScheme = () => {
  document.documentElement.classList.toggle("wa-dark", km_scheme.matches);
  document.documentElement.dataset.colorScheme = km_scheme.matches ? "dark" : "light";
};
km_applyScheme();
km_scheme.addEventListener("change", km_applyScheme);
