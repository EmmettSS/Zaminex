(function () {
  "use strict";

  var started = false;

  var getPersianDateTime = function () {
    try {
      var formatter = new Intl.DateTimeFormat("fa-IR-u-ca-persian-nu-latn", {
        timeZone: "Asia/Tehran",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false
      });
      return formatter.format(new Date()).replace(",", "");
    } catch (e) {
      return null;
    }
  };

  var updateDynamicDateTime = function () {
    var nowStr = getPersianDateTime();
    if (!nowStr) return;

    var metaEl = document.getElementById("doc-meta-generated-at");
    if (metaEl) {
      metaEl.textContent = nowStr;
    }

    var styleEl = document.getElementById("print-page-style");
    if (styleEl) {
      var css = styleEl.textContent || styleEl.innerHTML;
      if (css) {
        var updated = css.replace(
          /(@top-left\s*\{[^}]*content:\s*")[^"]*(";)/,
          "$1" + nowStr + "$2"
        );
        styleEl.textContent = updated;
      }
    }
  };

  var start = function () {
    if (started) return;
    started = true;
    updateDynamicDateTime();
    try {
      window.print();
    } catch (e) {
      /* Nothing else to do — the report stays readable on the page. */
    }
  };

  var reprint = document.getElementById("reprint-btn");
  if (reprint) {
    reprint.addEventListener("click", function () {
      started = false;
      start();
    });
  }

  var closeBtn = document.getElementById("close-btn");
  if (closeBtn) {
    closeBtn.addEventListener("click", function () {
      window.close();
    });
  }

  var settle = function () {
    setTimeout(start, 150);
  };

  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(settle)["catch"](settle);
  } else if (document.readyState === "complete") {
    settle();
  } else {
    window.addEventListener("load", settle);
  }

  setTimeout(start, 4000);
})();
