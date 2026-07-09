export async function api(path, options = {}) {
  const response = await fetch(path, {
    method: options.method || 'GET',
    headers: {'Content-Type': 'application/json'},
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
  if (response.status === 401) {
    location.href = '/login';
    throw new Error('Niet ingelogd');
  }
  if (!response.ok) {
    const detail = (await response.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === 'string' ? detail : response.statusText);
  }
  return response.status === 204 ? null : response.json();
}

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else if (key === 'html') node.innerHTML = value;
    else if (value !== null && value !== undefined) node.setAttribute(key, value);
  }
  node.append(...children.filter((c) => c !== null && c !== undefined));
  return node;
}
