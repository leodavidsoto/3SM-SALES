const API = import.meta.env.VITE_API || 'http://localhost:4000';

async function handle(res) {
  if (!res.ok) {
    let msg = `Error HTTP ${res.status}`;
    try { const data = await res.json(); if (data?.error) msg = data.error; } catch {}
    throw new Error(msg);
  }
  return res.json();
}

export async function uploadFile(file) {
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch(`${API}/api/analyze`, { method: 'POST', body: fd });
  return handle(res);
}

export async function createOrder(payload) {
  const res = await fetch(`${API}/api/order`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  return handle(res);
}

export async function listOrders() {
  const res = await fetch(`${API}/api/orders`);
  return handle(res);
}
