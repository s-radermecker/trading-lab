from pathlib import Path
import pandas as pd

# === PARAMÈTRES ===
input_folder = Path.home() / "Desktop" / "Trading Lab" / "Sample" / "EURUSD"
output_file = Path.home() / "Desktop" / "Trading Lab" / "Sample" / "EURUSD_M15.csv"

csv_files = sorted(input_folder.glob("*.csv"))

if not csv_files:
    raise ValueError(f"Aucun fichier CSV trouvé dans {input_folder}")

all_dfs = []

for file in csv_files:
    print(f"Lecture : {file.name}")

    df = pd.read_csv(
        file,
        header=None,
        names=["DatePart", "TimePart", "Open", "High", "Low", "Close", "Volume"]
    )

    df["Datetime"] = pd.to_datetime(
        df["DatePart"].astype(str).str.strip() + " " + df["TimePart"].astype(str).str.strip(),
        format="%Y.%m.%d %H:%M",
        errors="coerce"
    )

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["Datetime", "Open", "High", "Low", "Close"])
    df = df[["Datetime", "Open", "High", "Low", "Close", "Volume"]].copy()

    all_dfs.append(df)

full_df = pd.concat(all_dfs, ignore_index=True)
full_df = full_df.drop_duplicates(subset=["Datetime"])
full_df = full_df.sort_values("Datetime").reset_index(drop=True)

m15_df = (
    full_df.set_index("Datetime")
    .resample("15min")
    .agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum"
    })
    .dropna(subset=["Open", "High", "Low", "Close"])
    .reset_index()
)

m15_df["Date"] = m15_df["Datetime"].dt.strftime("%Y.%m.%d %H:%M")
m15_df = m15_df[["Date", "Open", "High", "Low", "Close", "Volume"]]

output_file.parent.mkdir(parents=True, exist_ok=True)
m15_df.to_csv(output_file, index=False)

print(f"\nFichier exporté : {output_file}")
print(f"Nombre de bougies M15 : {len(m15_df)}")
print("\nAperçu :")
print(m15_df.head())
print(m15_df.tail())