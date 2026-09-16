// Powers the "Certifiable components" switch on the home page catalog grid,
// mirroring the filter on tmforum.org/oda/directory/components-map. A
// component counts as certifiable if it ships a conformance profile
// (see generate.py's `data-certifiable` attribute).
document$.subscribe(function () {
  var toggle = document.getElementById("oda-certifiable-toggle");
  if (!toggle) {
    return;
  }
  toggle.checked = false;
  toggle.addEventListener("change", function () {
    document.querySelectorAll(".oda-catalog-card").forEach(function (card) {
      var certifiable = card.getAttribute("data-certifiable") === "true";
      card.style.display = !toggle.checked || certifiable ? "" : "none";
    });
  });
});
