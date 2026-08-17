(() => {
  "use strict";

  if (window.lucide) {
    window.lucide.createIcons();
  }

  const header = document.querySelector("[data-header]");
  const navToggle = document.querySelector("[data-nav-toggle]");
  const navLinks = document.querySelector("[data-nav-links]");
  const researchTrigger = document.querySelector("[data-research-trigger]");
  const researchList = document.querySelector("[data-research-list]");

  const setHeaderState = () => {
    header?.classList.toggle("is-scrolled", window.scrollY > 12);
  };

  setHeaderState();
  window.addEventListener("scroll", setHeaderState, { passive: true });

  const closeMobileNav = () => {
    if (!navToggle || !navLinks) return;
    navToggle.setAttribute("aria-expanded", "false");
    navToggle.setAttribute("aria-label", "Open navigation");
    navLinks.classList.remove("is-open");
    document.body.classList.remove("nav-open");
  };

  navToggle?.addEventListener("click", () => {
    const open = navToggle.getAttribute("aria-expanded") === "true";
    navToggle.setAttribute("aria-expanded", String(!open));
    navToggle.setAttribute("aria-label", open ? "Open navigation" : "Close navigation");
    navLinks?.classList.toggle("is-open", !open);
    document.body.classList.toggle("nav-open", !open);
  });

  navLinks?.querySelectorAll("a[href^='#']").forEach((link) => {
    link.addEventListener("click", closeMobileNav);
  });

  researchTrigger?.addEventListener("click", (event) => {
    event.stopPropagation();
    const open = researchTrigger.getAttribute("aria-expanded") === "true";
    researchTrigger.setAttribute("aria-expanded", String(!open));
    researchList?.classList.toggle("is-open", !open);
  });

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".research-menu")) {
      researchTrigger?.setAttribute("aria-expanded", "false");
      researchList?.classList.remove("is-open");
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    closeMobileNav();
    researchTrigger?.setAttribute("aria-expanded", "false");
    researchList?.classList.remove("is-open");
  });

  const revealItems = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window) {
    const revealObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -45px" });

    revealItems.forEach((item) => revealObserver.observe(item));
  } else {
    revealItems.forEach((item) => item.classList.add("is-visible"));
  }

  const railNodes = Array.from(document.querySelectorAll(".rail-node"));
  if (railNodes.length) {
    let activeRailNode = 0;
    window.setInterval(() => {
      railNodes[activeRailNode].classList.remove("is-active");
      activeRailNode = (activeRailNode + 1) % railNodes.length;
      railNodes[activeRailNode].classList.add("is-active");
    }, 2000);
  }

  const typewriter = document.querySelector("[data-typewriter]");
  const logMessages = [
    "plan.md updated: verify attachment before send",
    "backup.md updated: locate widget by text and role",
    "recover.md updated: dismiss pop-up, resume at step 4",
    "meta.json verified: reusable on related task variants"
  ];

  if (typewriter && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    let messageIndex = 0;
    let characterIndex = logMessages[0].length;
    let deleting = true;

    window.setInterval(() => {
      const message = logMessages[messageIndex];
      if (deleting) {
        characterIndex -= 1;
        if (characterIndex <= 0) {
          deleting = false;
          messageIndex = (messageIndex + 1) % logMessages.length;
        }
      } else {
        characterIndex += 1;
        if (characterIndex >= logMessages[messageIndex].length) {
          deleting = true;
        }
      }
      typewriter.textContent = logMessages[messageIndex].slice(0, characterIndex);
    }, 62);
  }

  const filePreviews = {
    meta: {
      name: "meta.json",
      code: `{
  "intent": "send email with attachment",
  "app": "Gmail",
  "platform": "Android",
  "keywords": ["compose", "attach", "send"],
  "status": "verified"
}`
    },
    plan: {
      name: "plan.md",
      code: `# Executable plan
1. Open the compose view.
2. Fill recipient, subject, and body.
3. Add the requested attachment.
4. Verify the attachment chip is visible.
5. Send only after verification passes.`
    },
    backup: {
      name: "backup.md",
      code: `# Localization fallbacks
- Prefer visible text + semantic role.
- If the attachment icon moved, query the
  accessibility tree for "Attach file".
- Re-observe after any layout transition.`
    },
    recover: {
      name: "recover.md",
      code: `# Recovery rules
- Unexpected pop-up: dismiss, then re-observe.
- Stale screen: wait once and refresh state.
- Wrong page: backtrack to the last verified
  checkpoint instead of restarting.`
    },
    a11y: {
      name: "a11y.py",
      code: `def find_actionable(tree, label, role=None):
    """Return visible nodes matching label + role."""
    nodes = normalize(tree)
    return rank_matches(
        nodes, label=label, role=role,
        visible=True, enabled=True
    )`
    },
    failures: {
      name: "failures/003.json",
      code: `{
  "failed_step": 4,
  "direct_cause": "attachment not verified",
  "evidence": "no file chip before Send tap",
  "target_file": "plan.md",
  "revision": "insert explicit verification"
}`
    }
  };

  const previewName = document.querySelector("[data-preview-name]");
  const previewCode = document.querySelector("[data-preview-code]");
  document.querySelectorAll("[data-file]").forEach((button) => {
    button.addEventListener("click", () => {
      const preview = filePreviews[button.dataset.file];
      if (!preview || !previewName || !previewCode) return;

      document.querySelectorAll("[data-file]").forEach((item) => {
        const selected = item === button;
        item.classList.toggle("is-selected", selected);
        item.setAttribute("aria-pressed", String(selected));
      });

      previewName.textContent = preview.name;
      previewCode.textContent = preview.code;
    });
  });

  const activateResult = (name) => {
    document.querySelectorAll("[data-result-tab]").forEach((tab) => {
      const selected = tab.dataset.resultTab === name;
      tab.classList.toggle("is-active", selected);
      tab.setAttribute("aria-selected", String(selected));
    });

    document.querySelectorAll("[data-result-panel]").forEach((panel) => {
      const selected = panel.dataset.resultPanel === name;
      panel.hidden = !selected;
      panel.classList.toggle("is-active", selected);
    });
  };

  document.querySelectorAll("[data-result-tab]").forEach((tab) => {
    tab.addEventListener("click", () => activateResult(tab.dataset.resultTab));
    tab.addEventListener("keydown", (event) => {
      if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
      const tabs = Array.from(document.querySelectorAll("[data-result-tab]"));
      const current = tabs.indexOf(tab);
      const direction = event.key === 'ArrowRight' ? 1 : -1;
      const next = tabs[(current + direction + tabs.length) % tabs.length];
      activateResult(next.dataset.resultTab);
      next.focus();
    });
  });

  const activateCase = (name) => {
    document.querySelectorAll("[data-case-tab]").forEach((tab) => {
      const selected = tab.dataset.caseTab === name;
      tab.classList.toggle("is-active", selected);
      tab.setAttribute("aria-selected", String(selected));
    });

    document.querySelectorAll("[data-case-panel]").forEach((panel) => {
      const selected = panel.dataset.casePanel === name;
      panel.hidden = !selected;
      panel.classList.toggle("is-active", selected);
    });
  };

  document.querySelectorAll("[data-case-tab]").forEach((tab) => {
    tab.addEventListener("click", () => activateCase(tab.dataset.caseTab));
  });

  const copyButton = document.querySelector("[data-copy-bib]");
  const copyStatus = document.querySelector("[data-copy-status]");
  const bibtexCode = document.querySelector("#bibtex-code");

  const copyText = async (text) => {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }

    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  };

  copyButton?.addEventListener("click", async () => {
    if (!bibtexCode || !copyStatus) return;
    try {
      await copyText(bibtexCode.textContent.trim());
      copyStatus.textContent = "Copied";
      copyButton.setAttribute("aria-label", "BibTeX copied");
    } catch {
      copyStatus.textContent = "Copy failed";
    }
    window.setTimeout(() => {
      copyStatus.textContent = "";
      copyButton.setAttribute("aria-label", "Copy BibTeX");
    }, 1800);
  });
})();
