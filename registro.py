import json
import os
from pathlib import Path
import time

import estado_operacional

BASE_DIR = Path(__file__).resolve().parent
PASTA_RELATORIOS = BASE_DIR / "relatorios"
_registro = {
    "ativo": False,
    "inicio": None,
    "data_inicio": None,
    "ultimo_relatorio": None
}


def iniciar(configuracoes=None):
    global _registro
    _registro = {
        "ativo": False,
        "inicio": None,
        "data_inicio": None,
        "ultimo_relatorio": _registro.get("ultimo_relatorio")
    }
    os.makedirs(PASTA_RELATORIOS, exist_ok=True)
    print("Modulo de registro operacional iniciado.")


def atuar(acao, objeto, entidade=None, comando=None):
    if objeto != "registro_operacional":
        return {"ok": False, "mensagem": "Objeto de registro nao reconhecido."}

    if acao == "iniciar":
        return _iniciar_registro(comando)

    if acao == "encerrar":
        return _encerrar_registro(comando)

    return {"ok": False, "mensagem": f"Acao de registro nao suportada: {acao}"}


def _iniciar_registro(comando):
    if _registro["ativo"]:
        return {"ok": True, "mensagem": "Registro operacional ja esta em andamento."}

    _registro["ativo"] = True
    _registro["inicio"] = time.time()
    _registro["data_inicio"] = estado_operacional.agora()
    estado_operacional.registrar_evento("registro", "Registro operacional iniciado.")
    return {"ok": True, "mensagem": comando["resposta"]}


def _encerrar_registro(comando):
    if not _registro["ativo"]:
        return {"ok": False, "mensagem": "Nenhum registro operacional em andamento."}

    estado = estado_operacional.get_estado()
    relatorio = {
        "assistente": "DroneDash",
        "data_inicio": _registro["data_inicio"],
        "data_fim": estado_operacional.agora(),
        "duracao_s": round(time.time() - _registro["inicio"], 1),
        "lgpd": estado.get("seguranca_lgpd", {}),
        "resumo_operacional": {
            "centro": estado.get("centro"),
            "monitoramentos": estado.get("monitoramentos"),
            "meteorologia": estado.get("meteorologia")
        },
        "drones": estado.get("drones"),
        "pedidos": estado.get("pedidos"),
        "eventos": estado.get("eventos", [])[-100:]
    }

    nome_arquivo = f"relatorio_drones_{time.strftime('%Y%m%d_%H%M%S')}_{int(time.time() * 1000) % 1000}.json"
    caminho = PASTA_RELATORIOS / nome_arquivo
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(relatorio, arquivo, indent=4, ensure_ascii=False)

    _registro["ativo"] = False
    _registro["inicio"] = None
    _registro["ultimo_relatorio"] = str(caminho)
    estado_operacional.registrar_evento("registro", f"Registro operacional salvo em {caminho}.")
    return {
        "ok": True,
        "mensagem": comando["resposta"],
        "detalhe": f"Arquivo: {caminho}."
    }


def get_estado():
    return dict(_registro)
