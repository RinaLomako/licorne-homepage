/* Site-wide behaviour: mobile nav and the footer year.
   Loaded on every page. */
(function () {
  "use strict";

  // --- mobile navigation ---------------------------------------------------
  var toggle = document.querySelector(".nav-toggle");
  var nav = document.getElementById("nav");

  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      toggle.setAttribute("aria-expanded", String(open));
    });

    // Close the menu when a link is chosen, or on Escape.
    nav.addEventListener("click", function (e) {
      if (e.target.closest("a")) {
        nav.classList.remove("open");
        toggle.setAttribute("aria-expanded", "false");
      }
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && nav.classList.contains("open")) {
        nav.classList.remove("open");
        toggle.setAttribute("aria-expanded", "false");
        toggle.focus();
      }
    });
  }

  // --- footer year ---------------------------------------------------------
  // Uses a data attribute rather than an id, so a page that omits it is fine.
  var year = String(new Date().getFullYear());
  document.querySelectorAll("[data-year]").forEach(function (el) {
    el.textContent = year;
  });

  // --- email address -------------------------------------------------------
  // Assembled at runtime so the address is not sitting in the HTML source for
  // scrapers to harvest. Degrades to plain text if scripting is off.
  document.querySelectorAll("a.email").forEach(function (el) {
    var user = el.dataset.user;
    var domain = el.dataset.domain;
    if (!user || !domain) return;
    var address = user + "@" + domain;
    el.href = "mailto:" + address;
    el.textContent = address;
  });
})();
