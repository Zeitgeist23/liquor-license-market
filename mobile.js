(() => {
  const ready = () => {
    const body = document.body;
    if (!body || document.querySelector('.llm-mobile-header')) return;

    const path = location.pathname.replace(/\/+$/, '') || '/';
    const isHome = path === '/' || path === '/index.html';
    if (isHome) body.classList.add('llm-homepage');

    const header = document.createElement('header');
    header.className = 'llm-mobile-header';
    header.innerHTML = `
      <a class="llm-mobile-brand" href="/" aria-label="Liquor License Market home">
        <span class="llm-mobile-mark" aria-hidden="true"><b>LLM</b></span>
        <span class="llm-mobile-brand-copy"><strong>Liquor License Market</strong><small>National Marketplace</small></span>
      </a>
      <button class="llm-mobile-menu-button" type="button" aria-label="Open menu" aria-expanded="false" aria-controls="llm-mobile-drawer"><span class="llm-mobile-menu-icon" aria-hidden="true"></span></button>`;

    const drawer = document.createElement('div');
    drawer.className = 'llm-mobile-drawer';
    drawer.id = 'llm-mobile-drawer';
    drawer.setAttribute('aria-hidden', 'true');
    drawer.innerHTML = `
      <nav aria-label="Mobile navigation">
        <a href="/">Home</a>
        <a href="/browse-markets.html">Browse Markets</a>
        <a href="/sell-license.html">Sell a License</a>
        <a href="/financing.html">Financing</a>
        <a href="/resources.html">Resources</a>
        <a href="/about.html">About Us</a>
        <a href="/contact.html">Contact</a>
        <a class="llm-mobile-login" href="/client-login.html">Client Login</a>
      </nav>`;

    body.prepend(drawer);
    body.prepend(header);
    body.classList.add('llm-mobile-ready');

    const button = header.querySelector('.llm-mobile-menu-button');
    const closeMenu = () => {
      button.setAttribute('aria-expanded', 'false');
      button.setAttribute('aria-label', 'Open menu');
      drawer.setAttribute('aria-hidden', 'true');
      drawer.classList.remove('is-open');
      body.classList.remove('llm-mobile-menu-open');
    };
    const openMenu = () => {
      button.setAttribute('aria-expanded', 'true');
      button.setAttribute('aria-label', 'Close menu');
      drawer.setAttribute('aria-hidden', 'false');
      drawer.classList.add('is-open');
      body.classList.add('llm-mobile-menu-open');
    };
    button.addEventListener('click', () => button.getAttribute('aria-expanded') === 'true' ? closeMenu() : openMenu());
    drawer.addEventListener('click', e => { if (e.target.closest('a')) closeMenu(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') closeMenu(); });
    window.addEventListener('resize', () => { if (innerWidth > 820) closeMenu(); });

    if (isHome) {
      const mobileHero = document.createElement('section');
      mobileHero.className = 'llm-mobile-home-hero';
      mobileHero.setAttribute('aria-label', 'Liquor License Market');
      mobileHero.innerHTML = `
        <p class="llm-mobile-home-eyebrow">The National Marketplace for Liquor Licenses</p>
        <h1>Buy. Sell. Finance.<span>Liquor Licenses.</span></h1>
        <p class="llm-mobile-home-lede">Browse active state markets, list a license for sale, connect with independent brokers, or explore liquor-license financing in one national marketplace.</p>
        <div class="llm-mobile-home-actions">
          <a class="primary" href="/browse-markets.html">BROWSE MARKETS</a>
          <a class="secondary" href="/sell-license.html">SELL A LICENSE</a>
        </div>
        <section class="llm-mobile-market-panel" aria-label="Active liquor license markets">
          <div class="llm-mobile-market-heading">
            <span>ACTIVE MARKETS</span>
            <a href="/browse-markets.html">View all</a>
          </div>
          <div class="llm-mobile-state-grid">
            <a href="/florida/"><b>FL</b><span>Florida</span></a>
            <a href="/california/licenses-for-sale/"><b>CA</b><span>California</span></a>
            <a href="/arizona/licenses-for-sale/"><b>AZ</b><span>Arizona</span></a>
            <a href="/new-mexico/licenses-for-sale/"><b>NM</b><span>New Mexico</span></a>
            <a href="/michigan/licenses-for-sale/"><b>MI</b><span>Michigan</span></a>
            <a href="/ohio/licenses-for-sale/"><b>OH</b><span>Ohio</span></a>
            <a href="/pennsylvania/licenses-for-sale/"><b>PA</b><span>Pennsylvania</span></a>
            <a href="/new-jersey/licenses-for-sale/"><b>NJ</b><span>New Jersey</span></a>
          </div>
        </section>`;
      const heroWrap = document.querySelector('.hero-wrap');
      if (heroWrap) heroWrap.before(mobileHero); else header.after(mobileHero);
    }
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready, {once:true});
  else ready();
})();
