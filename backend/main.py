import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pyprojroot import here
root = here()
sys.path.append(root)
from backend.data_process.load_data import CryptoDataFeed
from backend.data_process.trans_pine_chart import apply_master_strategy