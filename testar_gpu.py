from inicializador_modelo import possui_cuda


if __name__ == "__main__":
    if possui_cuda():
        print("CUDA disponivel para inferencia do Wav2Vec2.")
    else:
        print("CUDA indisponivel. O assistente usara CPU.")
