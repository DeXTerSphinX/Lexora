/* ═══════════════════════════════════════════════
   transitions.js  —  Morphic Blur Transition
   Add <script defer src="transitions.js"></script>
   to every HTML file's <head>
   ═══════════════════════════════════════════════ */

(() => {
    const DURATION = 500; // ms — match your CSS transition

    /* ── 1. Create the overlay ──────────────────── */
    const overlay = document.createElement('div');
    overlay.id = 'page-transition-overlay';
    document.body.appendChild(overlay);

    /* ── 2. Page ENTER — clear overlay immediately ─
       The body animation (morphIn) handles the
       actual visual entry. Overlay just needs to
       stay out of the way.                          */
    // Nothing needed — overlay starts at opacity:0

    /* ── 3. Core exit function ──────────────────── */
    function morphTo(url) {
        // Prevent double-firing
        if (overlay.classList.contains('morph-out')) return;

        // Trigger the blur build-up
        overlay.classList.add('morph-out');

        // Also blur + shrink the page content itself
        document.body.style.transition =
            `filter ${DURATION}ms cubic-bezier(0.4,0,0.2,1),
             transform ${DURATION}ms cubic-bezier(0.4,0,0.2,1),
             opacity ${DURATION}ms cubic-bezier(0.4,0,0.2,1)`;
        document.body.style.filter    = 'blur(12px)';
        document.body.style.transform = 'scale(1.02)';
        document.body.style.opacity   = '0';

        // Navigate after blur peaks
        setTimeout(() => {
            window.location.href = url;
        }, DURATION);
    }

    /* ── 4. Expose globally for onclick usage ────── */
    window.transitionTo = morphTo;

    /* ── 5. Intercept ALL internal <a> clicks ────── */
    document.addEventListener('click', (e) => {
        const link = e.target.closest('a');
        if (!link || !link.href)                   return;
        if (link.target === '_blank')              return;
        if (link.href.startsWith('mailto:'))       return;
        if (link.href.startsWith('tel:'))          return;
        if (link.getAttribute('href')?.startsWith('#')) return;
        if (new URL(link.href).origin !== location.origin) return;

        e.preventDefault();
        morphTo(link.href);
    });

})();