const NAV = [
  { href: "/", key: "home", label: "ホーム" },
  { href: "/files", key: "files", label: "ファイル" },
  { href: "/templates", key: "templates", label: "テンプレート" },
] as const;

function constellations(): string {
  return `<svg class="stars" viewBox="0 0 960 720" aria-hidden="true">
    <g class="constellation c-leo">
      <circle cx="92" cy="118" r="2.2" />
      <circle cx="128" cy="96" r="1.6" />
      <circle cx="168" cy="108" r="2.6" />
      <circle cx="196" cy="148" r="1.5" />
      <circle cx="158" cy="176" r="1.8" />
      <path d="M92 118 L128 96 L168 108 L196 148 M168 108 L158 176" />
    </g>
    <g class="constellation c-scorpio">
      <circle cx="780" cy="86" r="1.7" />
      <circle cx="812" cy="118" r="2.1" />
      <circle cx="838" cy="162" r="1.5" />
      <circle cx="818" cy="208" r="2.4" />
      <circle cx="776" cy="228" r="1.6" />
      <path d="M780 86 L812 118 L838 162 L818 208 L776 228" />
    </g>
    <g class="constellation c-corona">
      <circle cx="620" cy="520" r="1.8" />
      <circle cx="656" cy="498" r="2.2" />
      <circle cx="698" cy="506" r="1.5" />
      <circle cx="724" cy="538" r="1.7" />
      <path d="M620 520 L656 498 L698 506 L724 538" />
    </g>
  </svg>`;
}

export function shell(active: string, main: string, meeting = false): string {
  const item = (href: string, label: string, key: string, extra = "") =>
    `<a href="${href}" class="${extra}${active === key ? " active" : ""}">${label}</a>`;
  const railNav = NAV.map((n) => item(n.href, n.label, n.key)).join("");
  const dock = NAV.map((n) => item(n.href, n.label, n.key, "dock-item ")).join("");
  return `<a class="skip-link" href="#main">本文へ</a>
  ${constellations()}
  <div class="app${meeting ? " app-meeting" : ""}">
    <aside class="rail">
      <a class="brand" href="/">
        <img src="/brand/kitepon-dev-on-night.png" alt="kitepon.dev" width="160" height="48" />
        <span class="product">plaude</span>
      </a>
      <nav class="rail-nav">${railNav}</nav>
    </aside>
    <main id="main" class="main">${main}</main>
    <nav class="dock" aria-label="主要">${dock}</nav>
  </div>`;
}
