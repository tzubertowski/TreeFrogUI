---
layout: default
title: Minimalistic emulation frontend for SF3000-like handhelds
---

<section class="hero">
  <div class="hero-copy">
    <p class="eyebrow">TreeFrogUI / handheld frontend</p>
    <h1>Minimalistic emulation frontend for the SF3000 likes</h1>
    <p class="lede">For R36SX, SF3500, GB350 and similar handhelds.</p>
    <div class="actions">
      <a class="button" href="{{ '/guides/installation/' | relative_url }}">Installation guide</a>
      <a class="text-link" href="{{ '/scraper/' | relative_url }}">Easy boxart &amp; artwork →</a>
    </div>
  </div>
  <img class="hero-image" src="{{ '/assets/images/console.jpg' | relative_url }}" alt="TreeFrogUI running on a handheld console">
</section>

<section class="tool-shelf" aria-label="TreeFrogUI tools">
  <a class="tool-card" href="https://github.com/tzubertowski/TreeFrogUI-installer/releases"><span class="tool-card-copy"><strong>TreeFrogUI Installer</strong><small>Install TreeFrogUI from Windows, macOS, or Linux.</small></span><span class="tool-card-arrow" aria-hidden="true">↗</span></a>
  <a class="tool-card" href="{{ '/scraper/' | relative_url }}"><span class="tool-card-copy"><strong>Browser artwork tool</strong><small>Find box art and download a ready-to-use ZIP without installing software.</small></span><span class="tool-card-arrow" aria-hidden="true">↗</span></a>
  <a class="tool-card" href="https://github.com/tzubertowski/mini-scraper-cfw/releases"><span class="tool-card-copy"><strong>Mini Scraper</strong><small>Find and add box art and other game artwork.</small></span><span class="tool-card-arrow" aria-hidden="true">↗</span></a>
  <a class="tool-card" href="https://github.com/tzubertowski/TreeFrogUI_PortsCollection/releases"><span class="tool-card-copy"><strong>Ports Collection</strong><small>Add optional standalone games to your handheld.</small></span><span class="tool-card-arrow" aria-hidden="true">↗</span></a>
</section>

<section class="guide-links">
  <h2>New to TreeFrogUI?</h2>
  <p>Follow a simple guide to set up your device, add games and make the menu yours.</p>
  <div class="guide-grid">
    <a href="{{ '/guides/installation/' | relative_url }}"><strong>Install TreeFrogUI</strong><span>Choose your device and follow the setup steps.</span></a>
    <a href="{{ '/guides/artwork/' | relative_url }}"><strong>Add box art</strong><span>Find artwork in your browser or use Mini Scraper.</span></a>
    <a href="{{ '/guides/folders/' | relative_url }}"><strong>Games, folders &amp; systems</strong><span>Find the right folder for each console.</span></a>
    <a href="{{ '/guides/theming/' | relative_url }}"><strong>Change the look</strong><span>Install MuOS themes or pick colours, backgrounds and fonts.</span></a>
    <a href="{{ '/guides/ports/' | relative_url }}"><strong>Install game ports</strong><span>Add optional ports such as standalone games.</span></a>
    <a href="{{ '/guides/date-time/' | relative_url }}"><strong>Set date and time</strong><span>Use the emulated clock and account for time while powered off.</span></a>
  </div>
  <p class="guide-extras">Also: <a href="{{ '/guides/bios/' | relative_url }}">BIOS file list</a> · <a href="{{ '/guides/shortcuts/' | relative_url }}">in-game controls</a></p>
</section>

<section class="latest-releases" aria-label="Latest releases">
  <div class="section-heading"><div><p class="eyebrow">Latest updates</p><h2>News &amp; releases</h2></div><a href="https://github.com/tzubertowski/TreeFrogUI/releases">All releases →</a></div>
  <div class="releases">
    <article class="release-card" data-release="stable">
      <p class="eyebrow">Stable release</p>
      <h3 data-release-title>Loading…</h3>
      <time data-release-date></time>
      <div class="release-notes markdown-body" data-release-notes></div>
      <a data-release-link href="https://github.com/tzubertowski/TreeFrogUI/releases/latest">Read full release notes →</a>
    </article>
    <article class="release-card" data-release="prerelease">
      <p class="eyebrow">Pre-release</p>
      <h3 data-release-title>Loading…</h3>
      <time data-release-date></time>
      <div class="release-notes markdown-body" data-release-notes></div>
      <a data-release-link href="https://github.com/tzubertowski/TreeFrogUI/releases">Read full release notes →</a>
    </article>
  </div>
  <p class="quiet release-status" data-release-status aria-live="polite"></p>
</section>
<script src="{{ '/assets/js/releases.js' | relative_url }}" defer></script>
