/** Adapter HTTP. O restante da interface não conhece headers ou endpoints. */
export class DemoApi {
  constructor() {
    this.token = document.querySelector('meta[name="demo-nonce"]').content;
  }

  async request(path, body) {
    const options = body === undefined ? {} : {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-Demo-Token': this.token},
      body: JSON.stringify(body),
    };
    const response = await fetch(path, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Pedido não concluído.');
    return data;
  }

  info() { return this.request('/api/info'); }
  results() { return this.request('/api/results'); }
  benchmark() { return this.request('/api/benchmark'); }
  connect(port) { return this.request('/api/connect', {port}); }
  analyze(wav, start, board, port) {
    return this.request('/api/analyze', {wav, start, board, port});
  }
  capture(port) { return this.request('/api/capture', {port}); }
}

export function toBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

export function audioBlob(encoded) {
  return new Blob([Uint8Array.from(atob(encoded), value => value.charCodeAt(0))], {type: 'audio/wav'});
}
