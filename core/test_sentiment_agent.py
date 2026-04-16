from core.sentiment_agent import analyze_sentiment_from_text, analyze_sentiments_from_texts
from core.sentiment_pillar import build_sentiment_thesis
from core.connectors.investinglive import fetch_latest_articles


def main() -> None:
    print("=== TEST 1 : sentiment depuis texte brut ===\n")

    text_1 = """
    Risk sentiment has deteriorated sharply this morning as equities sold off across
    all major markets. The VIX spiked above 25 and traders are rushing to safe haven
    assets including JPY, CHF and gold. Risk-off tone is dominant with carry trades
    being unwound aggressively. Retail positioning shows extreme long exposure
    in AUD and NZD which could amplify the downside.
    """

    info_1 = analyze_sentiment_from_text(
        raw_text=text_1,
        source_name="test_manual",
    )

    print(f"title      : {info_1.title}")
    print(f"direction  : {info_1.direction_hint}")
    print(f"tags       : {info_1.tags}")
    print(f"importance : {info_1.importance_score}")
    print()

    print("=== TEST 2 : sentiment depuis articles investinglive en temps reel ===\n")

    articles = fetch_latest_articles(
        section="forex",
        max_articles=3,
        fetch_full_text=True,
        delay_between_requests=1.0,
    )

    if not articles:
        print("Aucun article récupéré.")
        return

    infos = analyze_sentiments_from_texts(
        texts=[f"{a.title}\n\n{a.summary}" for a in articles],
        source_name="investinglive",
    )

    for i, info in enumerate(infos):
        print(f"--- article {i+1} ---")
        print(f"title     : {info.title}")
        print(f"direction : {info.direction_hint}")
        print(f"tags      : {info.tags}")
        print()

    print("=== THESIS SENTIMENT TEMPS REEL ===\n")

    thesis = build_sentiment_thesis(
        info_objects=infos,
        asset_scope=["EURUSD", "USDJPY", "AUDUSD"],
        thesis_id="sentiment_live_test",
    )

    print(f"bias       : {thesis.directional_bias}")
    print(f"conviction : {thesis.conviction_score}")
    print(f"tradable   : {thesis.tradable}")
    print(f"state      : {thesis.state_label}")
    print(f"drivers    : {thesis.key_drivers}")
    print(f"summary    : {thesis.thesis_summary_short}")


if __name__ == "__main__":
    main()