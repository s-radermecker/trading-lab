from core.pipeline_v2 import run_pipeline_v2


def main() -> None:
    print("=== PIPELINE V2 — TEMPS REEL COMPLET ===\n")

    result = run_pipeline_v2(
        asset_scope=["EURUSD", "USDJPY", "GBPUSD"],
        pipeline_id="v2_live_test_001",
        news_section="forex",
        max_articles=3,
    )

    print("\n=== RESULTATS ===\n")
    print(f"Articles analysés  : {result['articles_analyzed']}")
    print(f"Sources            : {result['sources']}")
    print()

    g = result["global"]
    print(f"--- GLOBAL THESIS ---")
    print(f"bias               : {g['global_bias']}")
    print(f"conviction         : {g['global_conviction']}")
    print(f"trade permission   : {g['trade_permission']}")
    print(f"trigger state      : {g['trigger_state']}")
    print(f"state label        : {g['state_label']}")
    print(f"summary            : {g['summary_short']}")
    print()

    e = result["execution"]
    print(f"--- EXECUTION ---")
    print(f"permission state   : {e.get('execution_permission', 'n/a')}")
    print(f"next step          : {e.get('next_step', 'n/a')}")
    print(f"executable         : {e.get('executable', 'n/a')}")


if __name__ == "__main__":
    main()