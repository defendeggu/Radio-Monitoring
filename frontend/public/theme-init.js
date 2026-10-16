// Apply the saved theme before the first paint (avoids a light/dark flash).
try {
  var t = localStorage.getItem('radiomoni.theme') || 'system';
  var dark = t === 'dark' || (t === 'system' && matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.classList.toggle('dark', dark);
} catch {
  document.documentElement.classList.add('dark');
}
