from pathlib import Path
import json
import os
import re
import secrets
import unicodedata

from dotenv import load_dotenv
load_dotenv()

from inicializador_modelo import iniciar_modelo, possui_cuda
from transcritor import TAXA_AMOSTRAGEM, carregar_fala, transcrever_fala

import centro
import despacho
import estado_operacional
import frota
import meteorologia
import pedidos
import registro

try:
    from flask import Flask, Response, request, send_from_directory
except Exception:
    Flask = None
    Response = None
    request = None
    send_from_directory = None

BASE_DIR = Path(__file__).resolve().parent
CAMINHO_AUDIO_FALAS = BASE_DIR / "temp"
CONFIGURACOES = BASE_DIR / "config.json"
LINGUAGEM_PADRAO = "portuguese"
CANAIS = 1
TEMPO_GRAVACAO = 5

MODO_LINHA_DE_COMANDO = 1
MODO_WEB = 2
MODO_DE_FUNCIONAMENTO = MODO_WEB

ATUADORES = {
    "centro": centro,
    "despacho": despacho,
    "frota": frota,
    "meteorologia": meteorologia,
    "pedidos": pedidos,
    "registro": registro
}

STOPWORDS_FALLBACK = {
    "a", "ao", "aos", "as", "da", "das", "de", "do", "dos", "e",
    "em", "na", "nas", "no", "nos", "o", "os", "para", "por", "um",
    "uma", "com"
}


def carregar_configuracoes(caminho=CONFIGURACOES):
    with open(caminho, "r", encoding="utf-8") as arquivo:
        configuracoes = json.load(arquivo)
    validar_configuracoes(configuracoes)
    return configuracoes


def validar_configuracoes(configuracoes):
    comandos = configuracoes.get("comandos", [])
    if not comandos:
        raise ValueError("config.json deve conter a chave 'comandos'.")

    ids = set()
    campos_obrigatorios = {
        "id", "frase", "atuador", "acao", "objeto", "palavras", "resposta"
    }
    for comando in comandos:
        faltantes = campos_obrigatorios - set(comando)
        if faltantes:
            raise ValueError(f"Comando sem campos obrigatorios: {faltantes}")
        if comando["id"] in ids:
            raise ValueError(f"Comando duplicado no config.json: {comando['id']}")
        if comando["atuador"] not in ATUADORES:
            raise ValueError(f"Atuador nao cadastrado: {comando['atuador']}")
        ids.add(comando["id"])


def normalizar_texto(texto):
    texto = unicodedata.normalize("NFD", texto.lower())
    texto = "".join(char for char in texto if unicodedata.category(char) != "Mn")
    return texto


def tokenizar(texto):
    texto = normalizar_texto(texto)
    try:
        from nltk import word_tokenize

        tokens = word_tokenize(texto, language="portuguese")
    except Exception:
        tokens = re.findall(r"[a-zA-Z0-9]+", texto)
    return [token for token in tokens if re.fullmatch(r"[a-zA-Z0-9]+", token)]


def criar_palavras_de_parada(linguagem=LINGUAGEM_PADRAO):
    try:
        from nltk import corpus

        palavras = corpus.stopwords.words(linguagem)
        return {normalizar_texto(palavra) for palavra in palavras}
    except Exception:
        return set(STOPWORDS_FALLBACK)


def processar_transcricao(transcricao, palavras_de_parada):
    tokens = tokenizar(transcricao)
    return [
        token for token in tokens
        if token not in palavras_de_parada and token.isalnum()
    ]


def expandir_tokens(tokens, configuracoes):
    expandidos = set(tokens)
    sinonimos = configuracoes.get("nlu", {}).get("sinonimos", {})
    for canonico, variantes in sinonimos.items():
        canonico_norm = normalizar_texto(canonico)
        variantes_norm = {normalizar_texto(variante) for variante in variantes}
        if canonico_norm in expandidos or expandidos.intersection(variantes_norm):
            expandidos.add(canonico_norm)
            expandidos.update(variantes_norm)
    return expandidos


def validar_comando(tokens, configuracoes):
    tokens_expandidos = expandir_tokens(tokens, configuracoes)
    score_minimo = int(configuracoes.get("nlu", {}).get("score_minimo", 2))
    melhor_comando = None
    melhor_score = 0
    melhor_cobertura = 0.0

    for comando in configuracoes["comandos"]:
        palavras = {
            normalizar_texto(palavra)
            for palavra in comando.get("palavras", [])
        }
        score = sum(1 for palavra in palavras if palavra in tokens_expandidos)
        cobertura = score / max(len(palavras), 1)
        if (score, cobertura) > (melhor_score, melhor_cobertura):
            melhor_score = score
            melhor_cobertura = cobertura
            melhor_comando = comando

    if melhor_comando and melhor_score >= score_minimo:
        return True, melhor_comando, melhor_score
    return False, None, melhor_score


def iniciar(dispositivo=None, carregar_modelo=True):
    configuracoes = carregar_configuracoes()
    CAMINHO_AUDIO_FALAS.mkdir(exist_ok=True)

    estado_operacional.iniciar(configuracoes)
    for atuador in ATUADORES.values():
        atuador.iniciar(configuracoes)

    linguagem = configuracoes.get("assistente", {}).get("linguagem", LINGUAGEM_PADRAO)
    palavras_de_parada = criar_palavras_de_parada(linguagem)

    modelo = None
    processador = None
    modelo_iniciado = False
    if carregar_modelo:
        dispositivo = dispositivo or escolher_dispositivo()
        modelo_nome = configuracoes.get("assistente", {}).get("modelo_asr")
        modelo_iniciado, processador, modelo = iniciar_modelo(modelo_nome, dispositivo)
    else:
        dispositivo = dispositivo or "cpu"
        modelo_iniciado = True

    return {
        "iniciado": modelo_iniciado,
        "dispositivo": dispositivo,
        "processador": processador,
        "modelo": modelo,
        "palavras_de_parada": palavras_de_parada,
        "configuracoes": configuracoes,
        "modelo_carregado": carregar_modelo and modelo is not None
    }


def escolher_dispositivo():
    return "cuda:0" if possui_cuda() else "cpu"


def atuar(comando):
    atuador = ATUADORES[comando["atuador"]]
    resultado = atuador.atuar(
        comando["acao"],
        comando["objeto"],
        comando.get("entidade"),
        comando
    )
    return resultado


def executar_transcricao(transcricao, contexto):
    tokens = processar_transcricao(transcricao, contexto["palavras_de_parada"])
    valido, comando, score = validar_comando(tokens, contexto["configuracoes"])

    if not valido:
        return {
            "ok": False,
            "transcricao": transcricao,
            "tokens": tokens,
            "score": score,
            "feedback": "Comando nao reconhecido. Tente uma frase cadastrada no config.json.",
            "comando": None,
            "status": get_status()
        }

    resultado = atuar(comando)
    feedback = resultado.get("mensagem", comando["resposta"])
    if resultado.get("detalhe"):
        feedback = f"{feedback} {resultado['detalhe']}"

    return {
        "ok": bool(resultado.get("ok")),
        "transcricao": transcricao,
        "tokens": tokens,
        "score": score,
        "feedback": feedback,
        "comando": {
            "id": comando["id"],
            "acao": comando["acao"],
            "objeto": comando["objeto"],
            "entidade": comando.get("entidade"),
            "atuador": comando["atuador"]
        },
        "status": get_status()
    }


def get_status():
    estado = estado_operacional.get_estado()
    estado["registro"] = registro.get_estado()
    return estado


def capturar_fala():
    try:
        import sounddevice
    except Exception as erro:
        raise RuntimeError("sounddevice nao instalado. Instale requirements.txt.") from erro

    print("Fale o comando...")
    fala = sounddevice.rec(
        int(TEMPO_GRAVACAO * TAXA_AMOSTRAGEM),
        samplerate=TAXA_AMOSTRAGEM,
        channels=CANAIS
    )
    sounddevice.wait()
    print("Fala capturada.")
    return fala


def gravar_fala(fala):
    try:
        import soundfile
    except Exception as erro:
        raise RuntimeError("soundfile nao instalado. Instale requirements.txt.") from erro

    caminho = CAMINHO_AUDIO_FALAS / f"{secrets.token_hex(32)}.wav"
    soundfile.write(str(caminho), fala, TAXA_AMOSTRAGEM)
    return caminho


def ativar_linha_de_comando(contexto):
    if not contexto.get("modelo_carregado"):
        raise RuntimeError("Modo de linha de comando exige modelo ASR carregado.")

    while True:
        caminho = None
        try:
            caminho = gravar_fala(capturar_fala())
            transcricao = transcrever_fala(
                contexto["dispositivo"],
                carregar_fala(str(caminho)),
                contexto["modelo"],
                contexto["processador"]
            )
            resultado = executar_transcricao(transcricao, contexto)
            print(json.dumps(resultado, indent=2, ensure_ascii=False))
        finally:
            if caminho and caminho.exists():
                caminho.unlink()


if Flask:
    servico = Flask("assistente_despacho_drones", static_folder=str(BASE_DIR / "public"))
    limite_mb = carregar_configuracoes().get("assistente", {}).get("limite_upload_mb", 20)
    servico.config["MAX_CONTENT_LENGTH"] = int(limite_mb) * 1024 * 1024
else:
    servico = None


if servico:
    @servico.get("/")
    def acessar_pagina():
        return send_from_directory(BASE_DIR / "public", "index.html")


    @servico.get("/<path:caminho>")
    def acessar_pasta_estatica(caminho):
        return send_from_directory(BASE_DIR / "public", caminho)


    @servico.get("/status")
    def obter_status():
        contexto = servico.config["contexto"]
        status = get_status()
        status["modelo_carregado"] = contexto.get("modelo_carregado", False)
        return Response(
            json.dumps(status, ensure_ascii=False),
            status=200,
            content_type="application/json"
        )


    @servico.get("/comandos")
    def listar_comandos():
        contexto = servico.config["contexto"]
        comandos = [
            {
                "id": comando["id"],
                "frase": comando["frase"],
                "descricao": comando["descricao"]
            }
            for comando in contexto["configuracoes"]["comandos"]
        ]
        return Response(
            json.dumps(comandos, ensure_ascii=False),
            status=200,
            content_type="application/json"
        )


    @servico.post("/executar_texto")
    def executar_texto():
        dados = request.get_json(silent=True) or {}
        texto = dados.get("texto", "")
        if not texto:
            return Response(
                json.dumps({"erro": "Campo 'texto' e obrigatorio."}, ensure_ascii=False),
                status=400,
                content_type="application/json"
            )

        resultado = executar_transcricao(texto, servico.config["contexto"])
        return Response(
            json.dumps(resultado, ensure_ascii=False),
            status=200,
            content_type="application/json"
        )


    @servico.post("/reconhecer_comando")
    def reconhecer_comando():
        contexto = servico.config["contexto"]
        if not contexto.get("modelo_carregado"):
            return Response(
                json.dumps({
                    "erro": "Modelo ASR nao carregado. Reinicie o servidor com ASSISTENTE_CARREGAR_MODELO=1 no arquivo .env."
                }, ensure_ascii=False),
                status=503,
                content_type="application/json"
            )

        if "fala" not in request.files:
            return Response(status=400)

        caminho_arquivo = CAMINHO_AUDIO_FALAS / f"{secrets.token_hex(32)}.wav"
        request.files["fala"].save(caminho_arquivo)

        try:
            transcricao = transcrever_fala(
                contexto["dispositivo"],
                carregar_fala(str(caminho_arquivo)),
                contexto["modelo"],
                contexto["processador"]
            )
            resultado = executar_transcricao(transcricao, contexto)
            return Response(
                json.dumps(resultado, ensure_ascii=False),
                status=200,
                content_type="application/json"
            )
        except Exception as erro:
            return Response(
                json.dumps({"erro": str(erro)}, ensure_ascii=False),
                status=500,
                content_type="application/json"
            )
        finally:
            if caminho_arquivo.exists():
                caminho_arquivo.unlink()


def ativar_web(contexto):
    if not servico:
        raise RuntimeError("Flask nao esta instalado. Instale requirements.txt.")

    servico.config["contexto"] = contexto
    porta = contexto["configuracoes"].get("assistente", {}).get("porta", 7002)
    servico.run(host="0.0.0.0", port=int(porta))


if __name__ == "__main__":
    carregar_modelo = os.getenv("ASSISTENTE_CARREGAR_MODELO", "1") != "0"
    contexto = iniciar(carregar_modelo=carregar_modelo)

    if not contexto["iniciado"]:
        print("Ocorreu erro de inicializacao do assistente.")
    elif MODO_DE_FUNCIONAMENTO == MODO_WEB:
        ativar_web(contexto)
    else:
        ativar_linha_de_comando(contexto)
