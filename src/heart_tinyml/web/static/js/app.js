/** Controller da página: estado pequeno e fluxo explícito de ações. */
import {DemoApi, toBase64, audioBlob} from './api.js';
import {clearPlot, drawWave, drawMfe, drawBars} from './plots.js';
import {showPrediction, boardPrediction, showEvidence, number} from './views.js';

const api = new DemoApi();
const $ = selector => document.querySelector(selector);
const state = {audio: null, result: null, connected: false, busy: false, audioUrl: null};

function status(text, error = false) {
  $('#status').textContent = text;
  $('#status').classList.toggle('error', error);
}

function controls() {
  document.querySelectorAll('button, input, select').forEach(element => { element.disabled = state.busy; });
  $('#analyze').disabled = state.busy || !state.audio;
  $('#compare').disabled = state.busy || !state.audio || !state.connected;
  $('#capture').disabled = state.busy || !state.connected;
  $('#download').disabled = state.busy || !state.result;
}

function play(blob) {
  if (state.audioUrl) URL.revokeObjectURL(state.audioUrl);
  state.audioUrl = URL.createObjectURL(blob);
  $('#player').src = state.audioUrl;
}

function selectAudio(blob, name) {
  state.audio = blob;
  state.result = null;
  $('#filename').textContent = name;
  $('#offset').value = 0;
  $('#pc-result').textContent = 'Aguardando análise do áudio escolhido';
  $('#board-result').textContent = 'Sem medição nesta sessão';
  clearPlot($('#wave'));
  clearPlot($('#mfe'));
  play(blob);
  controls();
  status('Ouça o trecho e clique em Analisar no PC.');
}

async function execute(compare = false, capture = false) {
  if (!capture && !state.audio) return status('Escolha um áudio primeiro.', true);
  state.busy = true;
  state.result = null;
  controls();
  clearPlot($('#wave'));
  clearPlot($('#mfe'));
  $('#pc-result').textContent = 'Analisando…';
  $('#board-result').textContent = compare || capture ? 'Aguardando a placa…' : 'Sem medição nesta sessão';
  status(capture ? 'Após o aviso sonoro, reproduza o áudio perto da placa durante 3 segundos.' : 'Executando a rede neural…');
  try {
    const result = capture ? await api.capture($('#port').value) : await api.analyze(
      await toBase64(state.audio), Number($('#offset').value), compare, $('#port').value,
    );
    state.result = result;
    play(audioBlob(result.audio));
    if (capture && !result.capture.quality_ok) {
      $('#pc-result').textContent = 'Sem classificação: captura rejeitada';
      $('#board-result').textContent = result.capture.reason;
      return status('Ajuste volume ou distância e tente novamente. Não há previsão para esta captura.', true);
    }
    const experimental = Boolean(result.input.experimental);
    drawWave($('#wave'), result.waveform);
    drawMfe($('#mfe'), result.mfe);
    showPrediction($('#pc-result'), result, false, experimental);
    if (result.board) {
      showPrediction($('#board-result'), boardPrediction(result.board, result.threshold), true, experimental);
      status(`Concluído nos dois dispositivos. Diferença de escore: ${number(Math.abs(result.score - result.board.prob_present), 6)}.`);
    } else if (result.board_error) {
      state.connected = false;
      $('#connection').textContent = 'Placa desconectada. Conecte novamente para comparar.';
      $('#board-result').textContent = result.board_error;
      status('A análise do PC terminou. A comparação USB falhou e não gerou resultado da placa.', true);
    } else status('Análise concluída no PC.');
    $('#details').textContent = (result.input.conversion || result.input.source) +
      (result.input.padded ? '. Trecho completado com zeros.' : '') + '. Janela isolada de demonstração.';
  } catch (error) {
    $('#pc-result').textContent = 'Análise não concluída';
    $('#board-result').textContent = 'Sem resultado novo';
    status(error.message, true);
  } finally {
    state.busy = false;
    controls();
  }
}

async function refreshPorts() {
  const info = await api.info();
  $('#port').replaceChildren(new Option('Escolha automática', 'auto'));
  info.ports.forEach(port => $('#port').append(new Option(`${port.port}: ${port.description}`, port.port)));
  return info;
}

$('#connect').addEventListener('click', async () => {
  state.busy = true;
  controls();
  $('#connection').textContent = 'Procurando a placa e verificando o programa…';
  try {
    const requested = $('#port').value;
    await refreshPorts();
    if ([...$('#port').options].some(option => option.value === requested)) $('#port').value = requested;
    await api.connect($('#port').value);
    state.connected = true;
    $('#connection').textContent = 'Placa conectada e modelo verificado. A comparação está disponível.';
  } catch (error) {
    state.connected = false;
    $('#connection').textContent = error.message;
  } finally {
    state.busy = false;
    controls();
  }
});

$('.upload input').addEventListener('change', event => {
  const file = event.target.files[0];
  if (file) selectAudio(file, file.name);
});
$('#load-sample').addEventListener('click', async () => {
  const number = Number($('#sample-choice').value);
  if (!number) return status('Escolha um exemplo.', true);
  try {
    const response = await fetch(`/audio/${number}.wav`);
    if (!response.ok) throw new Error('O exemplo não foi encontrado.');
    const label = $('#sample-choice').selectedOptions[0].textContent;
    selectAudio(await response.blob(), label + ' • validation');
  } catch (error) { status(error.message, true); }
});
document.querySelectorAll('.tab').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('.pane').forEach(pane => { pane.hidden = pane.id !== button.dataset.pane; });
  document.querySelectorAll('.tab').forEach(tab => tab.classList.toggle('active', tab === button));
}));
$('#analyze').addEventListener('click', () => execute());
$('#compare').addEventListener('click', () => execute(true));
$('#capture').addEventListener('click', () => execute(false, true));
$('#download').addEventListener('click', () => {
  if (!state.result) return;
  const {audio, ...record} = state.result;
  const url = URL.createObjectURL(new Blob([JSON.stringify(record, null, 2)], {type: 'application/json'}));
  const link = document.createElement('a');
  link.href = url;
  link.download = `tinyml-demo-${Date.now()}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 3000);
});

(async () => {
  try {
    await refreshPorts();
    const catalog = await api.request('/api/examples');
    $('#sample-choice').replaceChildren(...catalog.examples.map(item => new Option(
      `Áudio ${item.number} · ${item.label_pt.toLowerCase()} (rótulo do grupo)`, item.number,
    )));
    const [evidence, benchmark] = await Promise.all([api.results(), api.benchmark()]);
    showEvidence(evidence, benchmark);
    const fresh = await api.request('/api/fresh-benchmark');
    const modes = [['cpu_float', 'CPU Float32 / TensorFlow'], ['gpu_float', 'RTX Float32 / TensorFlow'],
      ['cpu_float_lite', 'CPU Float32 / reference'], ['cpu_int8', 'CPU INT8 / reference'], ['board_int8', 'RP2040 INT8 / demo V3']];
    const table = document.createElement('table');
    const rows = [['Execução', 'Inference mediana (ms)', 'MFE + network (ms)'], ...modes.map(([key, title]) => [title,
      number(fresh.modes[key].summary.inference_ms.median_ms, 3), number(fresh.modes[key].summary.processing_ms.median_ms, 3)])];
    rows.forEach((values, index) => { const row = table.insertRow(); values.forEach(value => {
      const cell = document.createElement(index ? 'td' : 'th'); cell.textContent = value; row.append(cell);
    }); });
    $('#fresh-table').replaceChildren(table);
    drawBars($('#gpu-chart'), ['CPU Float32', 'RTX Float32'], ['cpu_float', 'gpu_float'].map(key => fresh.modes[key].summary.inference_ms.median_ms), 'Inference (ms)');
    drawBars($('#size-chart'), ['TFLite Float32', 'TFLite INT8'], [fresh.float_tflite_bytes, fresh.int8_tflite_bytes], 'Bytes');
    $('#fresh-explanation').textContent = 'Nesta sessão, a RTX não reduziu a latência individual. INT8 reduziu o arquivo em 34,1%, mas não foi mais rápido no resolver de referência da CPU. Float32 e INT8 mudaram a classe de 2/100 windows no mesmo threshold. CPU INT8 e placa tiveram os mesmos scores nas 100 windows. Isso é concordância de exemplos, não patient accuracy.';

  } catch (error) { status('Informações indisponíveis: ' + error.message, true); }
  controls();
})();
