from copy import deepcopy
from threading import RLock
import time

_lock = RLock()
_estado = {}


def agora():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def iniciar(configuracoes):
    """Inicializa o estado compartilhado da simulacao."""
    global _estado
    with _lock:
        _estado = {
            "centro": {
                "ligado": False,
                "inicio": None
            },
            "drones": {
                drone["id"].upper(): deepcopy(drone)
                for drone in configuracoes.get("drones", [])
            },
            "pedidos": deepcopy(configuracoes.get("pedidos", [])),
            "meteorologia": deepcopy(configuracoes.get("meteorologia", {})),
            "monitoramentos": {
                "frota": False,
                "meteorologico": False
            },
            "eventos": [],
            "seguranca_lgpd": deepcopy(configuracoes.get("seguranca_lgpd", {}))
        }
    registrar_evento("sistema", "Estado operacional inicializado.")


def registrar_evento(tipo, mensagem, dados=None):
    with _lock:
        evento = {
            "timestamp": agora(),
            "tipo": tipo,
            "mensagem": mensagem,
            "dados": dados or {}
        }
        _estado.setdefault("eventos", []).append(evento)
        _estado["eventos"] = _estado["eventos"][-200:]
        return deepcopy(evento)


def get_estado():
    with _lock:
        return deepcopy(_estado)


def atualizar_centro(ligado):
    with _lock:
        _estado["centro"]["ligado"] = ligado
        _estado["centro"]["inicio"] = time.time() if ligado else None


def definir_monitoramento(nome, ativo):
    with _lock:
        _estado["monitoramentos"][nome] = ativo


def obter_drone(drone_id):
    with _lock:
        return deepcopy(_estado["drones"].get(str(drone_id).upper()))


def atualizar_drone(drone_id, **campos):
    drone_id = str(drone_id).upper()
    with _lock:
        if drone_id not in _estado["drones"]:
            return None
        _estado["drones"][drone_id].update(campos)
        return deepcopy(_estado["drones"][drone_id])


def listar_pedidos(status=None):
    with _lock:
        pedidos = deepcopy(_estado.get("pedidos", []))
    if status is None:
        return pedidos
    return [pedido for pedido in pedidos if pedido.get("status") == status]


def atualizar_pedido(pedido_id, **campos):
    pedido_id = str(pedido_id).upper()
    with _lock:
        for pedido in _estado.get("pedidos", []):
            if pedido.get("id", "").upper() == pedido_id:
                pedido.update(campos)
                return deepcopy(pedido)
    return None


def selecionar_pedido_pendente():
    prioridade = {"alta": 0, "media": 1, "baixa": 2}
    pendentes = listar_pedidos("pendente")
    if not pendentes:
        return None
    return sorted(
        pendentes,
        key=lambda pedido: (
            prioridade.get(pedido.get("prioridade"), 99),
            pedido.get("id", "")
        )
    )[0]


def selecionar_drone_disponivel(bateria_minima=50):
    with _lock:
        drones = deepcopy(_estado.get("drones", {}))
    candidatos = [
        drone for drone in drones.values()
        if drone.get("status") in {"em_espera", "decolagem_pendente"}
        and int(drone.get("bateria_percentual", 0)) >= bateria_minima
    ]
    if not candidatos:
        return None
    return sorted(
        candidatos,
        key=lambda drone: int(drone.get("bateria_percentual", 0)),
        reverse=True
    )[0]


def selecionar_drone_para_recarga():
    with _lock:
        drones = deepcopy(_estado.get("drones", {}))
    candidatos = [
        drone for drone in drones.values()
        if drone.get("status") in {"em_rota", "decolagem_autorizada", "decolagem_pendente"}
    ]
    if not candidatos:
        candidatos = list(drones.values())
    if not candidatos:
        return None
    return sorted(candidatos, key=lambda drone: int(drone.get("bateria_percentual", 0)))[0]


def atualizar_meteorologia(**campos):
    with _lock:
        _estado["meteorologia"].update(campos)
        return deepcopy(_estado["meteorologia"])
