async function loadSession() {
  const response = await fetch('/api/session');
  if (response.status === 401) {
    window.location.replace('/login');
    throw new Error('Session ended. Please sign in again.');
  }
  if (!response.ok) throw new Error('Unable to load workspace session.');
  const session = await response.json();
  window.tradeoffSession = session;
  document.getElementById('workspaceIdentity').textContent = session.participant;
  document.getElementById('workspaceOrganization').textContent = session.organization + ' · ' + session.username;
  const coordinator = session.role === 'coordinator';
  document.querySelectorAll('.coordinator-only').forEach(node => node.hidden = !coordinator);
  if (!coordinator) {
    const view = document.getElementById('view');
    view.value = session.participant;
    view.disabled = true;
    document.getElementById('intelligencePanel').hidden = true;
    document.getElementById('participantNotice').hidden = false;
  }
  document.getElementById('dashboard').hidden = false;
  return session;
}
document.getElementById('signOut').addEventListener('click', async () => {
  const response = await fetch('/api/logout', {method:'POST'});
  if (response.ok) window.location.replace('/login');
  else document.getElementById('sessionError').textContent = 'Sign-out failed. Please try again.';
});
const sessionReady = loadSession();
