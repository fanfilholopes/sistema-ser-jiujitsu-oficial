self.addEventListener('install', (e) => {
  console.log('SER JJ Service Worker Instalado');
});

self.addEventListener('fetch', (e) => {
  // Mantém o app funcionando online
});