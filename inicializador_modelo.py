MODELOS = ["lgris/wav2vec2-large-xlsr-open-brazilian-portuguese-v2"]


def iniciar_modelo(nome_modelo, dispositivo="cpu"):
    """Carrega o modelo Wav2Vec2 somente quando a execucao exigir ASR."""
    iniciado, processador, modelo = False, None, None

    try:
        from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

        processador = Wav2Vec2Processor.from_pretrained(nome_modelo)
        modelo = Wav2Vec2ForCTC.from_pretrained(nome_modelo).to(dispositivo)
        iniciado = True
    except Exception as erro:
        print(f"erro iniciando modelo: {erro}")

    return iniciado, processador, modelo


def possui_cuda():
    try:
        import torch

        return torch.cuda.is_available()
    except Exception:
        return False


if __name__ == "__main__":
    dispositivo = "cuda:0" if possui_cuda() else "cpu"
    for modelo in MODELOS:
        iniciado, _, __ = iniciar_modelo(modelo, dispositivo)
        if iniciado:
            print(f"modelo {modelo} iniciado com sucesso em {dispositivo}")
