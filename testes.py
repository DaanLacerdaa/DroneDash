import io
import json
import os
import re
import time
import unittest
import wave
from pathlib import Path

import assistente
import estado_operacional
import registro
from transcritor import carregar_fala, transcrever_fala

BASE_DIR = Path(__file__).resolve().parent
PAUSA_ENTRE_TESTES = float(os.getenv("DRONEDASH_TEST_SLEEP", "0.15"))
PULAR_ASR = os.getenv("DRONEDASH_PULAR_ASR", "0") == "1"

AUDIO_CASOS = [
    ("ligar_centro_distribuicao", "ligar-centro-distribuicao.wav"),
    ("desligar_centro_distribuicao", "desligar-centro-distribuicao.wav"),
    ("autorizar_decolagem_drone_xy", "autorizar-decolagem-drone-xy.wav"),
    ("verificar_bateria_drone_abc", "verificar-bateria-drone-abc.wav"),
    ("abortar_decolagem_drone_z", "abortar-decolagem-drone-z.wav"),
    ("retornar_drone_base_recarga", "retornar-drone-base-recarga.wav"),
    ("verificar_pedidos_pendentes", "verificar-pedidos-pendentes.wav"),
    ("iniciar_monitoramento_meteorologico", "iniciar-monitoramento-meteorologico.wav"),
    ("encerrar_monitoramento_meteorologico", "encerrar-monitoramento-meteorologico.wav"),
    ("iniciar_monitoramento_frota", "iniciar-monitoramento-frota.wav"),
    ("encerrar_monitoramento_frota", "encerrar-monitoramento-frota.wav"),
    ("despachar_proxima_entrega", "despachar-proxima-entrega.wav"),
    ("confirmar_entrega_pedido_p001", "confirmar-entrega-pedido-p001.wav"),
    ("iniciar_registro_operacional", "iniciar-registro-operacional.wav"),
    ("encerrar_registro_operacional", "encerrar-registro-operacional.wav"),
]

RESPOSTAS_MINIMAS = {
    "autorizar_decolagem_drone_xy": "Autorizar decolagem do drone XY.",
    "verificar_bateria_drone_abc": "Verificar nivel de bateria do drone ABC.",
    "abortar_decolagem_drone_z": "Abortar decolagem do drone Z, mau tempo detectado.",
    "retornar_drone_base_recarga": "Retornar drone para base de recarga.",
    "verificar_pedidos_pendentes": "Verificar pedidos pendentes na lista de entregas.",
}


class BaseTesteAssistente(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contexto = assistente.iniciar(carregar_modelo=False)
        cls.configuracoes = cls.contexto["configuracoes"]
        cls.comandos_por_id = {
            comando["id"]: comando
            for comando in cls.configuracoes["comandos"]
        }

    def setUp(self):
        reiniciar_estado(self.configuracoes)

    def tearDown(self):
        time.sleep(PAUSA_ENTRE_TESTES)

    def executar(self, texto):
        return assistente.executar_transcricao(texto, self.contexto)

    def executar_comando_por_id(self, comando_id):
        reiniciar_estado(self.configuracoes)
        preparar_precondicao(comando_id, self.contexto)
        frase = self.comandos_por_id[comando_id]["frase"]
        resultado = self.executar(frase)
        validar_resultado_operacional(self, comando_id, resultado)
        return resultado


class Teste01Configuracao(BaseTesteAssistente):
    def testar_config_json_externo_e_completo(self):
        caminho = BASE_DIR / "config.json"
        self.assertTrue(caminho.exists())
        with open(caminho, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)

        self.assertEqual(dados["assistente"]["nome"], "DroneDash")
        self.assertEqual(len(dados["comandos"]), len(AUDIO_CASOS))
        self.assertIn("seguranca_lgpd", dados)

    def testar_comandos_sem_ids_duplicados(self):
        ids = [comando["id"] for comando in self.configuracoes["comandos"]]
        self.assertEqual(len(ids), len(set(ids)))

    def testar_todos_comandos_apontam_para_atuadores_validos(self):
        atuadores = set(assistente.ATUADORES)
        for comando in self.configuracoes["comandos"]:
            with self.subTest(comando=comando["id"]):
                self.assertIn(comando["atuador"], atuadores)
                self.assertGreaterEqual(len(comando["palavras"]), 3)
                self.assertTrue(comando["resposta"].strip())

    def testar_cada_comando_tem_audio_de_referencia(self):
        audios = {comando_id for comando_id, _ in AUDIO_CASOS}
        comandos = set(self.comandos_por_id)
        self.assertEqual(comandos, audios)


class Teste02ReconhecimentoTexto(BaseTesteAssistente):
    def testar_todos_comandos_do_json_sao_reconhecidos_por_texto(self):
        for comando in self.configuracoes["comandos"]:
            with self.subTest(comando=comando["id"]):
                tokens = assistente.processar_transcricao(
                    comando["frase"],
                    self.contexto["palavras_de_parada"]
                )
                valido, comando_detectado, score = assistente.validar_comando(
                    tokens,
                    self.configuracoes
                )
                self.assertTrue(valido)
                self.assertGreaterEqual(score, self.configuracoes["nlu"]["score_minimo"])
                self.assertEqual(comando_detectado["id"], comando["id"])

    def testar_variacoes_naturais_por_sinonimos(self):
        casos = {
            "autorizar partida do drone x y": "autorizar_decolagem_drone_xy",
            "consultar carga do drone a b c": "verificar_bateria_drone_abc",
            "verificar entregas pendentes": "verificar_pedidos_pendentes",
            "mandar drone para estacao de recarga": "retornar_drone_base_recarga",
        }
        for frase, comando_id in casos.items():
            with self.subTest(frase=frase):
                resultado = self.executar(frase)
                self.assertTrue(resultado["ok"], resultado["feedback"])
                self.assertEqual(resultado["comando"]["id"], comando_id)

    def testar_frase_fora_do_mini_mundo_e_rejeitada(self):
        resultado = self.executar("qual e a previsao da bolsa de valores")
        self.assertFalse(resultado["ok"])
        self.assertIsNone(resultado["comando"])


class Teste03ExecucaoTextoEAtuadores(BaseTesteAssistente):
    def testar_respostas_minimas_exigidas(self):
        for comando_id, resposta in RESPOSTAS_MINIMAS.items():
            with self.subTest(comando=comando_id):
                resultado = self.executar_comando_por_id(comando_id)
                self.assertIn(resposta, resultado["feedback"])

    def testar_todos_comandos_executam_atuadores_por_texto(self):
        for comando_id, _ in AUDIO_CASOS:
            with self.subTest(comando=comando_id):
                resultado = self.executar_comando_por_id(comando_id)
                self.assertEqual(resultado["comando"]["id"], comando_id)

    def testar_registro_operacional_gera_json_em_pasta_isolada(self):
        original = registro.PASTA_RELATORIOS
        registro.PASTA_RELATORIOS = BASE_DIR / "relatorios"
        self.addCleanup(setattr, registro, "PASTA_RELATORIOS", original)
        reiniciar_estado(self.configuracoes)

        arquivos_antes = set(registro.PASTA_RELATORIOS.glob("*.json"))
        self.assertTrue(self.executar("Iniciar registro operacional")["ok"])
        time.sleep(PAUSA_ENTRE_TESTES)
        resultado = self.executar("Encerrar registro operacional")
        self.assertTrue(resultado["ok"])

        arquivos_depois = set(registro.PASTA_RELATORIOS.glob("*.json"))
        novos = list(arquivos_depois - arquivos_antes)
        self.assertEqual(len(novos), 1)
        self.addCleanup(remover_arquivo, novos[0])

        with open(novos[0], "r", encoding="utf-8") as arquivo:
            relatorio = json.load(arquivo)
        self.assertEqual(relatorio["assistente"], "DroneDash")
        self.assertIn("lgpd", relatorio)


class Teste04ApiWeb(BaseTesteAssistente):
    def testar_endpoint_texto_executa_comando_e_retorna_status(self):
        if assistente.servico is None:
            self.skipTest("Flask nao instalado.")

        assistente.servico.config["contexto"] = self.contexto
        cliente = assistente.servico.test_client()
        resposta = cliente.post(
            "/executar_texto",
            json={"texto": "Verificar pedidos pendentes na lista de entregas"}
        )
        self.assertEqual(resposta.status_code, 200)
        dados = resposta.get_json()
        self.assertTrue(dados["ok"])
        self.assertEqual(dados["comando"]["id"], "verificar_pedidos_pendentes")
        self.assertIn("status", dados)

    def testar_endpoint_audio_recusa_quando_modelo_nao_esta_carregado(self):
        if assistente.servico is None:
            self.skipTest("Flask nao instalado.")

        assistente.servico.config["contexto"] = self.contexto
        cliente = assistente.servico.test_client()
        audio = criar_wav_vazio()
        resposta = cliente.post(
            "/reconhecer_comando",
            data={"fala": (audio, "fala.wav")},
            content_type="multipart/form-data"
        )
        self.assertEqual(resposta.status_code, 503)


class Teste05AudiosReferencia(unittest.TestCase):
    def tearDown(self):
        time.sleep(PAUSA_ENTRE_TESTES)

    def testar_audios_de_referencia_existentes_validos_e_mapeados(self):
        for comando_id, nome_audio in AUDIO_CASOS:
            audio = BASE_DIR / "audios" / nome_audio
            with self.subTest(comando=comando_id, audio=nome_audio):
                self.assertTrue(audio.exists(), f"Audio ausente: {audio}")
                self.assertGreater(audio.stat().st_size, 10_000)
                with wave.open(str(audio), "rb") as arquivo_wav:
                    self.assertEqual(arquivo_wav.getnchannels(), 1)
                    self.assertGreater(arquivo_wav.getframerate(), 0)
                    self.assertGreater(arquivo_wav.getnframes(), 0)

    def testar_carregamento_tecnico_de_todos_os_wavs(self):
        for comando_id, nome_audio in AUDIO_CASOS:
            audio = BASE_DIR / "audios" / nome_audio
            with self.subTest(comando=comando_id):
                fala = carregar_fala(str(audio))
                self.assertGreater(int(fala.numel()), 0)
                time.sleep(PAUSA_ENTRE_TESTES)


@unittest.skipIf(PULAR_ASR, "Teste ASR pulado por DRONEDASH_PULAR_ASR=1.")
class Teste06IntegracaoAudioASR(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contexto = assistente.iniciar(carregar_modelo=True)
        cls.configuracoes = cls.contexto["configuracoes"]
        cls.comandos_por_id = {
            comando["id"]: comando
            for comando in cls.configuracoes["comandos"]
        }
        if not cls.contexto["iniciado"] or not cls.contexto.get("modelo_carregado"):
            raise RuntimeError(
                "Modelo ASR nao carregado. Execute `python inicializador_modelo.py` "
                "ou rode com internet na primeira vez."
            )

    def setUp(self):
        reiniciar_estado(self.configuracoes)

    def tearDown(self):
        time.sleep(PAUSA_ENTRE_TESTES)

    def testar_todos_os_audios_sao_transcritos_e_executam_comandos(self):
        for comando_id, nome_audio in AUDIO_CASOS:
            with self.subTest(comando=comando_id, audio=nome_audio):
                reiniciar_estado(self.configuracoes)
                resultado = self.executar_audio(comando_id, nome_audio)
                self.assertEqual(resultado["comando"]["id"], comando_id)
                validar_resultado_operacional(self, comando_id, resultado)
                time.sleep(PAUSA_ENTRE_TESTES)

    def testar_endpoint_web_processa_audio_real(self):
        if assistente.servico is None:
            self.skipTest("Flask nao instalado.")

        reiniciar_estado(self.configuracoes)
        assistente.servico.config["contexto"] = self.contexto
        cliente = assistente.servico.test_client()
        audio = BASE_DIR / "audios" / "verificar-pedidos-pendentes.wav"

        with open(audio, "rb") as arquivo:
            resposta = cliente.post(
                "/reconhecer_comando",
                data={"fala": (arquivo, audio.name)},
                content_type="multipart/form-data"
            )

        self.assertEqual(resposta.status_code, 200)
        dados = resposta.get_json()
        self.assertTrue(dados["ok"], dados.get("feedback"))
        self.assertEqual(dados["comando"]["id"], "verificar_pedidos_pendentes")

    def executar_audio(self, comando_id, nome_audio):
        preparar_precondicao(comando_id, self.contexto)
        caminho_audio = BASE_DIR / "audios" / nome_audio
        fala = carregar_fala(str(caminho_audio))
        transcricao = transcrever_fala(
            self.contexto["dispositivo"],
            fala,
            self.contexto["modelo"],
            self.contexto["processador"]
        )
        self.assertIsInstance(transcricao, str)
        self.assertTrue(transcricao.strip(), f"Transcricao vazia para {nome_audio}.")

        resultado = assistente.executar_transcricao(transcricao, self.contexto)
        self.assertTrue(
            resultado["ok"],
            (
                f"Audio {nome_audio} nao executou comando. "
                f"Transcricao='{transcricao}' | Tokens={resultado['tokens']} | "
                f"Feedback={resultado['feedback']}"
            )
        )
        return resultado


class Teste07Dependencias(unittest.TestCase):
    def testar_torch_e_torchaudio_compativeis(self):
        import torch
        import torchaudio

        versao_torch = versao_base(torch.__version__)
        versao_torchaudio = versao_base(torchaudio.__version__)
        self.assertEqual(
            versao_torch,
            versao_torchaudio,
            "torch e torchaudio devem usar a mesma versao base."
        )


def reiniciar_estado(configuracoes):
    estado_operacional.iniciar(configuracoes)
    for atuador in assistente.ATUADORES.values():
        atuador.iniciar(configuracoes)


def preparar_precondicao(comando_id, contexto):
    precondicoes = {
        "desligar_centro_distribuicao": ["Ligar centro de distribuicao"],
        "encerrar_monitoramento_meteorologico": ["Iniciar monitoramento meteorologico"],
        "encerrar_monitoramento_frota": ["Iniciar monitoramento da frota"],
        "encerrar_registro_operacional": ["Iniciar registro operacional"],
    }
    for frase in precondicoes.get(comando_id, []):
        resultado = assistente.executar_transcricao(frase, contexto)
        if not resultado["ok"]:
            raise AssertionError(f"Falha na precondicao '{frase}': {resultado}")
        time.sleep(PAUSA_ENTRE_TESTES)


def validar_resultado_operacional(caso_teste, comando_id, resultado):
    caso_teste.assertTrue(resultado["ok"], resultado["feedback"])
    estado = estado_operacional.get_estado()

    if comando_id == "ligar_centro_distribuicao":
        caso_teste.assertTrue(estado["centro"]["ligado"])
    elif comando_id == "desligar_centro_distribuicao":
        caso_teste.assertFalse(estado["centro"]["ligado"])
    elif comando_id == "autorizar_decolagem_drone_xy":
        caso_teste.assertEqual(estado_operacional.obter_drone("XY")["status"], "decolagem_autorizada")
    elif comando_id == "verificar_bateria_drone_abc":
        caso_teste.assertIn("42%", resultado["feedback"])
    elif comando_id == "abortar_decolagem_drone_z":
        caso_teste.assertEqual(estado_operacional.obter_drone("Z")["status"], "decolagem_abortada")
    elif comando_id == "retornar_drone_base_recarga":
        caso_teste.assertTrue(
            any(drone["status"] == "retornando_recarga" for drone in estado["drones"].values())
        )
    elif comando_id == "verificar_pedidos_pendentes":
        caso_teste.assertIn("Pendentes: 3", resultado["feedback"])
    elif comando_id == "iniciar_monitoramento_meteorologico":
        caso_teste.assertTrue(estado["monitoramentos"]["meteorologico"])
    elif comando_id == "encerrar_monitoramento_meteorologico":
        caso_teste.assertFalse(estado["monitoramentos"]["meteorologico"])
    elif comando_id == "iniciar_monitoramento_frota":
        caso_teste.assertTrue(estado["monitoramentos"]["frota"])
    elif comando_id == "encerrar_monitoramento_frota":
        caso_teste.assertFalse(estado["monitoramentos"]["frota"])
    elif comando_id == "despachar_proxima_entrega":
        pedido_p001 = next(pedido for pedido in estado["pedidos"] if pedido["id"] == "P001")
        caso_teste.assertEqual(pedido_p001["status"], "em_rota")
        caso_teste.assertEqual(estado_operacional.obter_drone("XY")["pedido_atual"], "P001")
    elif comando_id == "confirmar_entrega_pedido_p001":
        pedido_p001 = next(pedido for pedido in estado["pedidos"] if pedido["id"] == "P001")
        caso_teste.assertEqual(pedido_p001["status"], "entregue")
    elif comando_id == "iniciar_registro_operacional":
        caso_teste.assertTrue(registro.get_estado()["ativo"])
    elif comando_id == "encerrar_registro_operacional":
        caso_teste.assertFalse(registro.get_estado()["ativo"])


def criar_wav_vazio():
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as arquivo_wav:
        arquivo_wav.setnchannels(1)
        arquivo_wav.setsampwidth(2)
        arquivo_wav.setframerate(16000)
        arquivo_wav.writeframes(b"\x00\x00" * 16000)
    buffer.seek(0)
    return buffer


def versao_base(versao):
    encontrada = re.match(r"(\d+\.\d+\.\d+)", versao)
    if not encontrada:
        return versao
    return encontrada.group(1)


def remover_arquivo(caminho):
    try:
        Path(caminho).unlink(missing_ok=True)
    except PermissionError:
        pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
