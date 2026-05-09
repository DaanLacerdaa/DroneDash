import estado_operacional


def iniciar(configuracoes=None):
    print("Modulo de monitoramento de frota iniciado.")


def atuar(acao, objeto, entidade=None, comando=None):
    if acao == "verificar_bateria" and objeto == "drone":
        return _verificar_bateria(entidade, comando)

    if acao == "iniciar" and objeto == "monitoramento_frota":
        estado_operacional.definir_monitoramento("frota", True)
        estado_operacional.registrar_evento("frota", "Monitoramento da frota iniciado.")
        return {"ok": True, "mensagem": comando["resposta"]}

    if acao == "encerrar" and objeto == "monitoramento_frota":
        estado_operacional.definir_monitoramento("frota", False)
        estado_operacional.registrar_evento("frota", "Monitoramento da frota encerrado.")
        return {"ok": True, "mensagem": comando["resposta"]}

    return {"ok": False, "mensagem": f"Acao de frota nao suportada: {acao} {objeto}"}


def _verificar_bateria(drone_id, comando):
    drone = estado_operacional.obter_drone(drone_id)
    if not drone:
        return {"ok": False, "mensagem": f"Drone {drone_id} nao encontrado."}

    bateria = int(drone.get("bateria_percentual", 0))
    estado_operacional.registrar_evento(
        "frota",
        f"Bateria consultada para o drone {drone_id}.",
        {"drone_id": drone_id, "bateria_percentual": bateria}
    )
    return {
        "ok": True,
        "mensagem": comando["resposta"],
        "detalhe": f"Bateria atual: {bateria}% | Status: {drone.get('status', 'indefinido')}."
    }
