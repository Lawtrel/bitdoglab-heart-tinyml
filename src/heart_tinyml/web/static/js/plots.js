/** Renderização sem dependências externas e sem lógica de inferência. */
export function clearPlot(canvas) {
  canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
}

export function drawWave(canvas, values) {
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#102f39';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = '#51727c';
  ctx.beginPath();
  ctx.moveTo(0, canvas.height / 2);
  ctx.lineTo(canvas.width, canvas.height / 2);
  ctx.stroke();
  ctx.strokeStyle = '#69d7b7';
  ctx.lineWidth = 2;
  ctx.beginPath();
  values.forEach((value, index) => {
    const x = index * canvas.width / (values.length - 1);
    const y = canvas.height / 2 - value * canvas.height * 0.46;
    if (index) ctx.lineTo(x, y);
    else ctx.moveTo(x, y);
  });
  ctx.stroke();
}

export function drawMfe(canvas, matrix) {
  const ctx = canvas.getContext('2d');
  const minimum = Math.min(...matrix.flat());
  const maximum = Math.max(...matrix.flat());
  matrix.forEach((band, row) => band.forEach((value, time) => {
    const proportion = (value - minimum) / (maximum - minimum || 1);
    ctx.fillStyle = `hsl(${220 - 180 * proportion} 70% ${15 + 55 * proportion}%)`;
    ctx.fillRect(time * canvas.width / band.length,
      (matrix.length - 1 - row) * canvas.height / matrix.length,
      Math.ceil(canvas.width / band.length), Math.ceil(canvas.height / matrix.length));
  }));
}

export function drawBars(canvas, categories, values, unit) {
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = '#f4f6f3'; ctx.fillRect(0, 0, w, h);
  const left = 95, top = 40, bottom = h - 55, usable = bottom - top;
  const maximum = Math.max(...values) * 1.25;
  ctx.font = '20px Arial'; ctx.fillStyle = '#173d46'; ctx.fillText(unit, 14, 27);
  for (let i = 0; i <= 4; i++) {
    const value = maximum * i / 4, y = bottom - usable * i / 4;
    ctx.strokeStyle = '#cedbd5'; ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(w - 25, y); ctx.stroke();
    ctx.fillStyle = '#536b70'; ctx.fillText(value.toLocaleString('pt-BR', {maximumFractionDigits: 3}), 10, y + 6);
  }
  const span = (w - left - 30) / values.length;
  values.forEach((value, i) => {
    const x = left + span * i + span * .22, barW = span * .56, barH = usable * value / maximum;
    ctx.fillStyle = i ? '#b34c3e' : '#14766b'; ctx.fillRect(x, bottom - barH, barW, barH);
    ctx.textAlign = 'center'; ctx.fillStyle = '#173d46';
    ctx.fillText(value.toLocaleString('pt-BR', {maximumFractionDigits: 3}), x + barW / 2, bottom - barH - 12);
    ctx.fillText(categories[i], x + barW / 2, h - 20); ctx.textAlign = 'left';
  });
}
