def inicializar_nltk():
    try:
        import nltk

        nltk.download("punkt", quiet=True)
        nltk.download("punkt_tab", quiet=True)
        nltk.download("stopwords", quiet=True)
        print("Recursos do NLTK inicializados.")
        return True
    except Exception as erro:
        print(f"erro inicializando NLTK: {erro}")
        return False


if __name__ == "__main__":
    inicializar_nltk()
