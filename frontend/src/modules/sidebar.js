const STORAGE_KEY = 'sidebarCollapsed';

export function init() {
  const sidebar = document.getElementById('sidebar');
  const collapseBtn = document.getElementById('sidebar-collapse');
  const collapseIcon = document.getElementById('collapse-icon');
  const mobileBtn = document.getElementById('mobile-menu-btn');

  // Restore collapsed state
  if (localStorage.getItem(STORAGE_KEY) === '1') {
    document.body.classList.add('sidebar-collapsed');
    rotateIcon(collapseIcon, true);
  }

  collapseBtn?.addEventListener('click', () => {
    const collapsed = document.body.classList.toggle('sidebar-collapsed');
    localStorage.setItem(STORAGE_KEY, collapsed ? '1' : '0');
    rotateIcon(collapseIcon, collapsed);
  });

  // Mobile: toggle sidebar as drawer
  mobileBtn?.addEventListener('click', () => {
    sidebar.classList.toggle('hidden');
  });
}

function rotateIcon(icon, collapsed) {
  if (!icon) return;
  icon.style.transform = collapsed ? 'rotate(180deg)' : '';
}

export function setActiveTab(tabName) {
  document.querySelectorAll('.nav-item').forEach(btn => {
    const active = btn.dataset.tab === tabName;
    btn.classList.toggle('active', active);
  });
}
