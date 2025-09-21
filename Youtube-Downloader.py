import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import os
import yt_dlp
import yt_dlp.utils
import subprocess


# ---- Backend Utils ----
def check_ffmpeg():
    """Checks if FFmpeg is installed and accessible in the system's PATH."""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False

def format_size(bytes_val):
    """Formats bytes into a readable string (KB, MB, GB)."""
    if bytes_val is None:
        return "N/A"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.2f} GB"

def format_speed(bytes_per_sec):
    """Formats bytes per second into a readable speed string."""
    if bytes_per_sec is None:
        return "N/A"
    for unit in ['B/s', 'KB/s', 'MB/s', 'GB/s']:
        if bytes_per_sec < 1024:
            return f"{bytes_per_sec:.2f} {unit}"
        bytes_per_sec /= 1024
    return f"{bytes_per_sec:.2f} GB/s"

def format_eta(seconds):
    """Formats seconds into a readable MM:SS or HH:MM:SS string."""
    if seconds is None:
        return "N/A"
    mins, secs = divmod(int(seconds), 60)
    hours, mins = divmod(mins, 60)
    if hours > 0:
        return f"{hours:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


# ---- GUI App ----
class YouTubeDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🎥 Modern YouTube Downloader")
        self.root.geometry("600x550")
        self.root.resizable(False, False)

        # ---- Modern Dark Theme ----
        self.root.configure(bg="#FFFFFF") #whole bg

        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TLabel", background="#FFFFFF", foreground="black", font=("poppins", 11)) #TITLE
        style.configure("TButton", font=("poppins", 10, "bold"), padding=4, relief="flat", borderwidth=0)#fetch
        style.map("TButton",
                  background=[("active", "#4CAF50"), ("!active", "#3A7FE6")],
                  foreground=[("active", "white"), ("!active", "white")]) #fetch button
        style.configure("TEntry", padding=5, fieldbackground="#FFFFFF", foreground="black", borderwidth=3) #save to
        style.configure("TCombobox", fieldbackground="#FFFFFF", background="#3A7FE6",
                        foreground="black", arrowcolor="white", borderwidth=6) #fps
        style.map('TCombobox', fieldbackground=[('readonly', "#E7E4E4")], foreground=[('readonly', 'red')])#quality selection box
        style.configure("green.Horizontal.TProgressbar", troughcolor="#FBFFFF",
                        background="#4CAF50", thickness=25, bordercolor="#000000") #progress bar

        self.cancel_flag = False
        self.available_qualities = []
        self.available_fps = []

        # ---- Title ----
        ttk.Label(root, text="YouTube Video Downloader", font=("Poppins", 16, "bold")).pack(pady=12)

        # ---- Widgets ----
        # URL Input
        ttk.Label(root, text="YouTube URL:").pack(pady=3)
        self.url_entry = ttk.Entry(root, width=70)
        self.url_entry.pack(pady=5)

        # Fetch Info Button
        ttk.Button(root, text="🔍 Fetch Video Info", command=self.fetch_video_info).pack(pady=5)

        # Video Title Display
        self.video_title_label = ttk.Label(root, text="", font=("Segoe UI", 10, "italic"), foreground="#1980E0", wraplength=550)
        self.video_title_label.pack(pady=5)

        # Options Frame
        options_frame = ttk.Frame(root)
        options_frame.pack(pady=0)
        
        # Quality Dropdown
        ttk.Label(options_frame, text="Quality:").grid(row=0, column=0, padx=(0,5), sticky="e")
        self.quality_var = tk.StringVar()
        self.quality_menu = ttk.Combobox(options_frame, textvariable=self.quality_var, state="readonly", width=20)
        self.quality_menu.grid(row=0, column=1, padx=(0,0))

        # FPS Dropdown
        ttk.Label(options_frame, text="FPS:").grid(row=0, column=2, padx=5, sticky="e")
        self.fps_var = tk.StringVar()
        self.fps_menu = ttk.Combobox(options_frame, textvariable=self.fps_var, state="readonly", width=20)
        self.fps_menu.grid(row=0, column=3, padx=(0,5))
        
        # Folder Frame
        folder_frame = ttk.Frame(root)
        folder_frame.pack(pady=10)
        
        ttk.Label(folder_frame, text="Save to:").grid(row=0, column=0, padx=(0,4))
        self.output_path = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Downloads"))
        self.folder_entry = ttk.Entry(folder_frame, textvariable=self.output_path, width=50)
        self.folder_entry.grid(row=0, column=1, padx=0)
        ttk.Button(folder_frame, text="Browse", command=self.browse_folder).grid(row=0, column=2, padx=(5,0))

        # Buttons
        self.btn_frame = ttk.Frame(root)
        self.btn_frame.pack(pady=15)
        self.download_btn = ttk.Button(self.btn_frame, text="DOWNLOAD", command=self.start_download_thread)
        self.download_btn.grid(row=0, column=0, padx=(0,8))
        self.cancel_btn = ttk.Button(self.btn_frame, text="Cancel", command=self.cancel_download, state="disabled")
        self.cancel_btn.grid(row=0, column=1, padx=(8,0))

        # Progress Bar and Status
        ttk.Label(root, text="Progress Bar", font=("Poppins", 10, "bold")).pack(pady=6)
        self.progress = ttk.Progressbar(root, orient="horizontal", length=500, mode="determinate", style="green.Horizontal.TProgressbar")
        self.progress.pack(pady=(10, 0))
        self.status_label = tk.Label(root, text="", fg="#4CAF50", bg="#FFFFFF", font=("poppins", 10))
        self.status_label.pack()

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_path.set(folder)

    def fetch_video_info(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a YouTube URL first!")
            return
        
        # Run in a separate thread to keep the GUI responsive
        threading.Thread(target=self._fetch_info_worker, args=(url,), daemon=True).start()

    def _fetch_info_worker(self, url):
        try:
            self.status_label.config(text="Fetching video info...", fg="#FFD207") # Yellow
            self.root.update_idletasks()

            ydl_opts = {'quiet': True, 'noplaylist': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                formats = info.get('formats', [])
                title = info.get('title', "Unknown Title")

            self.video_title_label.config(text=f"🎬 {title}")

            heights = sorted({f.get('height') for f in formats if f.get('height') and f.get('vcodec') != 'none'}, reverse=True)
            self.available_qualities = [f"{h}p" for h in heights]

            fps_list = sorted({f.get('fps') for f in formats if f.get('fps') and f.get('vcodec') != 'none'}, reverse=True)
            self.available_fps = [str(int(fps)) for fps in fps_list]

            self.quality_menu['values'] = self.available_qualities
            if self.available_qualities:
                self.quality_var.set(self.available_qualities[0])

            self.fps_menu['values'] = self.available_fps
            if self.available_fps:
                self.fps_var.set(self.available_fps[0])

            self.status_label.config(text="Video info loaded. Ready to download.", fg="#4CAF50") # Green

        except Exception as e:
            self.status_label.config(text="Failed to fetch info.", fg="red")
            messagebox.showerror("Error", f"Failed to fetch video info:\n{str(e)}")

    def start_download_thread(self):
        if not self.quality_var.get() or not self.fps_var.get():
            messagebox.showwarning("Warning", "Please fetch video info and select a quality first.")
            return
            
        self.cancel_flag = False
        self.progress['value'] = 0
        self.download_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        threading.Thread(target=self.download_video, daemon=True).start()

    def cancel_download(self):
        self.cancel_flag = True
        self.status_label.config(text="Cancelling download...", fg="#FFC107") # Yellow
        self.cancel_btn.config(state="disabled")

    def progress_hook(self, d):
        if self.cancel_flag:
            raise yt_dlp.utils.DownloadCancelled("Download cancelled by user.")

        if d['status'] == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded_bytes = d.get('downloaded_bytes', 0)
            speed = d.get('speed')
            eta = d.get('eta')
            
            percentage = (downloaded_bytes / total_bytes * 100) if total_bytes else 0
            self.progress['value'] = percentage
            
            status_text = (
                f"Downloading... {percentage:.1f}% of {format_size(total_bytes)} "
                f"| {format_speed(speed)} | ETA: {format_eta(eta)}"
            )
            self.status_label.config(text=status_text, fg="#4CAF50") # Green
            self.root.update_idletasks()

        elif d['status'] == 'finished':
            self.progress['value'] = 100
            self.status_label.config(text="✅ Download finished! Merging formats...", fg="#4CAF50")

        elif d['status'] == 'error':
            self.status_label.config(text="❌ Error during download.", fg="red")

    def download_video(self):
        url = self.url_entry.get().strip()
        quality = self.quality_var.get().replace("p", "")
        fps = int(self.fps_var.get())
        output_path = self.output_path.get()
        
        os.makedirs(output_path, exist_ok=True)

        try:
            if not check_ffmpeg():
                messagebox.showwarning("FFmpeg Not Found", "FFmpeg is not found. Video and audio may download as separate files.")

            ydl_opts = {
                'format': f'bestvideo[height<={quality}][fps<={fps}]+bestaudio/best[height<={quality}][fps<={fps}]/best',
                'progress_hooks': [self.progress_hook],
                'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
                'quiet': True,
                'noplaylist': True,
                'merge_output_format': 'mp4',
            }
            
            self.status_label.config(text=f"Starting download for {quality}p at {fps} FPS...", fg="#4CAF50")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            if not self.cancel_flag:
                messagebox.showinfo("Success", "Download completed successfully!")
                self.status_label.config(text="✅ Download complete!", fg="#4CAF50")

        except yt_dlp.utils.DownloadCancelled:
            messagebox.showinfo("Cancelled", "The download was cancelled.")
            self.status_label.config(text="Download cancelled.", fg="#FFC107") # Yellow

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")
            self.status_label.config(text=f"Error: {e}", fg="red")

        finally:
            self.reset_ui_state()

    def reset_ui_state(self):
        self.download_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")
        self.progress['value'] = 0


# ---- Run GUI ----
if __name__ == "__main__":
    root = tk.Tk()
    app = YouTubeDownloaderApp(root)
    root.mainloop()