// Smart Park - App JS

// Countdown timers
function startTimers() {
  document.querySelectorAll('[data-seconds]').forEach(el => {
    let secs = parseInt(el.dataset.seconds, 10);
    if (isNaN(secs)) return;
    function tick() {
      if (secs <= 0) { el.textContent = 'Expired'; return; }
      const h = Math.floor(secs / 3600);
      const m = Math.floor((secs % 3600) / 60);
      const s = secs % 60;
      el.textContent = h > 0
        ? `${h}h ${String(m).padStart(2,'0')}m`
        : `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
      secs--;
      setTimeout(tick, 1000);
    }
    tick();
  });
}

document.addEventListener('DOMContentLoaded', () => {
  startTimers();

  // Flash alerts auto-dismiss
  document.querySelectorAll('.alert').forEach(el => {
    setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity 0.5s'; setTimeout(() => el.remove(), 500); }, 5000);
  });
});
