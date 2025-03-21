import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from PIL import Image, ImageTk
import os
from rembg import remove
import dotenv
import threading
import subprocess
from ttkthemes import ThemedTk

# Load environment variables
dotenv.load_dotenv()
DEFAULT_SAVE_PATH = os.getenv('DEFAULT_SAVE_PATH', os.path.expanduser("~/Processed_Images"))

class ImageProcessorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Cool Image Processor")
        self.root.geometry("1200x700")
        self.root.minsize(600, 300)

        # Apply modern theme
        self.root.set_theme("arc")

        # Set application icon
        self.icon_path = "app_icon.png"
        if os.path.exists(self.icon_path):
            self.root.iconphoto(True, tk.PhotoImage(file=self.icon_path))

        self.image_files = []
        self.processed_files = []
        self.save_path = DEFAULT_SAVE_PATH
        self.thumbnails = []
        self.processed_thumbnails = []
        self.preview_image = None
        self.preview_zoom_factor = 1.0
        self.processing_thread = None
        self.stop_processing = False

        # Load icons with fallback
        try:
            self.delete_icon = ImageTk.PhotoImage(Image.open("delete.png").resize((20, 20)))
        except FileNotFoundError:
            self.delete_icon = None
        try:
            self.change_icon = ImageTk.PhotoImage(Image.open("change.png").resize((20, 20)))
        except FileNotFoundError:
            self.change_icon = None
        try:
            self.view_icon = ImageTk.PhotoImage(Image.open("view.png").resize((20, 20)))
        except FileNotFoundError:
            self.view_icon = None

        self.create_menu()
        self.create_gui()

    def create_menu(self):
        menubar = tk.Menu(self.root, bg="#2d2d2d", fg="white", activebackground="#4a4a4a", activeforeground="white")
        self.root.config(menu=menubar)

        help_menu = tk.Menu(menubar, tearoff=0, bg="#2d2d2d", fg="white", activebackground="#4a4a4a")
        help_menu.add_command(label="About", command=self.show_about)
        help_menu.add_command(label="Guide", command=self.show_guide)
        help_menu.add_command(label="Terms & Privacy", command=self.show_terms)
        menubar.add_cascade(label="Help", menu=help_menu)

        view_menu = tk.Menu(menubar, tearoff=0, bg="#2d2d2d", fg="white", activebackground="#4a4a4a")
        view_menu.add_command(label="Processed Files", command=self.show_processed_files)
        menubar.add_cascade(label="View", menu=view_menu)

    def show_about(self):
        messagebox.showinfo("About", "Cool Image Processor v1.0\nDeveloped by XYZ\nA modern tool for removing image backgrounds.")

    def show_guide(self):
        messagebox.showinfo("Guide", "1. Import images\n2. Click row to preview with Ctrl++/- zoom\n3. Process images, stop with End Process\n4. View processed files with zoom & scroll")

    def show_terms(self):
        messagebox.showinfo("Terms & Privacy", "This software does not store or share any personal data. Use at your own risk.")

    def create_gui(self):
        self.main_frame = ttk.Frame(self.root, padding=10, style="Main.TFrame")
        self.main_frame.pack(fill='both', expand=True)

        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(2, weight=1)

        # Style configuration
        style = ttk.Style()
        style.configure("Main.TFrame", background="#f0f0f0")
        style.configure("TButton", font=("Helvetica", 10), padding=6)
        style.configure("TLabel", font=("Helvetica", 10))
        style.configure("Status.TLabel", font=("Helvetica", 12, "bold"), foreground="#2ecc71")

        # Control frame
        control_frame = ttk.Frame(self.main_frame, style="Main.TFrame")
        control_frame.grid(row=0, column=0, sticky='ew', pady=(0, 10))

        ttk.Button(control_frame, text="Import Images", command=self.import_images).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Select Save Folder", command=self.select_save_folder).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Process Images", command=self.start_processing).pack(side='left', padx=5)
        ttk.Button(control_frame, text="End Process", command=self.end_processing).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Remove All", command=self.remove_all).pack(side='right', padx=5)

        # Status and progress
        status_frame = ttk.Frame(self.main_frame, style="Main.TFrame")
        status_frame.grid(row=1, column=0, sticky='ew', pady=5)

        self.status_label = ttk.Label(status_frame, text="Ready", style="Status.TLabel")
        self.status_label.pack(side='top')

        self.progress = ttk.Progressbar(status_frame, length=300, mode='determinate')
        self.progress.pack(side='top', fill='x', padx=5, pady=5)

        # Paned window for resizable list and preview
        self.paned_window = ttk.PanedWindow(self.main_frame, orient=tk.HORIZONTAL)
        self.paned_window.grid(row=2, column=0, sticky='nsew')

        # List frame
        list_frame = ttk.Frame(self.paned_window)
        self.paned_window.add(list_frame, weight=3)

        self.canvas = tk.Canvas(list_frame, bg="#ffffff", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Preview frame with zoom and scroll
        preview_frame = ttk.Frame(self.paned_window)
        self.paned_window.add(preview_frame, weight=1)

        self.preview_canvas = tk.Canvas(preview_frame, bg="#ffffff", highlightthickness=0)
        self.preview_h_scroll = ttk.Scrollbar(preview_frame, orient="horizontal", command=self.preview_canvas.xview)
        self.preview_v_scroll = ttk.Scrollbar(preview_frame, orient="vertical", command=self.preview_canvas.yview)
        self.preview_canvas.configure(xscrollcommand=self.preview_h_scroll.set, yscrollcommand=self.preview_v_scroll.set)

        self.preview_canvas.pack(side="top", fill="both", expand=True)
        self.preview_h_scroll.pack(side="bottom", fill="x")
        self.preview_v_scroll.pack(side="right", fill="y")

        self.preview_label = ttk.Label(self.preview_canvas)
        self.preview_canvas.create_window((0, 0), window=self.preview_label, anchor="center")

        zoom_frame = ttk.Frame(preview_frame)
        zoom_frame.pack(pady=5)
        ttk.Button(zoom_frame, text="+", command=self.zoom_in_preview).pack(side='left', padx=5)
        ttk.Button(zoom_frame, text="-", command=self.zoom_out_preview).pack(side='left', padx=5)
        self.preview_filepath = None

        self.preview_canvas.bind("<MouseWheel>", self._on_preview_mousewheel)
        self.preview_canvas.bind("<Shift-MouseWheel>", lambda e: self.preview_canvas.xview_scroll(int(-1 * (e.delta / 120)), "units"))
        self.preview_canvas.bind("<Button-4>", lambda e: self.preview_canvas.yview_scroll(-1, "units"))
        self.preview_canvas.bind("<Button-5>", lambda e: self.preview_canvas.yview_scroll(1, "units"))
        self.preview_canvas.bind("<Shift-Button-4>", lambda e: self.preview_canvas.xview_scroll(-1, "units"))
        self.preview_canvas.bind("<Shift-Button-5>", lambda e: self.preview_canvas.xview_scroll(1, "units"))

        # Keyboard shortcuts for zoom
        self.root.bind("<Control-plus>", lambda e: self.zoom_in_preview())
        self.root.bind("<Control-minus>", lambda e: self.zoom_out_preview())

        self.clear_preview()

        # Counter
        self.counter_label = ttk.Label(self.main_frame, text="0 Images", font=("Helvetica", 10))
        self.counter_label.grid(row=3, column=0, sticky='ew', pady=5)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_preview_mousewheel(self, event):
        self.preview_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def import_images(self):
        files = filedialog.askopenfilenames(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp")])
        for file in files:
            if file not in self.image_files:
                self.image_files.append(file)
                self.add_image_to_list(file)
        self.update_counter()

    def add_image_to_list(self, filepath):
        filename = os.path.basename(filepath)
        frame = ttk.Frame(self.scrollable_frame, style="Main.TFrame")
        frame.pack(fill='x', pady=2)

        frame.columnconfigure(1, weight=1)

        try:
            img = Image.open(filepath)
            img.thumbnail((50, 50))
            thumbnail = ImageTk.PhotoImage(img)
            self.thumbnails.append(thumbnail)
            ttk.Label(frame, image=thumbnail).grid(row=0, column=0, padx=5)
        except Exception as e:
            ttk.Label(frame, text="No Preview").grid(row=0, column=0, padx=5)

        ttk.Label(frame, text=filename, anchor='w').grid(row=0, column=1, sticky='ew', padx=5)
        ttk.Button(frame, image=self.delete_icon, text="Delete" if not self.delete_icon else "", compound="left",
                   command=lambda: self.delete_image(filepath)).grid(row=0, column=2, padx=5)
        ttk.Button(frame, image=self.change_icon, text="Change" if not self.change_icon else "", compound="left",
                   command=lambda: self.change_image(filepath)).grid(row=0, column=3, padx=5)

        # Bind left-click to show preview
        frame.bind("<Button-1>", lambda e, f=filepath: self.show_preview(f))

    def show_preview(self, filepath):
        self.preview_filepath = filepath
        self.update_preview()

    def update_preview(self):
        if not self.preview_filepath:
            return
        try:
            img = Image.open(self.preview_filepath)
            base_size = 300
            new_size = int(base_size * self.preview_zoom_factor)
            img = img.resize((new_size, new_size), Image.Resampling.LANCZOS)
            self.preview_image = ImageTk.PhotoImage(img)
            self.preview_label.config(image=self.preview_image)
            self.preview_canvas.configure(scrollregion=(0, 0, new_size, new_size))
            self.preview_canvas.coords(self.preview_label, new_size // 2, new_size // 2)  # Center the image
        except Exception as e:
            self.preview_label.config(image="", text=f"Cannot preview: {str(e)}")

    def zoom_in_preview(self):
        self.preview_zoom_factor = min(self.preview_zoom_factor * 1.2, 5.0)
        self.update_preview()

    def zoom_out_preview(self):
        self.preview_zoom_factor = max(self.preview_zoom_factor / 1.2, 0.2)
        self.update_preview()

    def clear_preview(self):
        self.preview_image = None
        self.preview_filepath = None
        self.preview_zoom_factor = 1.0
        self.preview_label.config(image="", text="Click an image to preview")
        self.preview_canvas.configure(scrollregion=(0, 0, 0, 0))

    def delete_image(self, filepath):
        self.image_files.remove(filepath)
        for widget in self.scrollable_frame.winfo_children():
            if widget.winfo_children()[1]['text'] == os.path.basename(filepath):
                widget.destroy()
                break
        self.update_counter()
        messagebox.showinfo("Success", f"Image {os.path.basename(filepath)} deleted.")
        if self.preview_filepath == filepath:
            self.clear_preview()

    def change_image(self, filepath):
        new_image = filedialog.askopenfilename(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp")])
        if new_image and new_image != filepath:
            index = self.image_files.index(filepath)
            self.image_files[index] = new_image
            for widget in self.scrollable_frame.winfo_children():
                if widget.winfo_children()[1]['text'] == os.path.basename(filepath):
                    widget.destroy()
                    self.add_image_to_list(new_image)
                    break
            messagebox.showinfo("Success", f"Image changed to {os.path.basename(new_image)}.")
            if self.preview_filepath == filepath:
                self.show_preview(new_image)

    def remove_all(self):
        self.image_files.clear()
        self.thumbnails.clear()
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.update_counter()
        messagebox.showinfo("Success", "All images removed.")
        self.clear_preview()

    def update_counter(self):
        self.counter_label.config(text=f"{len(self.image_files)} Images")

    def select_save_folder(self):
        self.save_path = filedialog.askdirectory(initialdir=self.save_path)
        if not self.save_path:
            messagebox.showerror("Error", "Please select a save folder!")
        else:
            messagebox.showinfo("Success", f"Save folder set to: {self.save_path}")

    def start_processing(self):
        if not self.save_path:
            messagebox.showerror("Error", "Save folder not selected!")
            return
        if not self.image_files:
            messagebox.showerror("Error", "No images to process!")
            return
        self.stop_processing = False
        self.processing_thread = threading.Thread(target=self.process_images, daemon=True)
        self.processing_thread.start()

    def process_images(self):
        os.makedirs(self.save_path, exist_ok=True)
        self.progress['maximum'] = len(self.image_files)
        self.status_label.config(text="Processing...")
        self.processed_files.clear()

        for i, filepath in enumerate(self.image_files):
            if self.stop_processing:
                self.status_label.config(text="Processing Stopped")
                return
            try:
                input_image = Image.open(filepath).convert("RGBA")
                output_image = remove(input_image)
                filename = os.path.splitext(os.path.basename(filepath))[0] + "_nobg.png"
                output_path = os.path.join(self.save_path, filename)
                output_image.save(output_path, format="PNG")
                self.processed_files.append(output_path)
                self.progress['value'] = i + 1
                self.root.update_idletasks()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to process {os.path.basename(filepath)}: {str(e)}")

        self.status_label.config(text="Processing Completed!")
        messagebox.showinfo("Success", "Image processing completed! Opening folder...")
        self.open_save_folder()

    def end_processing(self):
        if self.processing_thread and self.processing_thread.is_alive():
            self.stop_processing = True
            self.processing_thread.join()
            messagebox.showinfo("Success", "Processing stopped.")

    def open_save_folder(self):
        if os.name == 'nt':  # Windows
            os.startfile(self.save_path)
        elif os.name == 'posix':  # MacOS/Linux
            subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', self.save_path])

    def show_processed_files(self):
        if not self.processed_files:
            messagebox.showinfo("Info", "No successfully processed files yet.")
            return

        processed_window = tk.Toplevel(self.root)
        processed_window.title("Processed Files")
        processed_window.geometry("800x600")
        if os.path.exists(self.icon_path):
            processed_window.iconphoto(True, tk.PhotoImage(file=self.icon_path))

        canvas = tk.Canvas(processed_window, bg="#ffffff", highlightthickness=0)
        scrollbar = ttk.Scrollbar(processed_window, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        canvas.bind("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")

        control_frame = ttk.Frame(processed_window)
        control_frame.pack(fill='x', pady=5)
        ttk.Button(control_frame, text="Delete All", command=lambda: self.delete_all_processed(scrollable_frame)).pack(side='right', padx=5)

        for filepath in self.processed_files:
            frame = ttk.Frame(scrollable_frame, style="Main.TFrame")
            frame.pack(fill='x', pady=2)
            frame.columnconfigure(1, weight=1)

            try:
                img = Image.open(filepath)
                img.thumbnail((50, 50))
                thumbnail = ImageTk.PhotoImage(img)
                self.processed_thumbnails.append(thumbnail)
                ttk.Label(frame, image=thumbnail).grid(row=0, column=0, padx=5)
            except Exception as e:
                ttk.Label(frame, text="No Preview").grid(row=0, column=0, padx=5)

            ttk.Label(frame, text=os.path.basename(filepath), anchor='w').grid(row=0, column=1, sticky='ew', padx=5)
            ttk.Button(frame, image=self.view_icon, text="View" if not self.view_icon else "", compound="left",
                       command=lambda f=filepath: self.view_processed_file(f)).grid(row=0, column=2, padx=5)
            ttk.Button(frame, image=self.delete_icon, text="Delete" if not self.delete_icon else "", compound="left",
                       command=lambda f=filepath: self.delete_processed_file(f, frame)).grid(row=0, column=3, padx=5)

        processed_window.protocol("WM_DELETE_WINDOW", lambda: self.on_processed_window_close(processed_window, canvas))

    def on_processed_window_close(self, window, canvas):
        canvas.unbind_all("<MouseWheel>")
        canvas.unbind_all("<Button-4>")
        canvas.unbind_all("<Button-5>")
        window.destroy()

    def view_processed_file(self, filepath):
        try:
            view_window = tk.Toplevel(self.root)
            view_window.title(os.path.basename(filepath))
            view_window.geometry("600x500")
            if os.path.exists(self.icon_path):
                view_window.iconphoto(True, tk.PhotoImage(file=self.icon_path))

            canvas = tk.Canvas(view_window, bg="#ffffff", highlightthickness=0)
            h_scroll = ttk.Scrollbar(view_window, orient="horizontal", command=canvas.xview)
            v_scroll = ttk.Scrollbar(view_window, orient="vertical", command=canvas.yview)
            canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)

            canvas.pack(side="top", fill="both", expand=True)
            h_scroll.pack(side="bottom", fill="x")
            v_scroll.pack(side="right", fill="y")

            label = ttk.Label(canvas)
            canvas.create_window((0, 0), window=label, anchor="center")

            img = Image.open(filepath)
            base_size = 400
            zoom_factor = 1.0

            def update_image():
                nonlocal zoom_factor
                new_size = int(base_size * zoom_factor)
                resized_img = img.resize((new_size, new_size), Image.Resampling.LANCZOS)
                preview = ImageTk.PhotoImage(resized_img)
                label.config(image=preview)
                label.image = preview
                canvas.configure(scrollregion=(0, 0, new_size, new_size))
                canvas.coords(label, new_size // 2, new_size // 2)

            zoom_frame = ttk.Frame(view_window)
            zoom_frame.pack(pady=5)
            ttk.Button(zoom_frame, text="+", command=lambda: [self.zoom_in_processed(update_image, zoom_factor), update_image()]).pack(side='left', padx=5)
            ttk.Button(zoom_frame, text="-", command=lambda: [self.zoom_out_processed(update_image, zoom_factor), update_image()]).pack(side='left', padx=5)

            canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
            canvas.bind("<Shift-MouseWheel>", lambda e: canvas.xview_scroll(int(-1 * (e.delta / 120)), "units"))
            canvas.bind("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
            canvas.bind("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))
            canvas.bind("<Shift-Button-4>", lambda e: canvas.xview_scroll(-1, "units"))
            canvas.bind("<Shift-Button-5>", lambda e: canvas.xview_scroll(1, "units"))

            view_window.bind("<Control-plus>", lambda e: [self.zoom_in_processed(update_image, zoom_factor), update_image()])
            view_window.bind("<Control-minus>", lambda e: [self.zoom_out_processed(update_image, zoom_factor), update_image()])

            update_image()

            view_window.protocol("WM_DELETE_WINDOW", lambda: self.on_view_window_close(view_window, canvas))
        except Exception as e:
            messagebox.showerror("Error", f"Could not view {os.path.basename(filepath)}: {str(e)}")

    def on_view_window_close(self, window, canvas):
        canvas.unbind_all("<MouseWheel>")
        canvas.unbind_all("<Shift-MouseWheel>")
        canvas.unbind_all("<Button-4>")
        canvas.unbind_all("<Button-5>")
        canvas.unbind_all("<Shift-Button-4>")
        canvas.unbind_all("<Shift-Button-5>")
        window.destroy()

    def zoom_in_processed(self, update_callback, zoom_factor):
        zoom_factor = min(zoom_factor * 1.2, 5.0)
        return zoom_factor

    def zoom_out_processed(self, update_callback, zoom_factor):
        zoom_factor = max(zoom_factor / 1.2, 0.2)
        return zoom_factor

    def delete_processed_file(self, filepath, frame):
        if filepath in self.processed_files:
            self.processed_files.remove(filepath)
            frame.destroy()
            if os.path.exists(filepath):
                os.remove(filepath)
            messagebox.showinfo("Success", f"Processed file {os.path.basename(filepath)} deleted.")
        if not self.processed_files:
            frame.winfo_toplevel().destroy()

    def delete_all_processed(self, scrollable_frame):
        for filepath in self.processed_files[:]:
            if os.path.exists(filepath):
                os.remove(filepath)
        self.processed_files.clear()
        self.processed_thumbnails.clear()
        for widget in scrollable_frame.winfo_children():
            widget.destroy()
        messagebox.showinfo("Success", "All processed files deleted.")
        scrollable_frame.winfo_toplevel().destroy()

if __name__ == "__main__":
    import sys
    root = ThemedTk(theme="arc")
    app = ImageProcessorApp(root)
    root.mainloop()