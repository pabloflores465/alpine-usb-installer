const header = document.querySelector('.site-header');
const heroCard = document.querySelector('.hero-card');

const updateHeader = () => {
  if (!header) return;
  header.classList.toggle('is-scrolled', window.scrollY > 16);
};

const updateHeroTilt = (event) => {
  if (!heroCard || window.matchMedia('(max-width: 900px)').matches) return;
  const rect = heroCard.getBoundingClientRect();
  const x = (event.clientX - rect.left) / rect.width - 0.5;
  const y = (event.clientY - rect.top) / rect.height - 0.5;
  heroCard.style.transform = `rotateX(${y * -4}deg) rotateY(${x * 5}deg) rotate(1deg)`;
};

const resetHeroTilt = () => {
  if (!heroCard) return;
  heroCard.style.transform = 'rotate(1deg)';
};

window.addEventListener('scroll', updateHeader, { passive: true });
heroCard?.addEventListener('mousemove', updateHeroTilt);
heroCard?.addEventListener('mouseleave', resetHeroTilt);
updateHeader();
