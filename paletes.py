import tkinter as tk
from tkinter import ttk, messagebox
import csv # Δεν χρησιμοποιείται άμεσα, ίσως για μελλοντική χρήση;
import os
from datetime import datetime, timedelta
import webbrowser
import tempfile
import pandas as pd
# import operator # Δεν χρησιμοποιείται, μπορεί να αφαιρεθεί
import sqlite3

CARRIERS = ["ΔΙΑΚΙΝΗΣΗ", "ΜΑΓΛΟΥΣΙΔΗΣ", "ΚΑΣΣΟΥΔΑΚΗΣ", "ΔΙΑΦΟΡΑ"]
SAVE_FOLDER = "data"
DB_PATH = os.path.join(SAVE_FOLDER, "paletes.db")
MAX_DAYS_HISTORY = 40
MAX_FUTURE_DAYS = 4

if not os.path.exists(SAVE_FOLDER):
    os.makedirs(SAVE_FOLDER)

class PaletesApp:
    def copy_main_selected(self, carrier):
        if self.current_mode != "main": return
        selected_item_id = self.tables[carrier].selection()
        if not selected_item_id:
            messagebox.showwarning("Προσοχή", "Επιλέξτε μια εγγραφή για αντιγραφή.")
            return
        values = self.tables[carrier].item(selected_item_id[0], "values")
        if not values or len(values) < 6:
            messagebox.showerror("Σφάλμα", "Δεν ήταν δυνατή η ανάγνωση των δεδομένων για αντιγραφή.")
            return
        code_val = values[0].replace("✓ ", "").strip()
        name_val = values[1]
        invoice_val = ""
        left_val = values[3]
        boxes_val = values[4]
        comments_val = values[5]
        conn = self.get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                sql_insert = """
                    INSERT INTO entries (entry_date, carrier, code, name, invoice, left, boxes, comments)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """
                cursor.execute(sql_insert, (
                    self.current_date.strftime('%Y-%m-%d'), carrier, code_val, name_val,
                    invoice_val, left_val, boxes_val, comments_val
                ))
                conn.commit()
                # messagebox.showinfo("Επιτυχία", f"Η εγγραφή αντιγράφηκε για την {self.current_date.strftime('%Y-%m-%d')}.")
            except sqlite3.IntegrityError as e:
                messagebox.showerror("Σφάλμα Βάσης", f"Πρόβλημα αντιγραφής (πιθανόν διπλότυπος κωδικός): {e}")
            except Exception as e:
                messagebox.showerror("Σφάλμα", f"Πρόβλημα κατά την αντιγραφή: {e}")
            finally:
                conn.close()
        self.load_main_data(self.current_date)

    def __init__(self, root):
        self.root = root
        self.root.title("Διαχείριση Παλετών")
        ttk.Style().theme_use('clam')
        self.root.geometry("1100x800")

        self.current_date = datetime.today().date()
        self.data = {c: [] for c in CARRIERS}
        self.prediction_data = {c: [] for c in CARRIERS}

        self.main_widgets = {c: {} for c in CARRIERS}
        self.prediction_widgets = {c: {} for c in CARRIERS}

        self.entries = {}
        self.tables = {}
        self.summary_labels = {c: {} for c in CARRIERS}
        self.add_update_btns = {}
        self.delete_btns = {}

        self.main_edit_btns = {}
        self.main_cancel_btns = {}
        self.prediction_edit_btns = {}
        self.prediction_cancel_btns = {}

        self.carrier_frames = {}
        self.main_frames = {}
        self.prediction_frames = {}

        self.edit_mode = False
        self.item_being_edited = {c: None for c in CARRIERS}

        self.sort_column = {c: None for c in CARRIERS}
        self.sort_direction = {c: 'asc' for c in CARRIERS}

        self.main_column_map = {"code": 0, "name": 1, "invoice": 2, "left": 3, "boxes": 4, "comments": 5}
        self.prediction_column_map = {"name": 0, "item_type": 1, "count": 2, "comments": 3}

        self.name_tag_map = {}
        self.color_list = ["#F0F8FF", "#F0FFFF", "#F5F5DC", "#FFE4C4", "#E0FFFF", "#FAFAD2", "#D3D3D3"]
        self.color_index_counter = 0

        self.name_vars = {c: tk.StringVar() for c in CARRIERS}
        self.name_combobox_values = {c: [] for c in CARRIERS}
        self.prediction_count_vars = {c: tk.StringVar() for c in CARRIERS}
        self.prediction_type_vars = {c: tk.StringVar(value="Παλέτα") for c in CARRIERS}

        self.current_mode = "main"
        self.mode_button = None; self.export_btn = None; self.canvas = None
        self.carriers_frame = None; self.canvas_window_id = None

        self.init_database()
        self.clean_old_data_from_db()
        self.create_widgets()
        self.set_mode("main")
        self.update_name_combobox_values()
        self.root.after(60000, self.auto_refresh)

    def get_db_connection(self):
        conn = None
        try:
            conn = sqlite3.connect(DB_PATH)
            return conn
        except sqlite3.Error as e:
            messagebox.showerror("Σφάλμα Βάσης", f"Σύνδεση απέτυχε: {e}")
            return None

    def init_database(self):
        conn = self.get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS entries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, entry_date TEXT NOT NULL, carrier TEXT NOT NULL,
                        code TEXT, name TEXT, invoice TEXT, left TEXT, boxes TEXT, comments TEXT
                    )""")
                try: cursor.execute("ALTER TABLE entries ADD COLUMN comments TEXT;")
                except sqlite3.OperationalError: pass
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS predictions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, entry_date TEXT NOT NULL, carrier TEXT NOT NULL,
                        name TEXT, item_type TEXT, count INTEGER, comments TEXT
                    )""")
                try: cursor.execute("ALTER TABLE predictions ADD COLUMN comments TEXT;")
                except sqlite3.OperationalError: pass
                conn.commit()
            except sqlite3.Error as e: messagebox.showerror("Σφάλμα Βάσης", f"Αρχικοποίηση πινάκων: {e}")
            finally: conn.close()

    def filter_names(self, event, carrier, cb):
        # Αν πατηθεί Tab, Shift, Ctrl, Alt, Enter, αγνοούμε το event για το φιλτράρισμα
        if event.keysym in ("Tab", "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Return", "KP_Enter"):
            return
        
        current_input = cb.get().lower()
        all_names = self.name_combobox_values.get(carrier, [])
        
        # Φιλτράρουμε τις τιμές του combobox βάσει της εισαγωγής
        filtered = [name for name in all_names if name.lower().startswith(current_input)]
        
        # Ενημερώνουμε τις τιμές του combobox με τις φιλτραρισμένες
        # Είναι σημαντικό να διατηρήσουμε την τρέχουσα τιμή που έχει πληκτρολογήσει ο χρήστης,
        # ακόμα κι αν δεν ταιριάζει ακριβώς με κάποια από τις φιλτραρισμένες τιμές,
        # ώστε να μπορεί να εισάγει νέο όνομα.
        current_text = cb.get() # Παίρνουμε την τρέχουσα τιμή από το πεδίο
        cb['values'] = filtered # Ενημερώνουμε τη λίστα του dropdown
        
        # Επαναφορά της τιμής που πληκτρολογούσε ο χρήστης, αν το φιλτράρισμα την άλλαξε
        # (Αυτό συνήθως δεν είναι απαραίτητο καθώς η τιμή στο entry δεν αλλάζει από την cb['values'])
        # cb.set(current_text) # Αυτή η γραμμή μπορεί να είναι και περιττή.

        # --- ΑΦΑΙΡΕΣΗ ΤΟΥ ΑΥΤΟΜΑΤΟΥ ΑΝΟΙΓΜΑΤΟΣ ΤΟΥ DROPDOWN ---
        # if filtered and current_input: 
            # cb.event_generate('<Down>') # Αυτή η γραμμή προκαλούσε το αυτόματο άνοιγμα
        # --- ΤΕΛΟΣ ΑΦΑΙΡΕΣΗΣ ---
        
        # Ο χρήστης μπορεί να ανοίξει το dropdown πατώντας το κάτω βελάκι στο πληκτρολόγιο
        # ή κάνοντας κλικ στο βελάκι του widget.

    def create_widgets(self):
        nav_frame = tk.Frame(self.root); nav_frame.pack(pady=5)
        self.prev_btn = tk.Button(nav_frame, text="←", command=self.prev_day); self.prev_btn.pack(side=tk.LEFT)
        self.date_label = tk.Label(nav_frame, text=str(self.current_date)); self.date_label.pack(side=tk.LEFT, padx=10)
        self.next_btn = tk.Button(nav_frame, text="→", command=self.next_day); self.next_btn.pack(side=tk.LEFT)
        self.mode_button = tk.Button(nav_frame, text="Πρόβλεψη Παλετών", command=self.toggle_mode); self.mode_button.pack(side=tk.LEFT, padx=10)
        self.refresh_btn = tk.Button(nav_frame, text="Ανανέωση", command=self.refresh_data); self.refresh_btn.pack(side=tk.LEFT, padx=10)
        self.export_btn = tk.Button(self.root, text="Εξαγωγή σε Excel (Κύρια Δεδομένα)", command=self.export_current_mode_to_excel); self.export_btn.pack(pady=5)
        self.canvas = tk.Canvas(self.root); self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.carriers_frame = tk.Frame(self.canvas)
        self.canvas_window_id = self.canvas.create_window((0, 0), window=self.carriers_frame, anchor="nw")

        for carrier in CARRIERS:
            carrier_frame = tk.LabelFrame(self.carriers_frame, text=carrier, padx=5, pady=5)
            carrier_frame.pack(side=tk.LEFT, fill=tk.Y, expand=False, padx=1, pady=5)
            self.carrier_frames[carrier] = carrier_frame
            main_frame = tk.Frame(carrier_frame); self.main_frames[carrier] = main_frame
            prediction_frame = tk.Frame(carrier_frame); prediction_frame.pack_forget(); self.prediction_frames[carrier] = prediction_frame
            self.populate_main_carrier_frame(carrier, main_frame)
            self.populate_prediction_carrier_frame(carrier, prediction_frame)

        self.canvas.update_idletasks()
        required_width = sum(frame.winfo_reqwidth() for frame in self.carrier_frames.values())
        padding_width = (len(CARRIERS) -1) * 2 + 40
        required_width += padding_width
        self.canvas.itemconfig(self.canvas_window_id, width=required_width, height=self.carriers_frame.winfo_reqheight())
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

    def populate_main_carrier_frame(self, carrier, frame):
        entry_frame = tk.Frame(frame); entry_frame.pack(pady=2, fill=tk.X)
        tk.Label(entry_frame, text="Κωδ. Παλέτας").grid(row=0, column=0, sticky="w", padx=1)
        tk.Label(entry_frame, text="Όνομα").grid(row=0, column=1, sticky="w", padx=1)
        tk.Label(entry_frame, text="Τιμολόγια").grid(row=0, column=2, sticky="w", padx=1)
        tk.Label(entry_frame, text="Έφυγε").grid(row=0, column=3, sticky="w", padx=1)
        tk.Label(entry_frame, text="Κιβώτια").grid(row=0, column=4, sticky="w", padx=1)
        code_entry = tk.Entry(entry_frame, width=6); code_entry.grid(row=1, column=0, padx=1, pady=1, sticky="ew")
        name_cb = ttk.Combobox(entry_frame, textvariable=self.name_vars[carrier], values=[], width=7, state="normal")
        name_cb.bind("<KeyRelease>", lambda event, c=carrier, cb=name_cb: self.filter_names(event, c, cb))
        name_cb.grid(row=1, column=1, padx=1, pady=1, sticky="ew")
        invoice_entry = tk.Entry(entry_frame, width=4); invoice_entry.grid(row=1, column=2, padx=1, pady=1, sticky="ew")
        left_var = tk.StringVar(value="ΟΧΙ")
        left_cb = ttk.Combobox(entry_frame, textvariable=left_var, values=["ΟΧΙ", "ΝΑΙ"], width=3, state="readonly")
        left_cb.grid(row=1, column=3, padx=1, pady=1, sticky="ew")
        boxes_entry = tk.Entry(entry_frame, width=3); boxes_entry.grid(row=1, column=4, padx=1, pady=1, sticky="ew")
        tk.Label(entry_frame, text="Σχόλια").grid(row=2, column=0, sticky="w", padx=1, pady=2)
        comments_text_main = tk.Text(entry_frame, height=2, width=1); comments_text_main.grid(row=3, column=0, columnspan=5, padx=1, pady=1, sticky="ew")
        for i in range(5): entry_frame.grid_columnconfigure(i, weight=1)
        self.main_widgets[carrier]['entries'] = (code_entry, name_cb, invoice_entry, left_cb, boxes_entry, comments_text_main) # left_cb αντί left_var για το bind
        
        button_frame = tk.Frame(frame); button_frame.pack(pady=2)
        main_add_update_btn = tk.Button(button_frame, text="Προσθήκη", command=lambda c=carrier: self.handle_main_add_update(c))
        main_add_update_btn.pack(side=tk.LEFT, padx=1); self.main_widgets[carrier]['add_update_btn'] = main_add_update_btn
        main_edit_btn = tk.Button(button_frame, text="Επεξεργασία", command=lambda c=carrier: self.enter_main_edit_mode(c))
        main_edit_btn.pack(side=tk.LEFT, padx=1); self.main_edit_btns[carrier] = main_edit_btn
        main_cancel_btn = tk.Button(button_frame, text="Ακύρωση", command=lambda c=carrier: self.exit_main_edit_mode(c))
        self.main_cancel_btns[carrier] = main_cancel_btn # Δεν το κάνουμε pack ακόμα
        main_delete_btn = tk.Button(button_frame, text="Διαγραφή", command=lambda c=carrier: self.delete_main_selected(c))
        main_delete_btn.pack(side=tk.LEFT, padx=1); self.main_widgets[carrier]['delete_btn'] = main_delete_btn; main_delete_btn.config(state=tk.DISABLED)
        copy_btn = tk.Button(button_frame, text="Αντιγραφή", command=lambda c=carrier: self.copy_main_selected(c))
        copy_btn.pack(side=tk.LEFT, padx=1); self.main_widgets[carrier]['copy_btn'] = copy_btn
        
        # Κλήση bind_enter_to_tab_and_submit για την κύρια λειτουργία
        self.bind_enter_to_tab_and_submit(
            [code_entry, name_cb, invoice_entry, left_cb, boxes_entry, comments_text_main],
            main_add_update_btn
        )
        
        table = ttk.Treeview(frame, columns=("code", "name", "invoice", "left", "boxes", "comments"), show="headings", height=32)
        main_columns_info = [
            ("code", "Κωδ.Παλέτας", 60), ("name", "Όνομα", 80), ("invoice", "Τιμολόγια", 50),
            ("left", "Έφυγε", 50), ("boxes", "Κιβώτια", 40), ("comments", "Σχόλια", 150)
        ]
        for col, text, width in main_columns_info:
            table.heading(col, text=text, anchor=tk.CENTER, command=lambda c=carrier, _col=col: self.sort_column_handler(c, _col))
            table.column(col, width=width, anchor=tk.CENTER, stretch=tk.YES)
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=table.yview)
        table.configure(yscrollcommand=scrollbar.set); scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        table.pack(pady=2, fill=tk.BOTH, expand=True)
        table.bind("<Double-1>", self.toggle_left_status)
        table.bind("<<TreeviewSelect>>", self.on_item_select)
        self.main_widgets[carrier]['table'] = table
        pallet_summary_frame = tk.Frame(frame); pallet_summary_frame.pack(pady=1)
        self.main_widgets[carrier]['summary_labels_pal'] = {}
        lbl_total_pal = tk.Label(pallet_summary_frame); lbl_total_pal.pack(side=tk.LEFT, padx=1); self.main_widgets[carrier]['summary_labels_pal']['total_pal'] = lbl_total_pal
        lbl_departed_pal = tk.Label(pallet_summary_frame); lbl_departed_pal.pack(side=tk.LEFT, padx=1); self.main_widgets[carrier]['summary_labels_pal']['departed_pal'] = lbl_departed_pal
        lbl_not_dep_pal = tk.Label(pallet_summary_frame, fg="red"); lbl_not_dep_pal.pack(side=tk.LEFT, padx=1); self.main_widgets[carrier]['summary_labels_pal']['not_departed_pal'] = lbl_not_dep_pal
        box_summary_frame = tk.Frame(frame); box_summary_frame.pack(pady=1)
        self.main_widgets[carrier]['summary_labels_box'] = {}
        lbl_total_box = tk.Label(box_summary_frame); lbl_total_box.pack(side=tk.LEFT, padx=1); self.main_widgets[carrier]['summary_labels_box']['total_box'] = lbl_total_box
        lbl_departed_box = tk.Label(box_summary_frame); lbl_departed_box.pack(side=tk.LEFT, padx=1); self.main_widgets[carrier]['summary_labels_box']['departed_box'] = lbl_departed_box
        lbl_not_dep_box = tk.Label(box_summary_frame, fg="red"); lbl_not_dep_box.pack(side=tk.LEFT, padx=1); self.main_widgets[carrier]['summary_labels_box']['not_departed_box'] = lbl_not_dep_box
        lbl_sum_inv = tk.Label(frame); lbl_sum_inv.pack(pady=1); self.main_widgets[carrier]['summary_labels_inv'] = {'sum_inv': lbl_sum_inv}

    def populate_prediction_carrier_frame(self, carrier, frame):
        entry_frame = tk.Frame(frame); entry_frame.pack(pady=2)
        tk.Label(entry_frame, text="Όνομα").grid(row=0, column=0, sticky="w", padx=1)
        tk.Label(entry_frame, text="Ποσότητα").grid(row=0, column=1, sticky="w", padx=1)
        tk.Label(entry_frame, text="Είδος").grid(row=0, column=2, sticky="w", padx=1)
        
        name_cb_pred = ttk.Combobox(entry_frame, textvariable=self.name_vars[carrier], values=[], width=10, state="normal")
        # Bind για φιλτράρισμα ονόματος στην πρόβλεψη
        name_cb_pred.bind("<KeyRelease>", lambda event, c=carrier, cb=name_cb_pred: self.filter_names(event, c, cb))
        name_cb_pred.grid(row=1, column=0, padx=1, pady=1)
        
        count_entry_pred = tk.Entry(entry_frame, textvariable=self.prediction_count_vars[carrier], width=5)
        count_entry_pred.grid(row=1, column=1, padx=1, pady=1)
        
        item_type_cb_pred = ttk.Combobox(entry_frame, textvariable=self.prediction_type_vars[carrier], values=["Παλέτα", "Κιβώτιο"], width=8, state="readonly")
        item_type_cb_pred.grid(row=1, column=2, padx=1, pady=1)
        
        tk.Label(entry_frame, text="Σχόλια").grid(row=2, column=0, sticky="w", padx=1, pady=2, columnspan=3)
        comments_text_prediction = tk.Text(entry_frame, height=2, width=20)
        comments_text_prediction.grid(row=3, column=0, columnspan=3, padx=1, pady=1, sticky="ew")
        
        self.prediction_widgets[carrier]['entries'] = (name_cb_pred, count_entry_pred, item_type_cb_pred) # Τα πεδία που συμμετέχουν στο tabbing
        self.prediction_widgets[carrier]['comments_text'] = comments_text_prediction

        button_frame = tk.Frame(frame); button_frame.pack(pady=2)
        pred_add_update_btn = tk.Button(button_frame, text="Προσθήκη", command=lambda c=carrier: self.handle_prediction_add_update(c))
        pred_add_update_btn.pack(side=tk.LEFT, padx=1); self.prediction_widgets[carrier]['add_update_btn'] = pred_add_update_btn
        pred_edit_btn = tk.Button(button_frame, text="Επεξεργασία", command=lambda c=carrier: self.enter_prediction_edit_mode(c))
        pred_edit_btn.pack(side=tk.LEFT, padx=1); self.prediction_edit_btns[carrier] = pred_edit_btn
        pred_cancel_btn = tk.Button(button_frame, text="Ακύρωση", command=lambda c=carrier: self.exit_prediction_edit_mode(c))
        self.prediction_cancel_btns[carrier] = pred_cancel_btn # Δεν το κάνουμε pack ακόμα
        pred_delete_btn = tk.Button(button_frame, text="Διαγραφή", command=lambda c=carrier: self.delete_prediction_selected(c))
        pred_delete_btn.pack(side=tk.LEFT, padx=1); self.prediction_widgets[carrier]['delete_btn'] = pred_delete_btn; pred_delete_btn.config(state=tk.DISABLED)

        # Κλήση bind_enter_to_tab_and_submit για τη λειτουργία πρόβλεψης
        # Η λίστα περιλαμβάνει και το comments_text_prediction ως το τελευταίο στοιχείο
        self.bind_enter_to_tab_and_submit(
            [name_cb_pred, count_entry_pred, item_type_cb_pred, comments_text_prediction],
            pred_add_update_btn
        )

        table = ttk.Treeview(frame, columns=("name", "item_type", "count", "comments"), show="headings", height=30)
        prediction_columns_info = [
            ("name", "Όνομα", 90), ("item_type", "Είδος", 55),
            ("count", "Ποσότητα", 55), ("comments", "Σχόλια", 120)
        ]
        for col, text, width in prediction_columns_info:
            table.heading(col, text=text, anchor=tk.CENTER, command=lambda c=carrier, _col=col: self.sort_column_handler(c, _col))
            table.column(col, width=width, anchor=tk.CENTER, stretch=tk.YES)
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=table.yview)
        table.configure(yscrollcommand=scrollbar.set); scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        table.pack(pady=2, fill=tk.BOTH, expand=True)
        table.bind("<<TreeviewSelect>>", self.on_item_select)
        self.prediction_widgets[carrier]['table'] = table
        summary_frame = tk.Frame(frame); summary_frame.pack(pady=1)
        self.prediction_widgets[carrier]['summary_labels'] = {}
        lbl_total_pal = tk.Label(summary_frame); lbl_total_pal.pack(side=tk.LEFT, padx=1); self.prediction_widgets[carrier]['summary_labels']['total_pal'] = lbl_total_pal
        lbl_total_box = tk.Label(summary_frame); lbl_total_box.pack(side=tk.LEFT, padx=1); self.prediction_widgets[carrier]['summary_labels']['total_box'] = lbl_total_box

    def toggle_mode(self):
        # ... (без изменений)
        if self.edit_mode:
            for carrier_in_edit in CARRIERS:
                if self.item_being_edited.get(carrier_in_edit) is not None:
                    if self.current_mode == "main": self.exit_main_edit_mode(carrier_in_edit)
                    elif self.current_mode == "prediction": self.exit_prediction_edit_mode(carrier_in_edit)
                    break
        if self.current_mode == "main": self.set_mode("prediction")
        else: self.set_mode("main")

    def bind_enter_to_tab_and_submit(self, entry_widgets, add_btn):
        # ... (η λογική παραμένει ίδια, είναι ήδη γενική)
        for i, widget in enumerate(entry_widgets):
            # Για τα Combobox που είναι readonly (π.χ. Έφυγε, Είδος Πρόβλεψης), το Enter δεν πρέπει να κάνει tab
            # αλλά να προχωράει ή να υποβάλλει αν είναι το τελευταίο.
            # Ωστόσο, η τρέχουσα λογική εφαρμόζει tab για όλα τα Entry/Combobox.
            # Αυτό μπορεί να παραμείνει για συνέπεια ή να γίνει πιο εξειδικευμένο.
            if isinstance(widget, (tk.Entry, ttk.Combobox)):
                # Ελέγχουμε αν το Combobox είναι readonly. Αν ναι, ίσως να μην θέλουμε να κάνει tab.
                # Για την ώρα το αφήνουμε ως έχει.
                def go_next(event, idx=i, current_widget=widget): # pylint: disable=cell-var-from-loop
                    # Αν το Combobox είναι dropdown ανοιχτό και πατηθεί Enter, συνήθως επιλέγει και κλείνει.
                    # Δεν θέλουμε να κάνει ΚΑΙ tab αμέσως μετά, εκτός αν είναι η επιθυμητή συμπεριφορά.
                    # Η .winfo_exists() είναι για ασφάλεια αν το widget καταστραφεί.
                    if isinstance(current_widget, ttk.Combobox) and current_widget.winfo_exists() and current_widget.winfo_ismapped() and current_widget.get() != "" :
                         # Αυτό μπορεί να χρειαστεί πιο ειδικό χειρισμό για το πότε ακριβώς να κάνει tab ένα combobox
                         pass # Αφήνουμε το Enter να κάνει την επιλογή του στο combobox

                    if idx + 1 < len(entry_widgets):
                        if entry_widgets[idx + 1].winfo_exists(): # Έλεγχος αν το widget υπάρχει
                             entry_widgets[idx + 1].focus_set()
                    # Αν είναι το τελευταίο widget πριν το Text, και το Text είναι το επόμενο,
                    # τότε δεν κάνουμε focus στο Text με το Tab, αφήνουμε το Enter στο Text να κάνει submit.
                    # Αυτό καλύπτεται από το ότι το Text widget δεν είναι στον βρόγχο αυτό.
                    return "break" # Σταματά το default behavior του Enter (π.χ. νέα γραμμή σε Entry)
                widget.bind("<Return>", go_next)
                widget.bind("<KP_Enter>", go_next) # Και για το Enter του Numpad

        # Το τελευταίο widget στη λίστα entry_widgets αναμένεται να είναι το Text widget για σχόλια
        if entry_widgets and isinstance(entry_widgets[-1], tk.Text):
            comments_text_widget = entry_widgets[-1]
            def submit_on_enter_text(event):
                if event.keysym == "Return": # Μόνο το Enter, όχι Shift+Enter κλπ.
                    if add_btn.winfo_exists(): # Έλεγχος αν το κουμπί υπάρχει
                        add_btn.invoke()
                    return "break" # Αποτροπή εισαγωγής νέας γραμμής
            comments_text_widget.bind("<KeyPress-Return>", submit_on_enter_text) # KeyPress για να προλάβει τη νέα γραμμή

    def set_mode(self, mode):
        # ... (без изменений)
        if mode not in ["main", "prediction"]: return
        if self.edit_mode:
            for carrier_in_edit in CARRIERS:
                if self.item_being_edited.get(carrier_in_edit) is not None:
                    if self.current_mode == "main": self.exit_main_edit_mode(carrier_in_edit)
                    elif self.current_mode == "prediction": self.exit_prediction_edit_mode(carrier_in_edit)
        if self.current_mode == "main":
            for carrier in CARRIERS: self.main_frames[carrier].pack_forget()
        elif self.current_mode == "prediction":
            for carrier in CARRIERS: self.prediction_frames[carrier].pack_forget()
        self.current_mode = mode
        if self.current_mode == "main":
            self.mode_button.config(text="Πρόβλεψη Παλετών")
            self.export_btn.config(text="Εξαγωγή σε Excel (Κύρια Δεδομένα)")
            for carrier in CARRIERS:
                self.main_frames[carrier].pack(fill=tk.BOTH, expand=True)
                self.entries[carrier] = self.main_widgets[carrier]['entries']
                self.tables[carrier] = self.main_widgets[carrier]['table']
                self.summary_labels[carrier] = {**self.main_widgets[carrier]['summary_labels_pal'], **self.main_widgets[carrier]['summary_labels_box'], **self.main_widgets[carrier]['summary_labels_inv']}
                self.add_update_btns[carrier] = self.main_widgets[carrier]['add_update_btn']
                self.delete_btns[carrier] = self.main_widgets[carrier]['delete_btn']
        elif self.current_mode == "prediction":
            self.mode_button.config(text="Επιστροφή στην Κύρια")
            self.export_btn.config(text="Εξαγωγή σε Excel (Πρόβλεψη)")
            for carrier in CARRIERS:
                self.prediction_frames[carrier].pack(fill=tk.BOTH, expand=True)
                self.entries[carrier] = self.prediction_widgets[carrier]['entries'] # Αυτό δεν περιλαμβάνει τα σχόλια, αλλά δεν πειράζει για το context menu κλπ.
                self.tables[carrier] = self.prediction_widgets[carrier]['table']
                self.summary_labels[carrier] = self.prediction_widgets[carrier]['summary_labels']
                self.add_update_btns[carrier] = self.prediction_widgets[carrier]['add_update_btn']
                self.delete_btns[carrier] = self.prediction_widgets[carrier]['delete_btn']
        self.load_data_for_date(self.current_date)
        self.canvas.update_idletasks()
        required_width = sum(frame.winfo_reqwidth() for frame in self.carrier_frames.values())
        padding_width = (len(CARRIERS) - 1) * 2 + 40
        required_width += padding_width
        self.canvas.itemconfig(self.canvas_window_id, width=required_width, height=self.carriers_frame.winfo_reqheight())
        self.canvas.config(scrollregion=self.canvas.bbox("all"))
        for carrier_key in CARRIERS:
            if self.tables.get(carrier_key) and self.tables[carrier_key].winfo_exists():
                self.tables[carrier_key].event_generate("<<TreeviewSelect>>")

    def on_item_select(self, event):
        # ... (без изменений)
        widget = event.widget; carrier = None
        for c_key, main_w_dict in self.main_widgets.items():
            if 'table' in main_w_dict and widget == main_w_dict['table']: carrier = c_key; break
        if not carrier:
            for c_key, pred_w_dict in self.prediction_widgets.items():
                if 'table' in pred_w_dict and widget == pred_w_dict['table']: carrier = c_key; break
        if not carrier: return
        has_selection = bool(widget.selection())
        is_this_carrier_editing = self.item_being_edited.get(carrier) is not None

        if self.delete_btns.get(carrier):
            self.delete_btns[carrier].config(state=tk.NORMAL if has_selection and not is_this_carrier_editing else tk.DISABLED)
        
        if self.current_mode == "main":
            if self.main_edit_btns.get(carrier): self.main_edit_btns[carrier].config(state=tk.NORMAL if has_selection and not is_this_carrier_editing else tk.DISABLED)
            if self.main_widgets.get(carrier, {}).get('copy_btn'): self.main_widgets[carrier]['copy_btn'].config(state=tk.NORMAL if has_selection and not is_this_carrier_editing else tk.DISABLED)
        elif self.current_mode == "prediction":
            if self.prediction_edit_btns.get(carrier): self.prediction_edit_btns[carrier].config(state=tk.NORMAL if has_selection and not is_this_carrier_editing else tk.DISABLED)

    def enter_main_edit_mode(self, carrier):
        # ... (без изменений)
        if self.current_mode != "main": return
        if self.edit_mode and self.item_being_edited.get(carrier) is None : # Αν είμαστε σε edit mode ΑΛΛΟΥ
             messagebox.showinfo("Προσοχή", "Ολοκληρώστε την επεξεργασία στον άλλο μεταφορέα πρώτα.")
             return
        selected_item_id_tuple = self.tables[carrier].selection()
        if not selected_item_id_tuple: messagebox.showwarning("Προσοχή", "Επιλέξτε εγγραφή."); return
        item_db_id = selected_item_id_tuple[0]
        conn = self.get_db_connection(); entry_to_edit = None
        if conn:
            try: cursor = conn.cursor(); cursor.execute("SELECT code, name, invoice, left, boxes, comments FROM entries WHERE id = ?", (item_db_id,)); entry_to_edit = cursor.fetchone()
            finally: conn.close()
        if not entry_to_edit: messagebox.showerror("Σφάλμα", "Δεν βρέθηκε η εγγραφή (main)."); return
        code_val, name_val, invoice_val, left_val, boxes_val, comments_val = entry_to_edit
        try: code_e, name_cb_e, inv_e, left_cb_e, box_e, comm_txt_e = self.main_widgets[carrier]['entries'] # left_cb_e αντί left_v_e
        except KeyError: messagebox.showerror("Σφάλμα Widgets", "Πρόβλημα πεδίων (main-edit)."); return
        code_e.delete(0, tk.END); code_e.insert(0, code_val or "")
        self.name_vars[carrier].set(name_val or "")
        inv_e.delete(0, tk.END); inv_e.insert(0, invoice_val or "")
        left_cb_e.set(left_val or "ΟΧΙ") # Χρήση του Combobox widget για το set
        box_e.delete(0, tk.END); box_e.insert(0, boxes_val or "")
        comm_txt_e.delete("1.0", tk.END);
        if comments_val: comm_txt_e.insert("1.0", comments_val)
        self.root.after(10, lambda: code_e.focus_set())
        self.main_widgets[carrier]['add_update_btn'].config(text="Ενημέρωση")
        self.main_edit_btns[carrier].config(state=tk.DISABLED)
        self.main_cancel_btns[carrier].pack(side=tk.LEFT, padx=1)
        self.main_widgets[carrier]['delete_btn'].config(state=tk.DISABLED)
        self.main_widgets[carrier]['copy_btn'].config(state=tk.DISABLED)
        self.edit_mode = True; self.item_being_edited[carrier] = item_db_id

    def exit_main_edit_mode(self, carrier, clear_selection=True):
        # ... (без изменений)
        if not self.item_being_edited.get(carrier) and self.current_mode == "main" : # Έλεγχος αν όντως ήμασταν σε edit για αυτόν τον carrier σε αυτό το mode
             # Αν δεν ήμασταν, δεν κάνουμε κάτι για να μην κρύψουμε κουμπιά άσκοπα
             # Αυτό μπορεί να συμβεί αν αλλάζουμε mode και καλείται προληπτικά
             if not self.edit_mode: return # Αν γενικά δεν είμαστε σε edit mode, σίγουρα δεν κάνουμε κάτι

        try:
            code_e, name_cb_e, inv_e, left_cb_e, box_e, comm_txt_e = self.main_widgets[carrier]['entries']
            code_e.delete(0, tk.END); self.name_vars[carrier].set("")
            inv_e.delete(0, tk.END); box_e.delete(0, tk.END)
            left_cb_e.set("ΟΧΙ"); comm_txt_e.delete("1.0", tk.END) # Χρήση του Combobox widget
            
            add_update_btn = self.main_widgets[carrier].get('add_update_btn')
            edit_btn = self.main_edit_btns.get(carrier)
            cancel_btn = self.main_cancel_btns.get(carrier)
            delete_btn = self.main_widgets[carrier].get('delete_btn')
            copy_btn = self.main_widgets[carrier].get('copy_btn')
            table_widget = self.tables.get(carrier)
            
            if add_update_btn: add_update_btn.config(text="Προσθήκη")
            has_sel = table_widget.selection() if table_widget and table_widget.winfo_exists() else False
            if edit_btn: edit_btn.config(state=tk.NORMAL if has_sel else tk.DISABLED)
            if cancel_btn: cancel_btn.pack_forget()
            if delete_btn: delete_btn.config(state=tk.NORMAL if has_sel else tk.DISABLED)
            if copy_btn: copy_btn.config(state=tk.NORMAL if has_sel else tk.DISABLED)

        except (KeyError, AttributeError) : pass # Widgets might not exist if mode changed rapidly
        
        self.item_being_edited[carrier] = None
        if not any(self.item_being_edited.values()): self.edit_mode = False
        
        if clear_selection and self.tables.get(carrier) and self.tables[carrier].winfo_exists():
            self.tables[carrier].selection_remove(self.tables[carrier].selection())
            # Trigger on_item_select to re-evaluate button states after clearing selection
            self.on_item_select(type('event', (object,), {'widget': self.tables[carrier]})())


    def enter_prediction_edit_mode(self, carrier):
        # ... (без изменений)
        if self.current_mode != "prediction": return
        if self.edit_mode and self.item_being_edited.get(carrier) is None:
             messagebox.showinfo("Προσοχή", "Ολοκληρώστε την επεξεργασία στον άλλο μεταφορέα πρώτα.")
             return
        selected_item_id_tuple = self.tables[carrier].selection()
        if not selected_item_id_tuple: messagebox.showwarning("Προσοχή", "Επιλέξτε πρόβλεψη."); return
        item_db_id = selected_item_id_tuple[0]
        conn = self.get_db_connection(); prediction_to_edit = None
        if conn:
            try: cursor = conn.cursor(); cursor.execute("SELECT name, item_type, count, comments FROM predictions WHERE id = ?", (item_db_id,)); prediction_to_edit = cursor.fetchone()
            finally: conn.close()
        if not prediction_to_edit: messagebox.showerror("Σφάλμα", "Δεν βρέθηκε η πρόβλεψη."); return
        name_val, type_val, count_val, comments_val = prediction_to_edit
        try:
            name_cb_p, count_e_p, item_type_cb_p = self.prediction_widgets[carrier]['entries']
            comm_txt_p = self.prediction_widgets[carrier]['comments_text']
        except KeyError: messagebox.showerror("Σφάλμα Widgets", "Πρόβλημα πεδίων (pred-edit)."); return
        self.name_vars[carrier].set(name_val or "")
        self.prediction_count_vars[carrier].set(str(count_val) if count_val is not None else "")
        self.prediction_type_vars[carrier].set(type_val or "Παλέτα")
        comm_txt_p.delete("1.0", tk.END)
        if comments_val: comm_txt_p.insert("1.0", comments_val)
        self.root.after(10, lambda: name_cb_p.focus_set())
        self.prediction_widgets[carrier]['add_update_btn'].config(text="Ενημέρωση")
        self.prediction_edit_btns[carrier].config(state=tk.DISABLED)
        self.prediction_cancel_btns[carrier].pack(side=tk.LEFT, padx=1)
        self.prediction_widgets[carrier]['delete_btn'].config(state=tk.DISABLED)
        self.edit_mode = True; self.item_being_edited[carrier] = item_db_id

    def exit_prediction_edit_mode(self, carrier, clear_selection=True):
        # ... (без изменений)
        if not self.item_being_edited.get(carrier) and self.current_mode == "prediction":
            if not self.edit_mode: return

        try:
            name_cb_p, count_e_p, item_type_cb_p = self.prediction_widgets[carrier]['entries']
            comm_txt_p = self.prediction_widgets[carrier]['comments_text']
            self.name_vars[carrier].set(""); self.prediction_count_vars[carrier].set("")
            self.prediction_type_vars[carrier].set("Παλέτα"); comm_txt_p.delete("1.0", tk.END)

            add_update_btn = self.prediction_widgets[carrier].get('add_update_btn')
            edit_btn = self.prediction_edit_btns.get(carrier)
            cancel_btn = self.prediction_cancel_btns.get(carrier)
            delete_btn = self.prediction_widgets[carrier].get('delete_btn')
            table_widget = self.tables.get(carrier)

            if add_update_btn: add_update_btn.config(text="Προσθήκη")
            has_sel = table_widget.selection() if table_widget and table_widget.winfo_exists() else False
            if edit_btn: edit_btn.config(state=tk.NORMAL if has_sel else tk.DISABLED)
            if cancel_btn: cancel_btn.pack_forget()
            if delete_btn: delete_btn.config(state=tk.NORMAL if has_sel else tk.DISABLED)
        except (KeyError, AttributeError): pass
            
        self.item_being_edited[carrier] = None
        if not any(self.item_being_edited.values()): self.edit_mode = False
            
        if clear_selection and self.tables.get(carrier) and self.tables[carrier].winfo_exists():
            self.tables[carrier].selection_remove(self.tables[carrier].selection())
            self.on_item_select(type('event', (object,), {'widget': self.tables[carrier]})())

    def handle_main_add_update(self, carrier):
        # ... (без изменений)
        if self.current_mode != "main": return
        try: code_w, name_cb_w, inv_w, left_cb_w, box_w, comm_txt_w = self.main_widgets[carrier]['entries'] # left_cb_w
        except ValueError: messagebox.showerror("Σφάλμα Widgets", "Πρόβλημα πεδίων (main add/update)."); return
        code_val = code_w.get().strip()
        name_val = self.name_vars[carrier].get().strip()
        inv_val = inv_w.get().strip()
        left_val = left_cb_w.get().strip() # Παίρνουμε την τιμή από το Combobox
        box_val = box_w.get().strip()
        comm_val = comm_txt_w.get("1.0", "end-1c").strip()
        if not code_val: messagebox.showerror("Σφάλμα", "Κωδικός Παλέτας υποχρεωτικός."); return
        if box_val and not box_val.isdigit(): messagebox.showerror("Σφάλμα", "Κιβώτια: αριθμός."); return
        if carrier == "ΔΙΑΚΙΝΗΣΗ" and not name_val: name_val = "Αθήνα"
        conn = self.get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(); db_id_to_edit = self.item_being_edited.get(carrier)
                if self.edit_mode and db_id_to_edit is not None:
                    cursor.execute("UPDATE entries SET code=?, name=?, invoice=?, left=?, boxes=?, comments=? WHERE id=?", (code_val, name_val, inv_val, left_val, box_val, comm_val, db_id_to_edit))
                    conn.commit(); self.exit_main_edit_mode(carrier, clear_selection=False)
                else:
                    cursor.execute("INSERT INTO entries (entry_date, carrier, code, name, invoice, left, boxes, comments) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (self.current_date.strftime('%Y-%m-%d'), carrier, code_val, name_val, inv_val, left_val, box_val, comm_val))
                    conn.commit()
                    code_w.delete(0, tk.END); self.name_vars[carrier].set(""); inv_w.delete(0, tk.END)
                    box_w.delete(0, tk.END); left_cb_w.set("ΟΧΙ"); comm_txt_w.delete("1.0", tk.END) # left_cb_w
                    self.root.after(50, lambda: code_w.focus_set())
                self.update_name_combobox_values()
            except sqlite3.Error as e: messagebox.showerror("Σφάλμα Βάσης", f"Σφάλμα εγγραφής (main): {e}"); conn.rollback()
            finally: conn.close()
        self.load_main_data(self.current_date)

    def handle_prediction_add_update(self, carrier):
        # ... (без изменений)
        if self.current_mode != "prediction": return
        try:
            name_cb_p, count_e_p, item_type_cb_p = self.prediction_widgets[carrier]['entries']
            comm_txt_p_widget = self.prediction_widgets[carrier]['comments_text']
        except KeyError: messagebox.showerror("Σφάλμα Widgets", "Πρόβλημα πεδίων (prediction add/update)."); return
        comm_val_p = comm_txt_p_widget.get("1.0", "end-1c").strip() if comm_txt_p_widget else ""
        name_val_p = self.name_vars[carrier].get().strip()
        count_val_p = self.prediction_count_vars[carrier].get().strip()
        item_type_val_p = self.prediction_type_vars[carrier].get().strip()
        if not name_val_p or not count_val_p or not item_type_val_p: messagebox.showerror("Σφάλμα", "Όνομα, Ποσότητα, Είδος υποχρεωτικά (pred)."); return
        if not count_val_p.isdigit(): messagebox.showerror("Σφάλμα", "Ποσότητα (pred): αριθμός."); return
        conn = self.get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(); db_id_to_edit = self.item_being_edited.get(carrier)
                if self.edit_mode and db_id_to_edit is not None:
                    cursor.execute("UPDATE predictions SET name=?, item_type=?, count=?, comments=? WHERE id=?", (name_val_p, item_type_val_p, int(count_val_p), comm_val_p, db_id_to_edit))
                    conn.commit(); self.exit_prediction_edit_mode(carrier, clear_selection=False)
                else:
                    cursor.execute("INSERT INTO predictions (entry_date, carrier, name, item_type, count, comments) VALUES (?, ?, ?, ?, ?, ?)", (self.current_date.strftime('%Y-%m-%d'), carrier, name_val_p, item_type_val_p, int(count_val_p), comm_val_p))
                    conn.commit()
                    self.name_vars[carrier].set(""); self.prediction_count_vars[carrier].set("")
                    self.prediction_type_vars[carrier].set("Παλέτα")
                    if comm_txt_p_widget: comm_txt_p_widget.delete("1.0", tk.END)
                    self.root.after(50, lambda: name_cb_p.focus_set())
                self.update_name_combobox_values()
            except sqlite3.Error as e: messagebox.showerror("Σφάλμα Βάσης", f"Σφάλμα εγγραφής (prediction): {e}"); conn.rollback()
            finally: conn.close()
        self.load_prediction_data(self.current_date)

    def delete_main_selected(self, carrier):
        # ... (без изменений)
        if self.current_mode != "main": return
        selected_ids = self.tables[carrier].selection()
        if not selected_ids: messagebox.showwarning("Προσοχή", "Επιλέξτε εγγραφή(ές) (main)."); return
        if not messagebox.askyesno("Επιβεβαίωση", f"Διαγραφή {len(selected_ids)} εγγραφών;"): return
        conn = self.get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(); deleted_count = 0
                for item_db_id in selected_ids: cursor.execute("DELETE FROM entries WHERE id = ?", (item_db_id,)); deleted_count += cursor.rowcount
                conn.commit()
                if deleted_count > 0: messagebox.showinfo("Επιτυχία", f"Διαγράφηκαν {deleted_count} εγγραφές.")
            except sqlite3.Error as e: messagebox.showerror("Σφάλμα Βάσης", f"Σφάλμα διαγραφής (main): {e}"); conn.rollback()
            finally: conn.close()
        self.load_main_data(self.current_date)
        self.item_being_edited[carrier] = None 
        if not any(self.item_being_edited.values()): self.edit_mode = False


    def delete_prediction_selected(self, carrier):
        # ... (без изменений)
        if self.current_mode != "prediction": return
        selected_ids = self.tables[carrier].selection()
        if not selected_ids: messagebox.showwarning("Προσοχή", "Επιλέξτε πρόβλεψη(εις)."); return
        if not messagebox.askyesno("Επιβεβαίωση", f"Διαγραφή {len(selected_ids)} προβλέψεων;"): return
        conn = self.get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(); deleted_count = 0
                for item_db_id in selected_ids: cursor.execute("DELETE FROM predictions WHERE id = ?", (item_db_id,)); deleted_count += cursor.rowcount
                conn.commit()
                if deleted_count > 0: messagebox.showinfo("Επιτυχία", f"Διαγράφηκαν {deleted_count} προβλέψεις.")
            except sqlite3.Error as e: messagebox.showerror("Σφάλμα Βάσης", f"Σφάλμα διαγραφής (prediction): {e}"); conn.rollback()
            finally: conn.close()
        self.load_prediction_data(self.current_date)
        self.item_being_edited[carrier] = None
        if not any(self.item_being_edited.values()): self.edit_mode = False


    def toggle_left_status(self, event):
        # ... (без изменений)
        if self.current_mode != "main": return
        widget = event.widget; carrier = None
        for c, main_w in self.main_widgets.items():
            if 'table' in main_w and widget == main_w['table']: carrier = c; break
        if not carrier: return
        item_iid = widget.identify_row(event.y)
        if not item_iid: return
        item_db_id = item_iid
        current_values_in_tree = list(widget.item(item_iid, "values"))
        if len(current_values_in_tree) < 4: return
        current_left_in_tree = current_values_in_tree[3]
        new_left_status = "ΝΑΙ" if current_left_in_tree == "ΟΧΙ" else "ΟΧΙ"
        conn = self.get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("UPDATE entries SET left = ? WHERE id = ?", (new_left_status, item_db_id))
                if cursor.rowcount == 0: messagebox.showwarning("Προσοχή", "Δεν ενημερώθηκε εγγραφή (toggle).")
                conn.commit()
            except sqlite3.Error as e: messagebox.showerror("Σφάλμα Βάσης", f"Σφάλμα ενημέρωσης 'Έφυγε': {e}"); conn.rollback()
            finally: conn.close()
        self.load_main_data(self.current_date)

    def load_data_for_date(self, date):
        # ... (без изменений)
        self.current_date = date; self.date_label.config(text=str(self.current_date))
        if self.edit_mode:
            for c_edit in CARRIERS:
                if self.item_being_edited.get(c_edit):
                    if self.current_mode == "main": self.exit_main_edit_mode(c_edit, clear_selection=False)
                    elif self.current_mode == "prediction": self.exit_prediction_edit_mode(c_edit, clear_selection=False)
                    break 
        self.load_main_data(date); self.load_prediction_data(date)
        self.update_navigation_buttons_state()
        for c_key in CARRIERS:
            if self.tables.get(c_key) and self.tables[c_key].winfo_exists():
                self.tables[c_key].selection_remove(self.tables[c_key].selection())
                self.on_item_select(type('event', (object,), {'widget': self.tables[c_key]})())


    def update_name_combobox_values(self):
        # ... (без изменений)
        conn = self.get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                for carrier in CARRIERS:
                    names = set()
                    cursor.execute("SELECT DISTINCT name FROM entries WHERE carrier = ? AND name IS NOT NULL AND name != ''", (carrier,))
                    for row in cursor.fetchall(): names.add(row[0])
                    cursor.execute("SELECT DISTINCT name FROM predictions WHERE carrier = ? AND name IS NOT NULL AND name != ''", (carrier,))
                    for row in cursor.fetchall(): names.add(row[0])
                    sorted_names = sorted(list(names))
                    self.name_combobox_values[carrier] = sorted_names
                    if carrier in self.main_widgets and 'entries' in self.main_widgets[carrier] and len(self.main_widgets[carrier]['entries']) > 1 and isinstance(self.main_widgets[carrier]['entries'][1], ttk.Combobox) and self.main_widgets[carrier]['entries'][1].winfo_exists():
                        self.main_widgets[carrier]['entries'][1].config(values=sorted_names)
                    if carrier in self.prediction_widgets and 'entries' in self.prediction_widgets[carrier] and len(self.prediction_widgets[carrier]['entries']) > 0 and isinstance(self.prediction_widgets[carrier]['entries'][0], ttk.Combobox) and self.prediction_widgets[carrier]['entries'][0].winfo_exists():
                        self.prediction_widgets[carrier]['entries'][0].config(values=sorted_names)
            except sqlite3.Error as e: messagebox.showerror("Σφάλμα Βάσης", f"Σφάλμα φόρτωσης ονομάτων: {e}")
            finally: conn.close()


    def update_main_view(self):
        self.name_tag_map.clear(); self.color_index_counter = 0
        for c in CARRIERS: # Ρύθμιση tag για κόκκινα γράμματα
            if c in self.main_widgets and 'table' in self.main_widgets[c] and self.main_widgets[c]['table'].winfo_exists():
                self.main_widgets[c]['table'].tag_configure("left_yes_red", foreground="red", font=("TkDefaultFont", 9, "bold"))
        
        for carrier in CARRIERS:
            if not (carrier in self.main_widgets and 'table' in self.main_widgets[carrier] and self.main_widgets[carrier]['table'].winfo_exists()): continue
            table = self.main_widgets[carrier]['table']
            s_pal = self.main_widgets[carrier]['summary_labels_pal']
            s_box = self.main_widgets[carrier]['summary_labels_box']
            s_inv = self.main_widgets[carrier]['summary_labels_inv']
            table.delete(*table.get_children())
            pt, pd, pnd = 0,0,0 # Paletes: total, departed, not_departed
            bt, bd, bnd = 0,0,0 # Boxes: total, departed, not_departed
            inv_s = 0           # Invoice sum
            
            for row_data in self.data.get(carrier, []): # data tuple: (id, carrier_db, code, name, invoice, left, boxes, comments)
                if len(row_data) < 8: continue 
                db_id, _, code, name, inv, left_stat, boxes_str, comm = row_data # Unpack
                
                boxes_num = int(boxes_str) if str(boxes_str).strip().isdigit() else 0
                inv_num = int(inv) if str(inv).strip().isdigit() else 0 # Αξία τιμολογίου για αυτή τη γραμμή
                left_s = str(left_stat).upper().strip()

                # --- ΔΙΟΡΘΩΣΗ ΕΔΩ ---
                if boxes_num > 0: # Αν είναι κιβώτια
                    bt += boxes_num
                    inv_s += inv_num # Προσθέτουμε την αξία του τιμολογίου
                    if left_s == "ΝΑΙ":
                        bd += boxes_num
                    else:
                        bnd += boxes_num
                else: # Αν είναι παλέτα (boxes_num == 0)
                    pt += 1
                    inv_s += inv_num # Προσθέτουμε την αξία του τιμολογίου (αν υπάρχει για την παλέτα)
                    if left_s == "ΝΑΙ":
                        pd += 1
                    else:
                        pnd += 1
                # --- ΤΕΛΟΣ ΔΙΟΡΘΩΣΗΣ ---
                
                tags = []
                if name and str(name).strip():
                    name_key = str(name).strip()
                    if name_key not in self.name_tag_map:
                        tag_name = f"name_color_{self.color_index_counter}"
                        color = self.color_list[self.color_index_counter % len(self.color_list)]
                        self.color_index_counter +=1 # Αύξηση του counter εδώ για να μην επαναλαμβάνεται ο ίδιος δείκτης
                        for c_inner in CARRIERS:
                            if c_inner in self.main_widgets and 'table' in self.main_widgets[c_inner] and self.main_widgets[c_inner]['table'].winfo_exists(): 
                                self.main_widgets[c_inner]['table'].tag_configure(tag_name, background=color)
                            if c_inner in self.prediction_widgets and 'table' in self.prediction_widgets[c_inner] and self.prediction_widgets[c_inner]['table'].winfo_exists(): 
                                self.prediction_widgets[c_inner]['table'].tag_configure(tag_name, background=color)
                        self.name_tag_map[name_key] = tag_name
                    tags.append(self.name_tag_map[name_key])
                
                if left_s == "ΝΑΙ": 
                    tags.append("left_yes_red")
                
                code_d = f"✓ {code}" if left_s == "ΝΑΙ" else str(code)
                # Εμφάνιση '0' για κιβώτια αν είναι κενό, αλλιώς η τιμή
                boxes_display = str(boxes_str).strip() if str(boxes_str).strip() else ('0' if boxes_num > 0 or str(boxes_str).strip() == '0' else '')

                tree_v = (code_d, name or "", inv or "", left_stat or "ΟΧΙ", boxes_display, comm or "")
                table.insert("", "end", iid=db_id, values=tree_v, tags=tuple(tags) if tags else ())

            s_pal['total_pal'].config(text=f"Παλέτες (Σύνολο): {pt}")
            s_pal['departed_pal'].config(text=f"Παλέτες (Αναχώρησαν): {pd}")
            s_pal['not_departed_pal'].config(text=f"Παλέτες (Χωρίς αναχ.): {pnd}")
            s_box['total_box'].config(text=f"Κιβώτια (Σύνολο): {bt}")
            s_box['departed_box'].config(text=f"Κιβώτια (Αναχώρησαν): {bd}")
            s_box['not_departed_box'].config(text=f"Κιβώτια (Χωρίς αναχ.): {bnd}")
            s_inv['sum_inv'].config(text=f"Σύνολο Τιμολογίων: {inv_s}")

    def update_prediction_view(self):
        # ... (без изменений)
        for carrier in CARRIERS:
            if not (carrier in self.prediction_widgets and 'table' in self.prediction_widgets[carrier] and self.prediction_widgets[carrier]['table'].winfo_exists()): continue
            table = self.prediction_widgets[carrier]['table']
            s_labels = self.prediction_widgets[carrier]['summary_labels']
            table.delete(*table.get_children()); pt, bt = 0,0
            for row_data in self.prediction_data.get(carrier, []):
                if len(row_data) < 6: continue
                db_id, _, name, item_type, count_s, comm_v = row_data
                count_n = int(count_s) if str(count_s).strip().isdigit() else 0
                if item_type == "Παλέτα": pt += count_n
                elif item_type == "Κιβώτιο": bt += count_n
                tag_n = ""
                if name and str(name).strip():
                    name_k = str(name).strip()
                    if name_k not in self.name_tag_map:
                        tag_n_new = f"name_color_{self.color_index_counter}"; clr = self.color_list[self.color_index_counter % len(self.color_list)]; self.color_index_counter += 1
                        for c_in in CARRIERS:
                            if c_in in self.main_widgets and 'table' in self.main_widgets[c_in] and self.main_widgets[c_in]['table'].winfo_exists(): self.main_widgets[c_in]['table'].tag_configure(tag_n_new, background=clr)
                            if c_in in self.prediction_widgets and 'table' in self.prediction_widgets[c_in] and self.prediction_widgets[c_in]['table'].winfo_exists(): self.prediction_widgets[c_in]['table'].tag_configure(tag_n_new, background=clr)
                        self.name_tag_map[name_k] = tag_n_new
                    tag_n = self.name_tag_map[name_k]
                tree_v = (name, item_type, count_n, comm_v)
                table.insert("", "end", iid=db_id, values=tree_v, tags=(tag_n,) if tag_n else ())
            s_labels['total_pal'].config(text=f"Σ. Παλ: {pt}"); s_labels['total_box'].config(text=f"Σ. Κιβ: {bt}")


    def sort_data(self, carrier, col_idx_in_data_tuple, direction, col_type='text'):
        # ... (без изменений)
        reverse = (direction == 'desc')
        data_list_to_sort = self.data[carrier] if self.current_mode == "main" else self.prediction_data[carrier]
        if not data_list_to_sort or col_idx_in_data_tuple >= len(data_list_to_sort[0]): return
        if col_type == 'text': data_list_to_sort.sort(key=lambda x: str(x[col_idx_in_data_tuple] or '').lower(), reverse=reverse)
        elif col_type == 'number':
            def numeric_key(item_tuple):
                val_str = str(item_tuple[col_idx_in_data_tuple]).strip()
                try: return int(val_str) if val_str.isdigit() else (float('-inf') if direction == 'asc' else float('inf'))
                except: return (float('-inf') if direction == 'asc' else float('inf'))
            data_list_to_sort.sort(key=numeric_key, reverse=reverse)


    def sort_column_handler(self, carrier, treeview_col_name):
        # ... (без изменений)
        data_tuple_actual_col_idx = None
        if self.current_mode == "main": display_to_data_map_main = {"code": 2, "name": 3, "invoice": 4, "left": 5, "boxes": 6, "comments": 7}; data_tuple_actual_col_idx = display_to_data_map_main.get(treeview_col_name)
        elif self.current_mode == "prediction": display_to_data_map_pred = {"name": 2, "item_type": 3, "count": 4, "comments": 5}; data_tuple_actual_col_idx = display_to_data_map_pred.get(treeview_col_name)
        if data_tuple_actual_col_idx is None: return
        current_sort_tv_col = self.sort_column.get(carrier); current_direction = self.sort_direction.get(carrier, 'asc')
        new_direction = 'desc' if current_sort_tv_col == treeview_col_name and current_direction == 'asc' else 'asc'
        self.sort_column[carrier] = treeview_col_name; self.sort_direction[carrier] = new_direction
        col_type_for_sort = 'text'
        if (self.current_mode == "main" and treeview_col_name in ['invoice', 'boxes']) or (self.current_mode == "prediction" and treeview_col_name == 'count'): col_type_for_sort = 'number'
        self.sort_data(carrier, data_tuple_actual_col_idx, new_direction, col_type_for_sort)
        if self.current_mode == "main": self.update_main_view()
        else: self.update_prediction_view()


    def update_navigation_buttons_state(self):
        # ... (без изменений)
        today = datetime.today().date(); oldest_date = today - timedelta(days=MAX_DAYS_HISTORY)
        self.prev_btn.config(state=tk.NORMAL if self.current_date > oldest_date else tk.DISABLED)
        self.next_btn.config(state=tk.NORMAL if (self.current_date - today).days < MAX_FUTURE_DAYS else tk.DISABLED)

    def prev_day(self):
        # ... (без изменений)
        today = datetime.today().date(); oldest_allowed = today - timedelta(days=MAX_DAYS_HISTORY)
        new_date = self.current_date - timedelta(days=1)
        if new_date >= oldest_allowed: self.load_data_for_date(new_date)
        else: messagebox.showinfo("Πληροφορία", f"Όριο {MAX_DAYS_HISTORY} ημερών."); self.prev_btn.config(state=tk.DISABLED)

    def next_day(self):
        # ... (без изменений)
        today = datetime.today().date(); new_date = self.current_date + timedelta(days=1)
        if (new_date - today).days <= MAX_FUTURE_DAYS: self.load_data_for_date(new_date)
        else: messagebox.showinfo("Πληροφορία", f"Όριο {MAX_FUTURE_DAYS} ημερών."); self.next_btn.config(state=tk.DISABLED)

    def refresh_data(self): self.load_data_for_date(self.current_date)
    def auto_refresh(self): self.refresh_data(); self.root.after(60000, self.auto_refresh)

    def clean_old_data_from_db(self):
        # ... (без изменений)
        limit_date_str = (datetime.today().date() - timedelta(days=MAX_DAYS_HISTORY)).strftime('%Y-%m-%d')
        conn = self.get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM entries WHERE entry_date < ?", (limit_date_str,)); e_del = cursor.rowcount
                cursor.execute("DELETE FROM predictions WHERE entry_date < ?", (limit_date_str,)); p_del = cursor.rowcount
                conn.commit(); print(f"DEBUG: Cleaned: {e_del} entries, {p_del} predictions < {limit_date_str}.")
            except sqlite3.Error as e: messagebox.showerror("Σφάλμα Βάσης", f"Σφάλμα καθαρισμού: {e}"); conn.rollback()
            finally: conn.close()

    def export_current_mode_to_excel(self):
        # ... (без изменений)
        conn = self.get_db_connection()
        if not conn: messagebox.showerror("Σφάλμα Βάσης", "Αδύνατη σύνδεση για εξαγωγή."); return
        try:
            date_str = self.current_date.strftime('%Y-%m-%d'); df = pd.DataFrame(); filename_suffix = f"{date_str}_{datetime.now().strftime('%H%M%S')}.xlsx"
            if self.current_mode == "main":
                df = pd.read_sql_query("SELECT carrier, code, name, invoice, left, boxes, comments FROM entries WHERE entry_date = ? ORDER BY carrier, name, code", conn, params=(date_str,))
                df.rename(columns={'carrier':'Μεταφορέας','code':'Κωδ.Παλέτας','name':'Όνομα','invoice':'Τιμολόγια','left':'Έφυγε','boxes':'Κιβώτια','comments':'Σχόλια'}, inplace=True)
                export_filename = f"Δεδομένα_Παλετών_Κύρια_{filename_suffix}"
            elif self.current_mode == "prediction":
                df = pd.read_sql_query("SELECT carrier, name, item_type, count, comments FROM predictions WHERE entry_date = ? ORDER BY carrier, name, item_type", conn, params=(date_str,))
                df.rename(columns={'carrier':'Μεταφορέας','name':'Όνομα','item_type':'Είδος','count':'Ποσότητα','comments':'Σχόλια'}, inplace=True)
                export_filename = f"Δεδομένα_Παλετών_Πρόβλεψη_{filename_suffix}"
            else: messagebox.showwarning("Προσοχή", "Εξαγωγή μη διαθέσιμη."); return
            if df.empty: messagebox.showwarning("Προσοχή", f"Δεν υπάρχουν δεδομένα ({date_str})."); return
            try:
                desktop_path = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop') if 'USERPROFILE' in os.environ else None
                save_path = os.path.join(desktop_path, export_filename) if desktop_path and os.path.isdir(desktop_path) else os.path.join(tempfile.gettempdir(), export_filename)
                df.to_excel(save_path, index=False)
                messagebox.showinfo("Επιτυχής Εξαγωγή", f"Αποθηκεύτηκε:\n{save_path}\n\nΆνοιγμα...")
                webbrowser.open(f"file://{os.path.realpath(save_path)}")
            except Exception as e_io: messagebox.showerror("Σφάλμα Εξαγωγής IO", f"Σφάλμα IO: {e_io}")
        except sqlite3.Error as e_sql: messagebox.showerror("Σφάλμα Βάσης/Εξαγωγής", f"Σφάλμα SQL: {e_sql}")
        except Exception as e_gen: messagebox.showerror("Σφάλμα Εξαγωγής", f"Γενικό σφάλμα: {e_gen}")
        finally:
            if conn: conn.close()

    def load_main_data(self, date):
        # ... (без изменений)
        self.data = {c: [] for c in CARRIERS}; conn = self.get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT id, carrier, code, name, invoice, left, boxes, comments FROM entries WHERE entry_date = ? ORDER BY carrier, name, code", (date.strftime('%Y-%m-%d'),))
                for row in cursor.fetchall():
                    if row[1] in self.data: self.data[row[1]].append(row)
            except sqlite3.Error as e: messagebox.showerror("Σφάλμα Βάσης", f"Φόρτωση κύριων: {e}")
            finally: conn.close()
        self.update_main_view()

    def load_prediction_data(self, date):
        # ... (без изменений)
        self.prediction_data = {c: [] for c in CARRIERS}; conn = self.get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT id, carrier, name, item_type, count, comments FROM predictions WHERE entry_date = ? ORDER BY carrier, name, item_type", (date.strftime('%Y-%m-%d'),))
                for row in cursor.fetchall():
                    if row[1] in self.prediction_data: self.prediction_data[row[1]].append(row)
            except sqlite3.Error as e: messagebox.showerror("Σφάλμα Βάσης", f"Φόρτωση πρόβλεψης: {e}")
            finally: conn.close()
        self.update_prediction_view()

if __name__ == "__main__":
    root = tk.Tk()
    app = PaletesApp(root)
    root.mainloop()