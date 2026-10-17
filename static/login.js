document.getElementById('loginForm').addEventListener('submit', async event => {
  event.preventDefault();
  const button = document.getElementById('enterWorkspace');
  button.disabled = true;
  document.getElementById('loginError').textContent = '';
  try {
    const response = await fetch('/api/login', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({username:document.getElementById('username').value.trim(), password:document.getElementById('password').value})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Unable to sign in.');
    window.location.assign('/app');
  } catch (error) {
    document.getElementById('loginError').textContent = error.message;
    document.getElementById('password').value = '';
    button.disabled = false;
  }
});
