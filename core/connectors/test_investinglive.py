from core.connectors.investinglive import fetch_latest_articles


def main() -> None:
    print("=== TEST connecteur investinglive ===")
    print("Récupération de 3 articles section forex...\n")

    articles = fetch_latest_articles(
        section="forex",
        max_articles=3,
        fetch_full_text=True,
        delay_between_requests=1.0,
    )

    if not articles:
        print("Aucun article récupéré. Vérifier la connexion ou la structure du site.")
        return

    for i, article in enumerate(articles):
        print(f"--- Article {i+1} ---")
        print(f"Titre   : {article.title}")
        print(f"URL     : {article.url}")
        print(f"Texte   : {article.summary[:200]}...")
        print()

    print(f"Total récupéré : {len(articles)} articles")


if __name__ == "__main__":
    main()