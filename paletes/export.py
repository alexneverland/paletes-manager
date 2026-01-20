import os
import tempfile
import webbrowser
from datetime import datetime


def export_dataframe_to_excel(df, filename_prefix):

    if df.empty:
        return None, "EMPTY"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{filename_prefix}_{timestamp}.xlsx"

    desktop = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
    save_dir = desktop if os.path.isdir(desktop) else tempfile.gettempdir()
    save_path = os.path.join(save_dir, filename)

    df.to_excel(save_path, index=False)
    webbrowser.open(f"file://{os.path.realpath(save_path)}")

    return save_path, None
