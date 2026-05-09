import estado_operacional


def iniciar(configuracoes=None):
    print("Modulo do centro de distribuicao iniciado.")


def atuar(acao, objeto, entidade=None, comando=None):
    if objeto != "centro_distribuicao":
        return {"ok": False, "mensagem": "Objeto operacional nao reconhecido."}

    if acao == "ligar":
        estado_operacional.atualizar_centro(True)
        estado_operacional.registrar_evento("centro", "Centro de distribuicao ligado.")
        return {"ok": True, "mensagem": comando["resposta"]}

    if acao == "desligar":
        estado_operacional.atualizar_centro(False)
        estado_operacional.registrar_evento("centro", "Centro de distribuicao desligado.")
        return {"ok": True, "mensagem": comando["resposta"]}

    return {"ok": False, "mensagem": f"Acao nao suportada pelo centro: {acao}"}
