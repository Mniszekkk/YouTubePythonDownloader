import threading
import queue
import yt_dlp
import customtkinter as ctk
from tkinter import filedialog
from PIL import Image
import requests
from io import BytesIO

# ================= LOGGER =================
class GuiLogger:
    def __init__(self, q): self.q = q
    def debug(self, m): self.q.put(m)
    def info(self, m): self.q.put(m)
    def warning(self, m): self.q.put(f"[WARN] {m}")
    def error(self, m): self.q.put(f"[ERROR] {m}")

# ================= DOWNLOAD =================
def download_media(url, folder, mode, quality, q, filename=""):
    logger = GuiLogger(q)

    # nazwa pliku
    if filename.strip():
        outtmpl = f"{folder}/{filename}.%(ext)s"
    else:
        outtmpl = f"{folder}/%(title)s.%(ext)s"

    ydl_opts_base = {
        "logger": logger,
        "noplaylist": True,
        "outtmpl": outtmpl
    }

    if mode == "MP3":
        ydl_opts_base.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320" if quality == "best" else quality,
            }]
        })
    else:
        fmt = (
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]"
            if quality == "best"
            else f"bestvideo[ext=mp4][height<={quality}]+bestaudio[ext=m4a]"
        )
        ydl_opts_base.update({
            "format": fmt,
            "merge_output_format": "mp4"
        })

    try:
        with yt_dlp.YoutubeDL(ydl_opts_base) as ydl:
            ydl.download([url])
        q.put("✔ Finished")
    except Exception as e:
        q.put(f"✖ {e}")

# ================= QUALITY TILE =================
class QualityTile(ctk.CTkButton):
    def __init__(self, parent, app, text, command):
        self.app = app
        self.selected = False

        super().__init__(
            parent,
            text=text,
            height=38,
            fg_color=app.CARD,
            border_width=1,
            border_color=app.SECONDARY,
            text_color=app.TEXT,
            command=command
        )

        # hover handlers
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)

    def on_enter(self, _):
        if not self.selected:
            self.configure(fg_color="#111827", text_color=self.app.TEXT)

    def on_leave(self, _):
        if not self.selected:
            self.configure(fg_color=self.app.CARD, text_color=self.app.TEXT)

    def select(self):
        self.selected = True
        self.configure(fg_color=self.app.ACCENT, text_color="#020617", border_color=self.app.ACCENT)

    def deselect(self):
        self.selected = False
        self.configure(fg_color=self.app.CARD, text_color=self.app.TEXT, border_color=self.app.SECONDARY)

# ================= APP =================
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.geometry("960x850")
        self.title("YT Downloader")

        self.log_q = queue.Queue()
        self.thumb_update_job = None

        # ---- COLORS ----
        self.ACCENT = "#7aa2f7"
        self.SECONDARY = "#64748b"
        self.TEXT = "#cbd5e1"
        self.CARD = "#020617"
        self.BG = "#0f172a"

        self.configure(fg_color=self.BG)

        wrap = ctk.CTkFrame(self, fg_color=self.CARD, corner_radius=22)
        wrap.pack(fill="both", expand=True, padx=24, pady=24)

        ctk.CTkLabel(
            wrap, text="YouTube Downloader",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=self.TEXT
        ).pack(pady=(16, 10))

        self.url_card(wrap)
        self.format_quality_card(wrap)
        self.output_card(wrap)
        self.console_card(wrap)

        self.after(100, self.update_console)

    # ---------- URL ----------
    def url_card(self, p):
        f = self.card(p)
        self.url = ctk.CTkEntry(
            f, height=40, placeholder_text="YouTube URL",
            fg_color=self.CARD, border_color=self.SECONDARY,
            text_color=self.TEXT
        )
        self.url.pack(fill="x", padx=14, pady=10)
        # live update miniaturki
        self.url.bind("<KeyRelease>", self.on_url_change)

        self.thumb = ctk.CTkLabel(f, text="")
        self.thumb.pack(pady=(0, 10))

    def on_url_change(self, event):
        if self.thumb_update_job:
            self.after_cancel(self.thumb_update_job)
        self.thumb_update_job = self.after(500, self.load_thumb)

    def load_thumb(self, *_):
        url = self.url.get().strip()
        if not url:
            self.thumb.configure(image=None)
            return
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "noplaylist": True}) as ydl:
                info = ydl.extract_info(url, download=False)
            img = Image.open(BytesIO(requests.get(info["thumbnail"]).content)).resize((320, 180))
            self.timg = ctk.CTkImage(img, size=(320, 180))
            self.thumb.configure(image=self.timg)
        except:
            self.thumb.configure(image=None)

    # ---------- FORMAT + QUALITY ----------
    def format_quality_card(self, p):
        f = self.card(p)

        self.mode = ctk.StringVar(value="MP3")
        self.format_btn = ctk.CTkSegmentedButton(
            f,
            values=["MP3", "MP4"],
            variable=self.mode,
            fg_color=self.CARD,
            selected_color=self.ACCENT,
            selected_hover_color="#5b8def",
            unselected_color=self.CARD,
            unselected_hover_color="#111827",
            text_color=self.TEXT,
            command=self.build_quality_tiles
        )
        self.format_btn.pack(fill="x", padx=14, pady=(10, 6))

        self.quality_frame = ctk.CTkFrame(f, fg_color="transparent")
        self.quality_frame.pack(fill="x", padx=14, pady=(6, 14))

        self.quality = "best"
        self.tiles = []
        self.build_quality_tiles()

    def build_quality_tiles(self, *_):
        for t in self.tiles:
            t.destroy()
        self.tiles.clear()

        options = ["best", "320kbps", "192kbps", "128kbps"] if self.mode.get() == "MP3" else ["best", "1080p", "720p", "480p"]

        for opt in options:
            tile = QualityTile(
                self.quality_frame,
                self,
                opt,
                lambda v=opt: self.select_quality(v)
            )
            tile.pack(side="left", expand=True, fill="x", padx=4)
            self.tiles.append(tile)

        self.select_quality("best")

    def select_quality(self, val):
        self.quality = val
        for t in self.tiles:
            t.select() if t.cget("text") == val else t.deselect()

    # ---------- OUTPUT ----------
    def output_card(self, p):
        f = self.card(p)
        
        # Folder
        row_folder = ctk.CTkFrame(f, fg_color="transparent")
        row_folder.pack(fill="x", padx=14, pady=(12,6))
        self.folder = ctk.CTkEntry(
            row_folder, placeholder_text="Destination folder",
            fg_color=self.CARD, border_color=self.SECONDARY,
            text_color=self.TEXT
        )
        self.folder.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(
            row_folder, text="📁", width=52,
            fg_color=self.ACCENT, hover_color="#5b8def",
            text_color="#020617",
            command=self.pick_folder
        ).pack(side="right")
        
        # File name
        row_name = ctk.CTkFrame(f, fg_color="transparent")
        row_name.pack(fill="x", padx=14, pady=(6,12))
        self.filename_entry = ctk.CTkEntry(
            row_name, placeholder_text="File name (leave empty to use video title)",
            fg_color=self.CARD, border_color=self.SECONDARY,
            text_color=self.TEXT
        )
        self.filename_entry.pack(fill="x", expand=True)

        # Download button
        ctk.CTkButton(
            f, text="Download", height=44,
            fg_color=self.ACCENT, hover_color="#5b8def",
            text_color="#020617",
            font=ctk.CTkFont(weight="bold"),
            command=self.start
        ).pack(fill="x", padx=14, pady=(0, 14))

    # ---------- CONSOLE ----------
    def console_card(self, p):
        f = self.card(p, expand=True)
        self.console = ctk.CTkTextbox(
            f, fg_color=self.CARD,
            text_color=self.TEXT,
            font=("Consolas", 12)
        )
        self.console.pack(fill="both", expand=True, padx=14, pady=12)
        self.console.configure(state="disabled")

    # ---------- HELPERS ----------
    def card(self, p, expand=False):
        f = ctk.CTkFrame(
            p, fg_color=self.BG,
            corner_radius=16,
            border_width=1,
            border_color=self.SECONDARY
        )
        f.pack(fill="both" if expand else "x", expand=expand, padx=20, pady=10)
        return f

    def pick_folder(self):
        d = filedialog.askdirectory()
        if d:
            self.folder.delete(0, "end")
            self.folder.insert(0, d)

    def start(self):
        filename = self.filename_entry.get().strip()
        threading.Thread(
            target=download_media,
            args=(self.url.get(), self.folder.get(), self.mode.get(), self.quality, self.log_q, filename),
            daemon=True
        ).start()

    def update_console(self):
        while not self.log_q.empty():
            m = self.log_q.get()
            self.console.configure(state="normal")
            self.console.insert("end", m + "\n")
            self.console.see("end")
            self.console.configure(state="disabled")
        self.after(100, self.update_console)

# ================= RUN =================
if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    App().mainloop()
