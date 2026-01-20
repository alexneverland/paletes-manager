import os
import sys

# =========================
# Base directory (DEV / EXE)
# =========================

def get_base_dir():
    # Αν τρέχουμε σαν EXE (PyInstaller)
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    # Αν τρέχουμε σαν script
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()

# =========================
# Paths
# =========================

SAVE_FOLDER = os.path.join(BASE_DIR, "data")
DB_FILENAME = "paletes.db"
DB_PATH = os.path.join(SAVE_FOLDER, DB_FILENAME)

# =========================
# App constants
# =========================

CARRIERS = ["ΔΙΑΚΙΝΗΣΗ", "ΜΑΓΛΟΥΣΙΔΗΣ", "ΚΑΣΣΟΥΔΑΚΗΣ", "ΔΙΑΦΟΡΑ"]

MAX_DAYS_HISTORY = 40
MAX_FUTURE_DAYS = 4

YES = "ΝΑΙ"
NO = "ΟΧΙ"

ITEM_PALLET = "Παλέτα"
ITEM_BOX = "Κιβώτιο"

PRED_TYPES = [ITEM_PALLET, ITEM_BOX]
LEFT_VALUES = [NO, YES]
