import './style.css';

import * as sidebar from './modules/sidebar.js';
import * as sdr from './modules/sdr.js';
import * as voice from './modules/voice.js';
import * as aprs from './modules/aprs.js';
import * as pocsag from './modules/pocsag.js';
import * as repeater from './modules/repeater.js';
import * as multi from './modules/multi.js';

const TABS = ['voice', 'aprs', 'pocsag', 'repeater', 'multi'];

function showTab(name) {
  TABS.forEach(t => {
    document.getElementById(t + 'Tab')?.classList.toggle('hidden', t !== name);
  });
  sidebar.setActiveTab(name);
  localStorage.setItem('activeTab', name);
}

function initNavigation() {
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => showTab(btn.dataset.tab));
  });

  const saved = localStorage.getItem('activeTab') || 'voice';
  showTab(SAVED_TAB_VALID.includes(saved) ? saved : 'voice');
}

const SAVED_TAB_VALID = TABS;

document.addEventListener('DOMContentLoaded', () => {
  sidebar.init();
  initNavigation();
  sdr.init();
  voice.init();
  aprs.init();
  pocsag.init();
  repeater.init();
  multi.init();
});
