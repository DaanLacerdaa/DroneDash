import estado_operacional


def iniciar(configuracoes=None):
    print("Modulo de despacho de drones iniciado.")


def atuar(acao, objeto, entidade=None, comando=None):
    if objeto not in {"drone", "lista_entregas"}:
        return {"ok": False, "mensagem": "Objeto de despacho nao reconhecido."}

    if acao == "autorizar_decolagem":
        return _autorizar_decolagem(entidade, comando)

    if acao == "abortar_decolagem":
        return _abortar_decolagem(entidade, comando)

    if acao == "retornar_base_recarga":
        return _retornar_base_recarga(comando)

    if acao == "despachar_proxima_entrega":
        return _despachar_proxima_entrega(comando)

    return {"ok": False, "mensagem": f"Acao de despacho nao suportada: {acao}"}


def _autorizar_decolagem(drone_id, comando):
    drone = estado_operacional.obter_drone(drone_id)
    if not drone:
        return {"ok": False, "mensagem": f"Drone {drone_id} nao encontrado."}

    atualizado = estado_operacional.atualizar_drone(
        drone_id,
        status="decolagem_autorizada"
    )
    estado_operacional.registrar_evento(
        "despacho",
        f"Decolagem autorizada para o drone {drone_id}.",
        {"drone": atualizado}
    )
    return {
        "ok": True,
        "mensagem": comando["resposta"],
        "detalhe": f"Status atual: {atualizado['status']}."
    }


def _abortar_decolagem(drone_id, comando):
    drone = estado_operacional.obter_drone(drone_id)
    if not drone:
        return {"ok": False, "mensagem": f"Drone {drone_id} nao encontrado."}

    meteorologia = estado_operacional.get_estado().get("meteorologia", {})
    atualizado = estado_operacional.atualizar_drone(
        drone_id,
        status="decolagem_abortada"
    )
    estado_operacional.registrar_evento(
        "despacho",
        f"Decolagem abortada para o drone {drone_id}.",
        {"drone": atualizado, "meteorologia": meteorologia}
    )
    return {
        "ok": True,
        "mensagem": comando["resposta"],
        "detalhe": (
            f"Condicao: {meteorologia.get('condicao', 'indefinida')}; "
            f"vento: {meteorologia.get('vento_kmh', 0)} km/h."
        )
    }


def _retornar_base_recarga(comando):
    drone = estado_operacional.selecionar_drone_para_recarga()
    if not drone:
        return {"ok": False, "mensagem": "Nenhum drone cadastrado para retorno."}

    atualizado = estado_operacional.atualizar_drone(
        drone["id"],
        status="retornando_recarga"
    )
    estado_operacional.registrar_evento(
        "despacho",
        f"Drone {drone['id']} retornando para base de recarga.",
        {"drone": atualizado}
    )
    return {
        "ok": True,
        "mensagem": comando["resposta"],
        "detalhe": f"Drone selecionado: {drone['id']} | Base: {drone.get('base', 'N/D')}."
    }


def _despachar_proxima_entrega(comando):
    pedido = estado_operacional.selecionar_pedido_pendente()
    drone = estado_operacional.selecionar_drone_disponivel()

    if not pedido:
        return {"ok": False, "mensagem": "Nao ha pedidos pendentes para despacho."}
    if not drone:
        return {"ok": False, "mensagem": "Nao ha drone disponivel com bateria minima para despacho."}

    estado_operacional.atualizar_pedido(pedido["id"], status="em_rota")
    atualizado = estado_operacional.atualizar_drone(
        drone["id"],
        status="em_rota",
        pedido_atual=pedido["id"]
    )
    estado_operacional.registrar_evento(
        "despacho",
        f"Pedido {pedido['id']} despachado com drone {drone['id']}.",
        {"pedido": pedido, "drone": atualizado}
    )
    return {
        "ok": True,
        "mensagem": comando["resposta"],
        "detalhe": f"Pedido {pedido['id']} atribuido ao drone {drone['id']}."
    }
