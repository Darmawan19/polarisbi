"""Pengaturan global tes: scheduler Insight selalu MATI (bawaan produksi = on, yang akan mengakses jaringan)."""
import os

os.environ["INSIGHT_SCHEDULER"] = "off"
