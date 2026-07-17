(function (window) {
  "use strict";

  function ecoreFormPreview(formId, opts) {
    const form = document.getElementById(formId);
    if (!form || !opts) return;

    const codeInput = form.querySelector(opts.code);
    const nomInput = form.querySelector(opts.nom);
    const metaInput = opts.meta ? form.querySelector(opts.meta) : null;
    const previewCode = document.querySelector(opts.previewCode);
    const previewNom = document.querySelector(opts.previewNom);
    const previewMeta = opts.previewMeta ? document.querySelector(opts.previewMeta) : null;

    function update() {
      if (previewCode) {
        previewCode.textContent = (codeInput?.value || "").trim() || (opts.codeEmpty || "CODE");
      }
      if (previewNom) {
        previewNom.textContent = (nomInput?.value || "").trim() || (opts.nomEmpty || "Libellé");
      }
      if (previewMeta && metaInput) {
        const val = parseInt(metaInput.value, 10);
        const suffix = opts.metaSuffix || "";
        if (val > 0) {
          const plural = val > 1 && suffix ? suffix + "s" : suffix;
          previewMeta.textContent = opts.metaFormat
            ? opts.metaFormat(val)
            : `${val} ${plural}`.trim();
        } else {
          previewMeta.textContent = opts.metaEmpty || "";
        }
      }
    }

    [codeInput, nomInput, metaInput].forEach(function (el) {
      if (el) el.addEventListener("input", update);
    });
    update();
  }

  function ecoreFormCapacityChips(root) {
    const scope = root || document;
    scope.querySelectorAll(".js-capacity-chips").forEach(function (wrap) {
      const target = wrap.dataset.target;
      const input = target ? document.querySelector(target) : null;
      if (!input) return;

      wrap.querySelectorAll(".ecore-form-capacity-chip, .ecore-local-capacity-chip").forEach(function (chip) {
        chip.addEventListener("click", function () {
          input.value = chip.dataset.cap;
          input.dispatchEvent(new Event("input"));
          wrap.querySelectorAll(".ecore-form-capacity-chip, .ecore-local-capacity-chip").forEach(function (c) {
            c.classList.toggle("is-active", c === chip);
          });
        });
        if (chip.dataset.cap === input.value) chip.classList.add("is-active");
      });
    });
  }

  window.ecoreFormPreview = ecoreFormPreview;
  window.ecoreFormCapacityChips = ecoreFormCapacityChips;
})(window);
