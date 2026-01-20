import os

CARRIERS = ["ΔΙΑΚΙΝΗΣΗ", "ΜΑΓΛΟΥΣΙΔΗΣ", "ΚΑΣΣΟΥΔΑΚΗΣ", "ΔΙΑΦΟΡΑ"]

SAVE_FOLDER = "data"
DB_FILENAME = "paletes.db"
DB_PATH = os.path.join(SAVE_FOLDER, DB_FILENAME)

MAX_DAYS_HISTORY = 40
MAX_FUTURE_DAYS = 4

YES = "ΝΑΙ"
NO = "ΟΧΙ"

ITEM_PALLET = "Παλέτα"
ITEM_BOX = "Κιβώτιο"

PRED_TYPES = [ITEM_PALLET, ITEM_BOX]
LEFT_VALUES = [NO, YES]
