import estado_operacional


def iniciar(configuracoes=None):
    print("Modulo de pedidos iniciado.")


def atuar(acao, objeto, entidade=None, comando=None):
    if acao == "verificar_pendentes" and objeto == "lista_entregas":
        return _verificar_pendentes(comando)

    if acao == "confirmar_entrega" and objeto == "pedido":
        return _confirmar_entrega(entidade, comando)

    return {"ok": False, "mensagem": f"Acao de pedidos nao suportada: {acao} {objeto}"}


def _verificar_pendentes(comando):
    pendentes = estado_operacional.listar_pedidos("pendente")
    codigos = ", ".join(pedido["id"] for pedido in pendentes) or "nenhum"
    estado_operacional.registrar_evento(
        "pedidos",
        "Lista de pedidos pendentes consultada.",
        {"quantidade": len(pendentes), "pedidos": codigos}
    )
    return {
        "ok": True,
        "mensagem": comando["resposta"],
        "detalhe": f"Pendentes: {len(pendentes)} | Codigos: {codigos}."
    }


def _confirmar_entrega(pedido_id, comando):
    pedido = estado_operacional.atualizar_pedido(pedido_id, status="entregue")
    if not pedido:
        return {"ok": False, "mensagem": f"Pedido {pedido_id} nao encontrado."}

    estado_operacional.registrar_evento(
        "pedidos",
        f"Entrega confirmada para o pedido {pedido_id}.",
        {"pedido": pedido}
    )
    return {
        "ok": True,
        "mensagem": comando["resposta"],
        "detalhe": f"Status do pedido {pedido_id}: entregue."
    }
