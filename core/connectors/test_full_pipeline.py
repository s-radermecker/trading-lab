from core.connectors.investinglive import fetch_latest_articles
from core.macro_agent import analyze_text_to_market_info
from core.macro_pillar import build_macro_thesis


def main() -> None:
    print("=== PIPELINE COMPLET : investinglive → macro agent → thesis ===\n")

    articles = fetch_latest_articles(
        section="forex",
        max_articles=3,
        fetch_full_text=True,
        delay_between_requests=1.0,
    )

    if not articles:
        print("Aucun article récupéré.")
        return

    market_infos = []

    for i, article in enumerate(articles):
        print(f"--- Analyse article {i+1} : {article.title[:60]}...")
        info = analyze_text_to_market_info(
            raw_text=f"{article.title}\n\n{article.summary}",
            source_name="investinglive",
        )
        market_infos.append(info)
        print(f"    direction : {info.direction_hint}")
        print(f"    tags      : {info.tags}")
        print(f"    asset     : {info.asset_scope}")
        print()

    thesis = build_macro_thesis(
        info_objects=market_infos,
        asset_scope=["EURUSD"],
        thesis_id="investinglive_live_test",
    )

    print("=== THESIS MACRO TEMPS REEL ===")
    print(f"bias       : {thesis.directional_bias}")
    print(f"conviction : {thesis.conviction_score}")
    print(f"tradable   : {thesis.tradable}")
    print(f"state      : {thesis.state_label}")
    print(f"drivers    : {thesis.key_drivers}")
    print(f"summary    : {thesis.thesis_summary_short}")


if __name__ == "__main__":
    main()