(() => {
  const form = document.querySelector('#assessment-form');
  if (!form) return;
  const key = `cyberready-assessment-draft:${form.dataset.draftId}`;
  // Each server-rendered assessment has a new draft ID. Remove drafts from
  // previous assessment attempts so answers cannot carry into this one.
  Object.keys(localStorage)
    .filter((storedKey) => storedKey.startsWith('cyberready-assessment-draft:') && storedKey !== key)
    .forEach((storedKey) => localStorage.removeItem(storedKey));
  const status = document.querySelector('#offline-status');
  const retry = document.querySelector('#retry-saved-assessment');
  const setStatus = (message) => { if (status) status.textContent = message; };
  const read = () => { try { return JSON.parse(localStorage.getItem(key)); } catch (_) { return null; } };
  const clear = () => localStorage.removeItem(key);
  const save = () => {
    const answers = {};
    form.querySelectorAll('input[type="radio"]:checked').forEach((input) => { answers[input.name] = input.value; });
    localStorage.setItem(key, JSON.stringify({ answers, savedAt: Date.now() }));
  };
  const restore = () => {
    const draft = read();
    if (!draft || !draft.answers) return;
    Object.entries(draft.answers).forEach(([name, value]) => {
      const input = form.querySelector(`input[type="radio"][name="${CSS.escape(name)}"][value="${CSS.escape(value)}"]`);
      if (input) input.checked = true;
    });
    setStatus('A saved assessment draft was restored on this device.');
  };
  const updateConnection = () => {
    if (navigator.onLine) {
      setStatus(read() ? 'Online — saved assessment is ready to submit.' : 'Online');
      retry.hidden = !read();
    } else {
      setStatus('Offline — your work is saved locally');
      retry.hidden = true;
    }
  };
  form.querySelectorAll('input[type="radio"]').forEach((input) => input.addEventListener('change', () => { save(); updateConnection(); }));
  form.addEventListener('submit', (event) => {
    save();
    if (!navigator.onLine) {
      event.preventDefault();
      setStatus('You are offline. Your assessment has been saved on this device and can be submitted when you reconnect.');
      retry.hidden = true;
    } else {
      // The server has received the completed assessment; never carry its
      // answers into a future assessment page.
      clear();
    }
  });
  const quit = document.querySelector('#quit-assessment');
  if (quit) quit.addEventListener('click', () => {
    clear();
    window.location.assign(quit.dataset.dashboardUrl);
  });
  retry.addEventListener('click', () => { if (navigator.onLine) form.requestSubmit(); });
  window.addEventListener('online', updateConnection);
  window.addEventListener('offline', updateConnection);
  window.addEventListener('pageshow', () => { restore(); updateConnection(); });
  window.addEventListener('beforeunload', () => {
    if (!navigator.onLine) save();
  });
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('/service-worker.js').catch(() => {});
  restore(); updateConnection();
})();
