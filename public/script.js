const recordButton = document.getElementById('recordButton');
const micState = document.getElementById('micState');
const textCommandForm = document.getElementById('textCommandForm');
const textCommand = document.getElementById('textCommand');
const transcriptionText = document.getElementById('transcriptionText');
const feedbackBox = document.getElementById('feedbackBox');
const feedbackText = document.getElementById('feedbackText');
const logList = document.getElementById('logList');
const clearLogButton = document.getElementById('clearLogButton');
const commandList = document.getElementById('commandList');

let audioContext;
let audioStream;
let audioSource;
let processor;
let buffers = [];
let recording = false;

recordButton.addEventListener('click', async () => {
    if (recording) {
        stopRecording();
        return;
    }
    await startRecording();
});

textCommandForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const texto = textCommand.value.trim();
    if (!texto) return;
    await executeTextCommand(texto);
});

clearLogButton.addEventListener('click', () => {
    logList.replaceChildren();
    addLog('Log local limpo.', 'info');
});

async function startRecording() {
    try {
        audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        audioSource = audioContext.createMediaStreamSource(audioStream);
        processor = audioContext.createScriptProcessor(4096, 1, 1);
        buffers = [];

        processor.onaudioprocess = (event) => {
            const channel = event.inputBuffer.getChannelData(0);
            buffers.push(new Float32Array(channel));
        };

        audioSource.connect(processor);
        processor.connect(audioContext.destination);
        recording = true;
        recordButton.classList.add('recording');
        micState.textContent = 'Gravando... pressione para parar';
        addLog('Gravacao iniciada.', 'info');
    } catch (error) {
        addLog(`Falha ao acessar microfone: ${error.message}`, 'error');
    }
}

async function stopRecording() {
    recording = false;
    recordButton.classList.remove('recording');
    recordButton.classList.add('processing');
    micState.textContent = 'Processando audio...';

    if (processor) processor.disconnect();
    if (audioSource) audioSource.disconnect();
    if (audioStream) audioStream.getTracks().forEach((track) => track.stop());

    const wavBlob = encodeWav(mergeBuffers(buffers), audioContext.sampleRate);
    await audioContext.close();

    const formData = new FormData();
    formData.append('fala', wavBlob, 'fala.wav');

    try {
        const response = await fetch('/reconhecer_comando', {
            method: 'POST',
            body: formData
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.erro || `HTTP ${response.status}`);
        renderCommandResult(payload);
    } catch (error) {
        showFeedback(`Erro no reconhecimento: ${error.message}`, false);
        addLog(`Erro no reconhecimento: ${error.message}`, 'error');
    } finally {
        recordButton.classList.remove('processing');
        micState.textContent = 'Pressione para gravar';
    }
}

async function executeTextCommand(texto) {
    try {
        const response = await fetch('/executar_texto', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ texto })
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.erro || `HTTP ${response.status}`);
        renderCommandResult(payload);
    } catch (error) {
        showFeedback(`Erro de comunicacao: ${error.message}`, false);
        addLog(`Erro de comunicacao: ${error.message}`, 'error');
    }
}

function renderCommandResult(payload) {
    transcriptionText.textContent = payload.transcricao || '(sem transcricao)';
    showFeedback(payload.feedback || 'Sem resposta operacional.', payload.ok);

    const comando = payload.comando ? payload.comando.id : 'nao reconhecido';
    addLog(`${comando}: ${payload.feedback}`, payload.ok ? 'success' : 'warn');
    if (payload.status) renderStatus(payload.status);
}

function showFeedback(message, ok) {
    feedbackBox.classList.toggle('success', Boolean(ok));
    feedbackBox.classList.toggle('error', !ok);
    feedbackText.textContent = message;
}

async function pollStatus() {
    try {
        const response = await fetch('/status');
        if (!response.ok) return;
        const status = await response.json();
        renderStatus(status);
        // modelo_carregado ausente (undefined) = servidor sem o campo, assume disponivel
        if (status.modelo_carregado === false) {
            setAudioAvailable(false);
        } else {
            setAudioAvailable(true);
        }
    } catch {
        setSystemState(false);
    }
}

function setAudioAvailable(available) {
    if (available) {
        recordButton.disabled = false;
        recordButton.title = 'Gravar comando de voz';
        if (!recording) micState.textContent = 'Pressione para gravar';
    } else {
        recordButton.disabled = true;
        recordButton.title = 'Audio indisponivel: reinicie o servidor com ASSISTENTE_CARREGAR_MODELO=1 no .env';
        micState.textContent = 'Audio indisponivel — reinicie o servidor com ASSISTENTE_CARREGAR_MODELO=1';
    }
}

async function loadCommands() {
    try {
        const response = await fetch('/comandos');
        if (!response.ok) return;
        const comandos = await response.json();
        commandList.replaceChildren();
        comandos.forEach((comando) => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'command-item';
            item.title = comando.descricao;
            item.textContent = comando.frase;
            item.addEventListener('click', () => {
                textCommand.value = comando.frase;
                executeTextCommand(comando.frase);
            });
            commandList.appendChild(item);
        });
    } catch {
        addLog('Nao foi possivel carregar os comandos.', 'warn');
    }
}

function renderStatus(status) {
    setSystemState(true, status.centro && status.centro.ligado);

    const pedidos = status.pedidos || [];
    const pendentes = pedidos.filter((pedido) => pedido.status === 'pendente');
    document.getElementById('pendingOrders').textContent = pendentes.length;
    document.getElementById('fleetMonitor').textContent = status.monitoramentos?.frota ? 'SIM' : 'NAO';
    document.getElementById('weatherSafe').textContent = status.meteorologia?.operacao_segura ? 'SIM' : 'NAO';

    const meteorologia = status.meteorologia || {};
    document.getElementById('weatherCondition').textContent = meteorologia.condicao || '-';
    document.getElementById('weatherWind').textContent = `${meteorologia.vento_kmh ?? '-'} km/h`;
    document.getElementById('weatherVisibility').textContent = `${meteorologia.visibilidade_km ?? '-'} km`;

    renderDrones(status.drones || {});
}

function setSystemState(serverOnline, centerOnline = false) {
    const dot = document.getElementById('systemDot');
    const label = document.getElementById('systemLabel');
    dot.className = 'state-dot';
    if (!serverOnline) {
        label.textContent = 'Servidor offline';
        document.getElementById('centerStatus').textContent = 'OFFLINE';
        return;
    }

    dot.classList.add(centerOnline ? 'online' : 'standby');
    label.textContent = centerOnline ? 'Centro online' : 'Servidor online';
    document.getElementById('centerStatus').textContent = centerOnline ? 'ONLINE' : 'STANDBY';
}

function renderDrones(drones) {
    const droneList = document.getElementById('droneList');
    droneList.replaceChildren();

    Object.values(drones).forEach((drone) => {
        const item = document.createElement('article');
        item.className = 'drone-card';

        const title = document.createElement('strong');
        title.textContent = `Drone ${drone.id}`;

        const status = document.createElement('span');
        status.textContent = drone.status;

        const battery = document.createElement('div');
        battery.className = 'battery';
        const fill = document.createElement('i');
        fill.style.width = `${Math.max(0, Math.min(100, drone.bateria_percentual))}%`;
        battery.appendChild(fill);

        const detail = document.createElement('p');
        detail.textContent = `Bateria ${drone.bateria_percentual}% | Base ${drone.base}`;

        item.append(title, status, battery, detail);
        droneList.appendChild(item);
        updatePin(drone);
    });
}

function updatePin(drone) {
    const pin = document.getElementById(`pin${drone.id}`);
    if (!pin) return;
    pin.dataset.status = drone.status;
    pin.title = `Drone ${drone.id}: ${drone.status} (${drone.bateria_percentual}%)`;
}

function addLog(message, type = 'info') {
    const item = document.createElement('div');
    item.className = `log-entry ${type}`;

    const time = document.createElement('span');
    time.textContent = new Date().toLocaleTimeString('pt-BR');

    const text = document.createElement('p');
    text.textContent = message;

    item.append(time, text);
    logList.appendChild(item);
    logList.scrollTop = logList.scrollHeight;
}

function mergeBuffers(chunks) {
    const length = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
    const result = new Float32Array(length);
    let offset = 0;
    chunks.forEach((chunk) => {
        result.set(chunk, offset);
        offset += chunk.length;
    });
    return result;
}

function encodeWav(samples, sampleRate) {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);
    writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + samples.length * 2, true);
    writeString(view, 8, 'WAVE');
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeString(view, 36, 'data');
    view.setUint32(40, samples.length * 2, true);

    let offset = 44;
    for (let i = 0; i < samples.length; i += 1) {
        const sample = Math.max(-1, Math.min(1, samples[i]));
        view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
        offset += 2;
    }
    return new Blob([view], { type: 'audio/wav' });
}

function writeString(view, offset, value) {
    for (let i = 0; i < value.length; i += 1) {
        view.setUint8(offset + i, value.charCodeAt(i));
    }
}

addLog('Interface pronta para comandos.', 'info');
loadCommands();
pollStatus();
setInterval(pollStatus, 2500);
