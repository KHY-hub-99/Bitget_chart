import pandas as pd
from data_process.indicator_engine import MasterIndicatorEngine

def apply_master_strategy(df: pd.DataFrame) -> pd.DataFrame:
    engine = MasterIndicatorEngine()
    return engine.calculate_indicators(df)