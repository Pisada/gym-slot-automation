import asyncio
import datetime
import json
import threading
import queue
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox

import booking_backend as bb

CONFIG_PATH = Path("booking_config.json")
log_queue = queue.Queue()
countdown_job = None
countdown_stop = False


# ---------------- Config helpers ----------------
def load_config():
    if CONFIG_PATH.exists():
        try:
            with CONFIG_PATH.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(data: dict):
    try:
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


# ---------------- Booking trigger ----------------
def start_booking():
    username = entry_user.get().strip()
    password = entry_pass.get().strip()
    day = int(entry_day.get().strip())
    month = int(entry_month.get().strip())
    wait_midnight = bool(wait_var.get())
    slot_idx = slot_idx_var.get()
    slot_selector = {
        "0": bb.SEL_SLOT_0,
        "1": bb.SEL_SLOT_1,
        "2": bb.SEL_SLOT_2,
        "3": bb.SEL_SLOT_3,
    }.get(slot_idx, bb.SEL_SLOT_0)
    try_others = bool(try_other_var.get())
    try:
        day_attempts = int(entry_day_attempts.get().strip())
    except Exception:
        day_attempts = 5

    target_date = datetime.date(datetime.date.today().year, month, day)

    if remember_var.get():
        save_config(
            {
                "username": username,
                "password": password,
                "day": day,
                "month": month,
                "wait_midnight": wait_midnight,
                "slot_idx": slot_idx,
                "day_attempts": day_attempts,
            }
        )

    if wait_midnight:
        start_countdown()
    else:
        stop_countdown()

    status_var.set("Running...")
    status_box.configure(state="normal")
    status_box.delete("1.0", "end")
    status_box.insert("end", "Starting...\n")
    status_box.configure(state="disabled")
    status_box.see("end")

    def log_cb(msg: str):
        log_queue.put(msg)

    def worker():
        try:
            asyncio.run(
                bb.run_booking(
                    username,
                    password,
                    target_date,
                    slot_selector,
                    wait_midnight,
                    log_cb=log_cb,
                    try_other_slots=try_others,
                    day_attempts=day_attempts,
                )
            )
            log_queue.put("STATUS:DONE")
        except Exception as e:
            log_queue.put(f"STATUS:ERROR:{e}")

    threading.Thread(target=worker, daemon=True).start()


# ---------------- Countdown ----------------
def start_countdown():
    global countdown_job, countdown_stop
    countdown_stop = False

    def update():
        global countdown_job
        if countdown_stop:
            countdown_var.set("Countdown: --:--:--")
            return
        now = datetime.datetime.now()
        tomorrow = now + datetime.timedelta(days=1)
        midnight = datetime.datetime.combine(tomorrow.date(), datetime.time(0, 0))
        remaining = midnight - now
        if remaining.total_seconds() < 0:
            countdown_var.set("Countdown: 00:00:00")
        else:
            h, rem = divmod(int(remaining.total_seconds()), 3600)
            m, s = divmod(rem, 60)
            countdown_var.set(f"Countdown: {h:02d}:{m:02d}:{s:02d}")
        countdown_job = root.after(500, update)

    update()


def stop_countdown():
    global countdown_job, countdown_stop
    countdown_stop = True
    if countdown_job:
        try:
            root.after_cancel(countdown_job)
        except Exception:
            pass
    countdown_job = None
    countdown_var.set("Countdown: --:--:--")


# ---------------- Log polling ----------------
def poll_logs():
    try:
        while True:
            msg = log_queue.get_nowait()
            if msg.startswith("STATUS:DONE"):
                status_var.set("Done")
                status_box.configure(state="normal")
                status_box.insert("end", "Done\n")
                status_box.see("end")
                status_box.configure(state="disabled")
                messagebox.showinfo("Done", "Booking flow finished; check status log and booking_result.png")
                stop_countdown()
            elif msg.startswith("STATUS:ERROR:"):
                status_var.set("Error")
                err = msg.split("STATUS:ERROR:", 1)[1]
                status_box.configure(state="normal")
                status_box.insert("end", f"Error: {err}\n")
                status_box.see("end")
                status_box.configure(state="disabled")
                messagebox.showerror("Error", err)
                stop_countdown()
            else:
                status_box.configure(state="normal")
                status_box.insert("end", msg + "\n")
                status_box.see("end")
                status_box.configure(state="disabled")
    except queue.Empty:
        pass
    root.after(200, poll_logs)


# ---------------- GUI ----------------
root = tk.Tk()
root.title("Gym Booking Bot")
root.configure(bg="#0b1324")
root.minsize(760, 820)

# Styling refreshed (clean single-column, centered title)
style = ttk.Style()
style.theme_use("clam")
style.configure("Main.TFrame", background="#0b1324")
style.configure("Card.TFrame", background="#101a30", relief="flat")
style.configure("Card.TLabel", background="#101a30", foreground="#e6e8ef", font=("Segoe UI", 11))
style.configure("Header.TLabel", background="#0b1324", foreground="#f7f9ff", font=("Segoe UI Semibold", 20))
style.configure("TButton", font=("Segoe UI Semibold", 11), padding=10, background="#1f2d44", foreground="#e6e8ef")
style.configure("Primary.TButton", font=("Segoe UI Semibold", 12), padding=12, background="#2b6cf6", foreground="#ffffff")
style.map("Primary.TButton", background=[("active", "#1f5bd6")])
style.configure("TCheckbutton", background="#101a30", foreground="#e6e8ef", font=("Segoe UI", 10))
style.configure("TRadiobutton", background="#101a30", foreground="#e6e8ef", font=("Segoe UI", 10))

root.rowconfigure(1, weight=1)
root.columnconfigure(0, weight=1)

# Header (centered title)
header_frame = ttk.Frame(root, style="Main.TFrame", padding=(20, 18))
header_frame.grid(row=0, column=0, sticky="ew")
ttk.Label(header_frame, text="Gym Booking Bot", style="Header.TLabel").pack(anchor="center")

# Main content single column
main = ttk.Frame(root, style="Main.TFrame", padding=(18, 12))
main.grid(row=1, column=0, sticky="nsew")
main.columnconfigure(0, weight=1)

# Form card
card = ttk.Frame(main, style="Card.TFrame", padding=24)
card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
card.columnconfigure(1, weight=1)
row = 0

ttk.Label(card, text="Username", style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=6)
entry_user = ttk.Entry(card, font=("Segoe UI", 11), background="#cce5ff", foreground="#000000")
entry_user.grid(row=row, column=1, sticky="ew", pady=6)
row += 1

ttk.Label(card, text="Password", style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=6)
entry_pass = ttk.Entry(card, show="*", font=("Segoe UI", 11), background="#cce5ff", foreground="#000000")
entry_pass.grid(row=row, column=1, sticky="ew", pady=6)
row += 1

ttk.Label(card, text="Day (e.g., 25)", style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=6)
entry_day = ttk.Entry(card, width=12, font=("Segoe UI", 11), background="#cce5ff", foreground="#000000")
entry_day.grid(row=row, column=1, sticky="w", pady=6)
row += 1

ttk.Label(card, text="Month (1-12)", style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=6)
entry_month = ttk.Entry(card, width=12, font=("Segoe UI", 11), background="#cce5ff", foreground="#000000")
entry_month.grid(row=row, column=1, sticky="w", pady=6)
row += 1

# Toggle buttons
toggle_inactive = {"bg": "#1f2d44", "fg": "#e6e8ef", "activebackground": "#24304a", "activeforeground": "#e6e8ef", "relief": tk.RIDGE, "bd": 1, "width": 22}
toggle_active = {"bg": "#2b6cf6", "fg": "#ffffff", "activebackground": "#1f5bd6", "activeforeground": "#ffffff", "relief": tk.RIDGE, "bd": 1, "width": 22}

wait_var = tk.IntVar(value=0)
remember_var = tk.IntVar(value=0)
try_other_var = tk.IntVar(value=0)

def make_toggle(text, var, row_idx, col_idx, col_span=1):
    btn = tk.Button(card, text=text, **toggle_inactive, font=("Segoe UI Semibold", 10))
    def on_click():
        var.set(0 if var.get() else 1)
        style_dict = toggle_active if var.get() else toggle_inactive
        btn.configure(**style_dict)
    btn.configure(command=on_click)
    btn.grid(row=row_idx, column=col_idx, columnspan=col_span, sticky="ew", pady=6, padx=2)
    return btn, on_click

# Wait toggle above slots
wait_btn, _ = make_toggle("Wait until midnight (start ~30s before)", wait_var, row, 0, 2)
row += 1

# Slots and toggles in one horizontal row
slot_row = ttk.Frame(card, style="Card.TFrame")
slot_row.grid(row=row, column=0, columnspan=2, sticky="ew", pady=4)
slot_row.columnconfigure(0, weight=1)
slot_row.columnconfigure(1, weight=1)

ttk.Label(slot_row, text="Time slot", style="Card.TLabel").grid(row=0, column=0, sticky="w", pady=4)
slot_idx_var = tk.StringVar(value="0")
slot_frame = ttk.Frame(slot_row, style="Card.TFrame")
slot_frame.grid(row=1, column=0, sticky="w")
for i, txt in enumerate(["14:00 - 15:30", "15:30 - 17:00", "17:00 - 18:30", "18:30 - 20:00"]):
    ttk.Radiobutton(slot_frame, text=txt, variable=slot_idx_var, value=str(i), style="TRadiobutton").pack(anchor="w", pady=1)

toggle_bar = ttk.Frame(slot_row, style="Card.TFrame")
toggle_bar.grid(row=1, column=1, sticky="e")
toggle_bar.columnconfigure((0,1), weight=1)
remember_btn, _ = make_toggle("Remember locally", remember_var, 0, 0)
try_other_btn, _ = make_toggle("Try other slots", try_other_var, 0, 1)
row += 1

# Toggles below slots, side by side
row += 0  # already placed

ttk.Label(card, text="Day click attempts", style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=6)
entry_day_attempts = ttk.Entry(card, width=10, font=("Segoe UI", 11), background="#cce5ff", foreground="#000000")
entry_day_attempts.insert(0, "5")
entry_day_attempts.grid(row=row, column=1, sticky="w", pady=6)
row += 1

# Countdown just below toggles/inputs
countdown_var = tk.StringVar(value="Countdown: --:--:--")
ttk.Label(card, textvariable=countdown_var, style="Card.TLabel", font=("Segoe UI Semibold", 12)).grid(
    row=row, column=0, columnspan=2, sticky="w", pady=(4, 6)
)
row += 1

# Status card
status_var = tk.StringVar(value="Idle")
status_card = ttk.Frame(main, style="Card.TFrame", padding=20)
status_card.grid(row=1, column=0, sticky="nsew", pady=(0, 12))
status_card.columnconfigure(0, weight=1)
ttk.Label(status_card, text="Status", style="Card.TLabel").grid(row=0, column=0, sticky="w")
status_box = tk.Text(status_card, height=6, bg="#0d172c", fg="#e6e8ef", relief="flat", wrap="word")
status_box.grid(row=1, column=0, sticky="ew", pady=(8, 6))
status_box.insert("end", "Idle\n")
status_box.configure(state="disabled")
status_box.see("end")

# Action button bottom
btn_frame = ttk.Frame(main, style="Main.TFrame")
btn_frame.grid(row=2, column=0, sticky="ew")
btn_frame.columnconfigure(0, weight=1)
ttk.Button(btn_frame, text="Start Booking", command=start_booking, style="Primary.TButton").grid(row=0, column=0, sticky="ew", pady=8)


def preload():
    cfg = load_config()
    if not cfg:
        return
    entry_user.insert(0, cfg.get("username", ""))
    entry_pass.insert(0, cfg.get("password", ""))
    entry_day.insert(0, cfg.get("day", ""))
    entry_month.insert(0, cfg.get("month", ""))
    slot_idx_var.set(cfg.get("slot_idx", "0"))
    wait_var.set(1 if cfg.get("wait_midnight") else 0)
    remember_var.set(1 if cfg.get("remember_details") else 0)
    try_other_var.set(1 if cfg.get("try_other_slots") else 0)
    if "day_attempts" in cfg:
        entry_day_attempts.delete(0, "end")
        entry_day_attempts.insert(0, str(cfg.get("day_attempts", 5)))

    # refresh toggle button visuals
    for var, btn in [(wait_var, wait_btn), (remember_var, remember_btn), (try_other_var, try_other_btn)]:
        style_dict = {"bg": "#2b6cf6", "fg": "#ffffff", "activebackground": "#1f5bd6", "activeforeground": "#ffffff", "relief": tk.RIDGE, "bd": 1} if var.get() else {"bg": "#1f2d44", "fg": "#e6e8ef", "activebackground": "#24304a", "activeforeground": "#e6e8ef", "relief": tk.RIDGE, "bd": 1}
        btn.configure(**style_dict)


preload()
poll_logs()
root.mainloop()
