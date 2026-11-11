/* Builds the gallery cloud from v2/order.txt plus the galleries' manifests.
   Rendering happens in the browser on purpose: changing the order means
   editing one plain-text file, with no build step and no code. */
(function () {
  "use strict";

  var GALLERIES = ["black-and-white", "colours-street", "portraits"];
  var mount = document.getElementById("cloud");
  if (!mount) return;

  function columnCount() {
    var w = window.innerWidth;
    if (w < 620) return 2;
    if (w < 1000) return 3;
    if (w < 1500) return 4;
    return 5;
  }

  function parseOrder(text) {
    return text.split("\n")
      .map(function (l) { return l.trim(); })
      .filter(function (l) { return l && l.charAt(0) !== "#"; });
  }

  Promise.all([
    fetch("/v2/order.txt", { cache: "no-cache" }).then(function (r) { return r.ok ? r.text() : ""; }),
    Promise.all(GALLERIES.map(function (g) {
      return fetch("/galleries/" + g + "/manifest.json", { cache: "no-cache" })
        .then(function (r) { return r.ok ? r.json() : []; })
        .then(function (list) {
          return list.map(function (e) { e.gallery = g; e.key = g + "/" + e.id; return e; });
        });
    }))
  ]).then(function (res) {
    var wanted = parseOrder(res[0]);
    var all = [].concat.apply([], res[1]);

    var byKey = {};
    all.forEach(function (e) { byKey[e.key] = e; });

    var ordered = [];
    var used = {};
    wanted.forEach(function (k) {
      if (byKey[k]) { ordered.push(byKey[k]); used[k] = true; }
      else { console.warn("order.txt lists a photograph that does not exist:", k); }
    });
    // Anything published but not mentioned in order.txt still gets shown,
    // appended at the end, so a new upload is never silently invisible.
    all.forEach(function (e) { if (!used[e.key]) ordered.push(e); });

    render(ordered);
    var last = columnCount();
    window.addEventListener("resize", function () {
      var n = columnCount();
      if (n !== last) { last = n; render(ordered); }
    });
  });

  function render(items) {
    mount.innerHTML = "";

    if (!items.length) {
      mount.innerHTML = '<p class="cloud-empty">No photographs yet.</p>';
      return;
    }

    var n = columnCount();
    var cols = [], heights = [];
    for (var i = 0; i < n; i++) {
      var c = document.createElement("div");
      c.className = "cloud-col";
      cols.push(c); heights.push(0);
      mount.appendChild(c);
    }

    items.forEach(function (e) {
      // Shortest-column placement: keeps order roughly intact while packing
      // tightly, which CSS columns cannot do.
      var shortest = heights.indexOf(Math.min.apply(null, heights));
      var ratio = e.height / e.width;          // relative height in one column
      heights[shortest] += ratio;

      var base = "/galleries/" + e.gallery + "/images/";
      var grid = (e.widths || []).filter(function (w) { return w <= 1600; });
      if (!grid.length) grid = [Math.max.apply(null, e.widths || [800])];

      var fig = document.createElement("figure");
      var img = document.createElement("img");
      img.src = base + e.id + "-" + grid[grid.length - 1] + ".webp";
      img.srcset = grid.map(function (w) { return base + e.id + "-" + w + ".webp " + w + "w"; }).join(", ");
      img.sizes = "(min-width: 1500px) 20vw, (min-width: 1000px) 25vw, (min-width: 620px) 33vw, 50vw";
      img.width = e.width;
      img.height = e.height;
      img.loading = "lazy";
      img.decoding = "async";
      img.alt = e.alt || "";
      fig.appendChild(img);
      cols[shortest].appendChild(fig);
    });
  }
})();
