# DroneDash - Assistente de Despacho de Drones

Trabalho avaliativo da disciplina de Inteligencia Artificial - IFBA.

## Tema

Assistente virtual para um centro de distribuicao que utiliza drones em entregas rapidas. O mini-mundo simula comandos de voz para autorizacao de decolagem, consulta de bateria, cancelamento por mau tempo, retorno para recarga, verificacao de pedidos e rotinas auxiliares de monitoramento.

## Arquitetura

```text
Microfone / navegador
    -> gravacao temporaria em WAV
    -> Wav2Vec2 + Transformers
    -> texto transcrito
    -> tokenizacao e stopwords com NLTK
    -> validacao por comandos do config.json
    -> atuadores Python
    -> atualizacao de dashboard e relatorio JSON
```

## Comandos principais

- Autorizar decolagem do drone XY.
- Verificar nivel de bateria do drone ABC.
- Abortar decolagem do drone Z, mau tempo detectado.
- Retornar drone para base de recarga.
- Verificar pedidos pendentes na lista de entregas.

Tambem existem comandos para ligar/desligar o centro, iniciar/encerrar monitoramento da frota, iniciar/encerrar monitoramento meteorologico, despachar proxima entrega, confirmar entrega e registrar a operacao.

Todos os comandos, palavras-chave, atuadores, objetos e respostas ficam em `config.json`, fora do script principal.

## Como executar

Ambiente recomendado no Windows com Python 3.13:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
python inicializador_nltk.py
python assistente.py
```

A interface web roda em:

```text
http://localhost:7002
```

Para abrir a interface sem carregar o modelo de fala, util para demonstrar os comandos por texto:

```powershell
$env:ASSISTENTE_CARREGAR_MODELO="0"
python assistente.py
```

Se o ambiente global ja tiver sido afetado por downgrade de PyTorch, repare a matriz de versoes antes de executar:

```powershell
python -m pip install --upgrade --force-reinstall torch==2.11.0 torchaudio==2.11.0
python -m pip check
```

O projeto nao usa `torchvision`, mas essa biblioteca costuma estar instalada em ambientes de IA. A versao `torchvision==0.26.0` exige `torch==2.11.0`; por isso `requirements.txt` fixa `torch==2.11.0` e `torchaudio==2.11.0`.

## Testes

Suite completa, incluindo transcricao dos WAVs com Wav2Vec2:

```powershell
python -m unittest -v
```

Modo rapido sem carregar o modelo ASR:

```powershell
$env:DRONEDASH_PULAR_ASR="1"
python -m unittest -v
Remove-Item Env:\DRONEDASH_PULAR_ASR
```

Os testes cobrem configuracao JSON, reconhecimento por texto, variacoes por sinonimos, atuadores, respostas minimas, endpoint Flask, arquivos WAV de referencia, carregamento tecnico dos WAVs, transcricao real por ASR, execucao correta dos comandos reconhecidos a partir dos audios e compatibilidade entre `torch` e `torchaudio`.

## LGPD e SecOps

O projeto nao armazena nomes, enderecos, telefones ou dados pessoais de clientes. Os pedidos usam somente codigos operacionais (`P001`, `P002`). Arquivos temporarios de audio recebem nomes aleatorios, sao removidos apos processamento e o upload tem limite configurado no Flask.
