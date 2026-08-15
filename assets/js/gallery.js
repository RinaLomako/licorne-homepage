/* Lightbox for the gallery pages.
   Grid thumbnails are small responsive WebP; opening one loads the large
   full-quality file, which is why the thumbnail stays visible until it lands. */
(function () {
  "use strict";

  var shots = Array.prototype.slice.call(document.querySelectorAll(".shot-open"));
  if (!shots.length) return;

  var box = document.getElementById("lightbox");
  var img = document.getElementById("lbImg");
  var cap = document.getElementById("lbCaption");
  var btnClose = document.getElementById("lbClose");
  var btnPrev = document.getElementById("lbPrev");
  var btnNext = document.getElementById("lbNext");
  if (!box || !img) return;

  var current = -1;
  var lastFocus = null;

  function preload(i) {
    if (i < 0 || i >= shots.length) return;
    var src = shots[i].dataset.full;
    if (src) new Image().src = src;
  }

  function show(i) {
    if (i < 0) i = shots.length - 1;
    if (i >= shots.length) i = 0;
    current = i;

    var el = shots[i];
    var thumb = el.querySelector("img");

    img.src = el.dataset.full;
    img.alt = thumb ? thumb.alt : "";
    cap.textContent = el.dataset.caption || "";
    cap.hidden = !el.dataset.caption;

    // Warm the neighbours so paging feels instant.
    preload(i + 1);
    preload(i - 1);
  }

  function open(i) {
    lastFocus = document.activeElement;
    show(i);
    box.classList.add("open");
    box.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    btnClose.focus();
  }

  function close() {
    box.classList.remove("open");
    box.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    img.src = "";
    img.alt = "";
    cap.textContent = "";
    current = -1;
    if (lastFocus) lastFocus.focus();
  }

  function isOpen() {
    return box.classList.contains("open");
  }

  shots.forEach(function (el, i) {
    el.addEventListener("click", function () { open(i); });
  });

  btnClose.addEventListener("click", close);
  if (btnPrev) btnPrev.addEventListener("click", function () { show(current - 1); });
  if (btnNext) btnNext.addEventListener("click", function () { show(current + 1); });

  // Clicking the backdrop closes; clicking the photo itself does not.
  box.addEventListener("click", function (e) {
    if (e.target === box || e.target.classList.contains("lb-stage")) close();
  });

  document.addEventListener("keydown", function (e) {
    if (!isOpen()) return;
    if (e.key === "Escape") { close(); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); show(current - 1); }
    else if (e.key === "ArrowRight") { e.preventDefault(); show(current + 1); }
  });

  // --- swipe ---------------------------------------------------------------
  // Horizontal drags page between photos; a mostly-vertical drag is ignored so
  // it does not fight with scrolling or pinch-zoom.
  var startX = 0, startY = 0, tracking = false;

  box.addEventListener("touchstart", function (e) {
    if (e.touches.length !== 1) { tracking = false; return; }
    tracking = true;
    startX = e.touches[0].clientX;
    startY = e.touches[0].clientY;
  }, { passive: true });

  box.addEventListener("touchend", function (e) {
    if (!tracking) return;
    tracking = false;
    var t = e.changedTouches[0];
    var dx = t.clientX - startX;
    var dy = t.clientY - startY;
    if (Math.abs(dx) > 55 && Math.abs(dx) > Math.abs(dy) * 1.5) {
      show(current + (dx < 0 ? 1 : -1));
    }
  }, { passive: true });
})();
