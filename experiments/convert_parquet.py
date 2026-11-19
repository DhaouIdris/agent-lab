"""Convert the downloaded Parquet mirror to a local CSV (requires pandas, pyarrow)."""
from pathlib import Path
import pandas as pd

source=Path('local_data/lieux.parquet')
destination=Path('local_data/lieux.csv')
if not source.is_file():raise SystemExit('Fichier local_data/lieux.parquet absent.')
if destination.exists():raise SystemExit('Fichier CSV déjà présent : choisir un nouveau dossier.')
frame=pd.read_parquet(source)
frame.to_csv(destination,index=False,encoding='utf-8')
print(f'Export CSV : {len(frame)} lignes')
