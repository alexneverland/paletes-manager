import tkinter as tk
from paletes.ui import PaletesApp

def main():
    root = tk.Tk()
    try:
        PaletesApp(root)
    except RuntimeError:
        root.destroy()
        return
    root.mainloop()

if __name__ == "__main__":
    main()
