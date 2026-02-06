document.addEventListener('DOMContentLoaded', function () {
  // Fix: Garantir display flex no ide-container para layout correto
  const ideContainer = document.querySelector('.ide-container');
  if (ideContainer) {
    ideContainer.style.display = 'flex';
    ideContainer.style.flexDirection = 'column';
  }

  const tabs = document.querySelectorAll('.tab');
  const panels = document.querySelectorAll('.panel');
  function activate(target) {
    tabs.forEach(t => t.classList.toggle('active', t.dataset.target === target));
    panels.forEach(p => p.classList.toggle('active', p.id === target));
  }
  tabs.forEach(t => t.addEventListener('click', () => activate(t.dataset.target)));

  // keyboard nav
  document.addEventListener('keyup', e => {
    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
      const arr = Array.from(tabs);
      const idx = arr.findIndex(t => t.classList.contains('active'));
      const next = e.key === 'ArrowRight' ? (idx + 1) % arr.length : (idx - 1 + arr.length) % arr.length;
      arr[next].click();
    }
  });
});