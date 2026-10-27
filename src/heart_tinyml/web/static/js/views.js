/** Apresentação dos resultados, sem acesso à USB nem ao runtime do modelo. */
export const number = (value, digits = 3) => Number(value).toLocaleString('pt-BR', {
  minimumFractionDigits: digits, maximumFractionDigits: digits,
});

export function table(headers, rows) {
  const element = document.createElement('table');
  const header = element.createTHead().insertRow();
  headers.forEach(text => {
    const cell = document.createElement('th');
    cell.textContent = text;
    header.append(cell);
  });
  const body = element.createTBody();
  rows.forEach(values => {
    const row = body.insertRow();
    values.forEach(value => { row.insertCell().textContent = value; });
  });
  return element;
}

export function showPrediction(container, result, board = false, experimental = false) {
  container.replaceChildren();
  const present = result.score >= result.threshold;
  container.className = 'prediction ' + (experimental ? 'experimental' : present ? 'present' : 'absent');
  const label = document.createElement('span');
  label.textContent = board ? 'BITDOGLAB' : 'COMPUTADOR';
  const prediction = document.createElement('strong');
  prediction.textContent = result.prediction + (experimental ? '?' : '');
  const score = document.createElement('p');
  score.textContent = `Escore ${number(result.score)} / limiar ${number(result.threshold)}`;
  const timing = document.createElement('p');
  timing.textContent = `Processamento: ${number(result.processing_ms)} ms`;
  container.append(label, prediction, score, timing);
}

export function boardPrediction(response, threshold) {
  return {
    score: response.prob_present, threshold,
    prediction: response.prob_present >= threshold ? 'COM SOPRO' : 'SEM SOPRO',
    processing_ms: response.processing_us / 1000,
  };
}

export function showEvidence(evidence, benchmark) {
  const versions = [
    ['PC float', evidence.float_host], ['PC INT8 otimizado', evidence.original_host_saved],
    ['PC INT8 referência', evidence.reference_host], ['BitDogLab INT8', evidence.rp2040],
  ];
  document.querySelector('#metrics').replaceChildren(table(
    ['Execução', 'F1', 'Sensibilidade', 'Acurácia'],
    versions.map(([name, values]) => [name, number(values.f1), number(values.recall * 100, 1) + '%', number(values.accuracy * 100, 1) + '%']),
  ));
  const board = evidence.rp2040;
  document.querySelector('#confusion').replaceChildren(table(
    ['Referência', 'Previsto com sopro', 'Previsto sem sopro'],
    [['Com sopro', board.tp, board.fn], ['Sem sopro', board.fp, board.tn]],
  ));
  document.querySelector('#result-explanation').textContent =
    `A placa identificou ${board.tp} dos ${board.support_present} grupos com sopro e perdeu ${board.fn}. F1 ${number(board.f1)}, IC95% 0,526 a 0,829.`;
  document.querySelector('#timing-table').replaceChildren(table(
    ['Etapa', 'PC mediana (ms)', 'Placa mediana (ms)'],
    [['MFE', 'preprocessing'], ['Inferência', 'inference'], ['Combinado', 'processing']].map(([name, key]) =>
      [name, number(benchmark.summary[key].pc.median_ms), number(benchmark.summary[key].board.median_ms)]),
  ));
  document.querySelector('#machine').textContent = `${benchmark.provenance.processor}. Ensaio suplementar em ${benchmark.utc.slice(0, 10)}.`;
}
