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
