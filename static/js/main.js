/* 24sevendelivery — main.js */

// ── Preloader ────────────────────────────────────────────────────────────
(() => {
  const preloader = document.getElementById('preloader');
  if (!preloader) return;
  const MIN_SHOW_MS = 3100; // keep it on screen long enough to actually see the animation
  const shownAt = Date.now();

  function hidePreloader() {
    const elapsed = Date.now() - shownAt;
    const wait = Math.max(0, MIN_SHOW_MS - elapsed);
    setTimeout(() => {
      preloader.classList.add('preloader--hide');
      document.body.classList.remove('is-loading');
      setTimeout(() => preloader.remove(), 650);
    }, wait);
  }

  if (document.readyState === 'complete') {
    hidePreloader();
  } else {
    window.addEventListener('load', hidePreloader);
    // safety net — never let it hang forever if an image stalls
    setTimeout(hidePreloader, 4000);
  }
})();

// ── Scroll-aware nav ───────────────────────────────────────────────────────
const nav = document.getElementById('nav');
if (nav) {
  window.addEventListener('scroll', () => {
    nav.classList.toggle('scrolled', window.scrollY > 40);
  }, { passive: true });
}

// ── Mobile nav ─────────────────────────────────────────────────────────────
const hamburger = document.getElementById('hamburger');
const mobileNav = document.getElementById('mobileNav');
const mobileClose = document.getElementById('mobileClose');

if (hamburger && mobileNav) {
  hamburger.addEventListener('click', () => mobileNav.classList.add('open'));
  mobileClose?.addEventListener('click', () => mobileNav.classList.remove('open'));
  mobileNav.addEventListener('click', (e) => {
    if (e.target.tagName === 'A') mobileNav.classList.remove('open');
  });
}

// ── Reveal-on-scroll (IntersectionObserver) ────────────────────────────────
const revealEls = document.querySelectorAll('.reveal');
if (revealEls.length) {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry, i) => {
      if (entry.isIntersecting) {
        // stagger siblings inside the same parent
        const siblings = Array.from(entry.target.parentElement?.querySelectorAll('.reveal') || []);
        const idx = siblings.indexOf(entry.target);
        setTimeout(() => {
          entry.target.classList.add('visible');
        }, idx * 80);
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

  revealEls.forEach(el => observer.observe(el));
}

// ── Smooth anchor links ────────────────────────────────────────────────────
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', e => {
    const id = a.getAttribute('href').slice(1);
    const target = document.getElementById(id);
    if (target) {
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth' });
    }
  });
});

// ── Product card hover shimmer ─────────────────────────────────────────────
document.querySelectorAll('.product-card').forEach(card => {
  card.addEventListener('mousemove', (e) => {
    const rect = card.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width - 0.5) * 12;
    const y = ((e.clientY - rect.top) / rect.height - 0.5) * 12;
    card.style.transform = `translateY(-5px) rotateX(${-y * 0.4}deg) rotateY(${x * 0.4}deg)`;
  });
  card.addEventListener('mouseleave', () => {
    card.style.transform = '';
    card.style.transition = 'transform .4s ease';
  });
  card.addEventListener('mouseenter', () => {
    card.style.transition = 'transform .1s ease';
  });
});

// ── Ticker pause on hover ──────────────────────────────────────────────────
const ticker = document.querySelector('.ticker__track');
if (ticker) {
  ticker.addEventListener('mouseenter', () => ticker.style.animationPlayState = 'paused');
  ticker.addEventListener('mouseleave', () => ticker.style.animationPlayState = 'running');
}

// ── Button ripple effect ───────────────────────────────────────────────────
document.querySelectorAll('.btn--gold').forEach(btn => {
  btn.addEventListener('click', function(e) {
    const ripple = document.createElement('span');
    const rect = this.getBoundingClientRect();
    ripple.style.cssText = `
      position: absolute;
      border-radius: 50%;
      background: rgba(255,255,255,0.25);
      width: 100px; height: 100px;
      left: ${e.clientX - rect.left - 50}px;
      top: ${e.clientY - rect.top - 50}px;
      transform: scale(0);
      animation: ripple .5s ease-out forwards;
      pointer-events: none;
    `;
    if (!this.style.position) this.style.position = 'relative';
    this.style.overflow = 'hidden';
    this.appendChild(ripple);
    setTimeout(() => ripple.remove(), 600);
  });
});

// Inject ripple keyframes once
if (!document.getElementById('rippleStyle')) {
  const style = document.createElement('style');
  style.id = 'rippleStyle';
  style.textContent = '@keyframes ripple { to { transform: scale(3); opacity: 0; } }';
  document.head.appendChild(style);
}

// ── Input focus float label animation ────────────────────────────────────
document.querySelectorAll('.input').forEach(input => {
  input.addEventListener('focus', () => {
    input.closest('.form-group')?.classList.add('focused');
  });
  input.addEventListener('blur', () => {
    input.closest('.form-group')?.classList.remove('focused');
  });
});

// ── Confirmation page: auto-redirect to home ────────────────────────────
// Scoped so it only runs on the confirmation page — every other page has
// no .confirmation-card__actions element, which was crashing this script
// (and everything after it) with a null-reference error site-wide.
const confirmationActions = document.querySelector('.confirmation-card__actions');
if (confirmationActions) {
  let secondsLeft = 6;
  const redirectNote = document.createElement('p');
  redirectNote.className = 'confirmation-card__redirect-note';
  redirectNote.textContent = `Redirecting to home in ${secondsLeft}s…`;
  confirmationActions.insertAdjacentElement('beforebegin', redirectNote);

  const countdown = setInterval(() => {
    secondsLeft--;
    redirectNote.textContent = `Redirecting to home in ${secondsLeft}s…`;
    if (secondsLeft <= 0) {
      clearInterval(countdown);
      window.location.href = '/';
    }
  }, 1000);
}