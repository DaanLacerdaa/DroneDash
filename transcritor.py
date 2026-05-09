TAXA_AMOSTRAGEM = 16_000


def carregar_fala(caminho_audio):
    try:
        import soundfile
        import torch
        import torchaudio
    except Exception as erro:
        raise RuntimeError(
            "Dependencias de audio ausentes. Instale requirements.txt para usar transcricao."
        ) from erro

    dados_audio, amostragem = soundfile.read(
        caminho_audio,
        dtype="float32",
        always_2d=True
    )
    audio = torch.from_numpy(dados_audio)
    if audio.shape[1] > 1:
        audio = torch.mean(audio, dim=1)
    else:
        audio = audio[:, 0]

    if amostragem != TAXA_AMOSTRAGEM:
        adaptador_amostragem = torchaudio.transforms.Resample(amostragem, TAXA_AMOSTRAGEM)
        audio = adaptador_amostragem(audio.unsqueeze(0)).squeeze(0)

    return audio.contiguous()


def transcrever_fala(dispositivo, fala, modelo, processador):
    try:
        import torch
    except Exception as erro:
        raise RuntimeError(
            "PyTorch ausente. Instale requirements.txt para usar transcricao."
        ) from erro

    entrada = processador(
        fala,
        return_tensors="pt",
        sampling_rate=TAXA_AMOSTRAGEM
    ).input_values.to(dispositivo)
    saida = modelo(entrada).logits
    predicao = torch.argmax(saida, dim=-1)
    transcricao = processador.batch_decode(predicao)[0]
    return transcricao.lower()
