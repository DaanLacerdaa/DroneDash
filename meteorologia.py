import random
import threading
import time

import estado_operacional

_thread_monitor = None
_parar_thread = threading.Event()


def iniciar(configuracoes=None):
    print("Modulo meteorologico iniciado.")


def atuar(acao, objeto, entidade=None, comando=None):
    if objeto != "monitoramento_meteorologico":
        return {"ok": False, "mensagem": "Objeto meteorologico nao reconhecido."}

    if acao == "iniciar":
        return _iniciar_monitoramento(comando)

    if acao == "encerrar":
        return _encerrar_monitoramento(comando)

    return {"ok": False, "mensagem": f"Acao meteorologica nao suportada: {acao}"}


def _iniciar_monitoramento(comando):
    global _thread_monitor
    estado_operacional.definir_monitoramento("meteorologico", True)
    _parar_thread.clear()
    if not _thread_monitor or not _thread_monitor.is_alive():
        _thread_monitor = threading.Thread(target=_simular_leituras, daemon=True)
        _thread_monitor.start()
    estado_operacional.registrar_evento("meteorologia", "Monitoramento meteorologico iniciado.")
    return {"ok": True, "mensagem": comando["resposta"]}


def _encerrar_monitoramento(comando):
    estado_operacional.definir_monitoramento("meteorologico", False)
    _parar_thread.set()
    estado_operacional.registrar_evento("meteorologia", "Monitoramento meteorologico encerrado.")
    return {"ok": True, "mensagem": comando["resposta"]}


def _simular_leituras():
    condicoes = [
        ("ceu_limpo", True),
        ("vento_moderado", True),
        ("chuva_intensa", False),
        ("baixa_visibilidade", False)
    ]
    while not _parar_thread.is_set():
        estado = estado_operacional.get_estado()
        if estado.get("monitoramentos", {}).get("meteorologico"):
            condicao, segura = random.choice(condicoes)
            meteorologia = estado_operacional.atualizar_meteorologia(
                condicao=condicao,
                vento_kmh=random.randint(8, 46),
                visibilidade_km=round(random.uniform(2.0, 10.0), 1),
                operacao_segura=segura
            )
            estado_operacional.registrar_evento(
                "meteorologia",
                "Leitura meteorologica simulada.",
                meteorologia
            )
        time.sleep(3)
