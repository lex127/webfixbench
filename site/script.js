(() => {
  const header = document.querySelector('[data-header]');
  const toggle = document.querySelector('[data-nav-toggle]');
  const nav = document.querySelector('[data-nav]');
  const year = document.querySelector('[data-year]');
  const copyButton = document.querySelector('[data-copy-code]');
  const code = document.querySelector('[data-code]');

  if (year) year.textContent = new Date().getFullYear();

  const syncHeader = () => header?.classList.toggle('scrolled', window.scrollY > 12);
  syncHeader();
  window.addEventListener('scroll', syncHeader, { passive: true });

  if (toggle && nav) {
    toggle.addEventListener('click', () => {
      const open = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', String(open));
    });
    nav.addEventListener('click', (event) => {
      if (event.target instanceof HTMLAnchorElement) {
        nav.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

  if (copyButton && code) {
    copyButton.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(code.textContent || '');
        copyButton.textContent = 'Copied';
        window.setTimeout(() => { copyButton.textContent = 'Copy'; }, 1400);
      } catch {
        copyButton.textContent = 'Select text';
      }
    });
  }
})();