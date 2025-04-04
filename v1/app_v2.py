import tkinter as tk
from tkinter import filedialog, ttk, messagebox, simpledialog, colorchooser
from PIL import Image, ImageTk
import os
from rembg import remove
import dotenv
import threading
import subprocess
from ttkthemes import ThemedTk
import numpy as np
import face_recognition

# Load environment variables
dotenv.load_dotenv()
DEFAULT_SAVE_PATH = os.getenv('DEFAULT_SAVE_PATH', os.path.expanduser("~/Processed_Images"))

class ImageProcessorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Smart Remove BG & Crop Image")
        self.root.geometry("1200x700")
        self.root.minsize(600, 300)

        # Use the "arc" theme from ttkthemes
        self.root.set_theme("arc")

        # Optional: Application icon
        self.icon_path = "app_icon.png"
        if os.path.exists(self.icon_path):
            self.root.iconphoto(True, tk.PhotoImage(file=self.icon_path))

        # Initialize variables
        self.image_files = []
        self.processed_files = []
        self.save_path = DEFAULT_SAVE_PATH
        self.thumbnails = []
        self.processed_thumbnails = []
        self.preview_image = None
        self.preview_filepath = None
        self.preview_zoom_factor = 1.0
        self.processing_thread = None
        self.stop_processing = False

        # Load icons from external image files
        self.delete_icon = self.load_icon("delete.png")
        self.change_icon = self.load_icon("change.png")
        self.view_icon   = self.load_icon("view.png")

        # Create menu and UI
        self.create_menu()
        self.create_gui()

    def load_icon(self, path):
        try:
            icon = Image.open(path).resize((20, 20), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(icon)
        except Exception as e:
            print(f"Error loading icon {path}: {e}")
            return None

    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # Help Menu (menu items don't support "style")
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        help_menu.add_command(label="Guide", command=self.show_guide)
        help_menu.add_command(label="Terms & Privacy", command=self.show_terms)
        menubar.add_cascade(label="Help", menu=help_menu)

        # View Menu
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Processed Files", command=self.show_processed_files)
        menubar.add_cascade(label="View", menu=view_menu)

        # Tools Menu (Smart Crop)
        tools_menu = tk.Menu(menubar, tearoff=0)
        smart_crop_menu = tk.Menu(tools_menu, tearoff=0)
        smart_crop_menu.add_command(label="1:1 (Square)", command=lambda: self.smart_crop_images(1, 1))
        smart_crop_menu.add_command(label="4:6 (Portrait)", command=lambda: self.smart_crop_images(4, 6))
        smart_crop_menu.add_command(label="16:9 (Widescreen)", command=lambda: self.smart_crop_images(16, 9))
        smart_crop_menu.add_command(label="3:2 (Photo)", command=lambda: self.smart_crop_images(3, 2))
        smart_crop_menu.add_command(label="Custom Ratio", command=self.smart_crop_custom)
        tools_menu.add_cascade(label="Smart Crop", menu=smart_crop_menu)
        menubar.add_cascade(label="Tools", menu=tools_menu)

        # Quick Tools Menu
        quick_tools_menu = tk.Menu(menubar, tearoff=0)
        fast_crop_menu = tk.Menu(quick_tools_menu, tearoff=0)
        fast_crop_menu.add_command(label="100x100", command=lambda: self.fast_crop_images(100, 100))
        fast_crop_menu.add_command(label="200x200", command=lambda: self.fast_crop_images(200, 200))
        fast_crop_menu.add_command(label="300x400", command=lambda: self.fast_crop_images(300, 400))
        fast_crop_menu.add_command(label="Custom Size", command=self.fast_crop_custom)
        quick_tools_menu.add_cascade(label="Fast Crop", menu=fast_crop_menu)
        quick_tools_menu.add_command(label="Resize All", command=self.resize_all)
        quick_tools_menu.add_command(label="Convert to JPG", command=self.convert_to_jpg)
        menubar.add_cascade(label="Quick Tools", menu=quick_tools_menu)

    def show_about(self):
        messagebox.showinfo("About", "Smart Remove BG & Crop Image: v1.0\nDeveloped by: novhuninfo@gmail.com")

    def show_guide(self):
        messagebox.showinfo(
            "Guide",
            "1. Import images\n2. Click a row to preview (use Ctrl+MouseWheel or Ctrl+/- to zoom)\n"
            "3. Process, Smart Crop, or use Quick Tools\n4. View processed files"
        )

    def show_terms(self):
        messagebox.showinfo("Terms & Privacy", "No data stored or shared. Use at your own risk.")

    def create_gui(self):
        # Configure a custom style for cool button look
        style = ttk.Style()
        style.theme_use("clam")  # "clam" supports background modifications
        style.configure("Cool.TButton", foreground="white", background="#3498db",
                        font=("Helvetica", 10, "bold"), padding=6)
        style.map("Cool.TButton", background=[('active', '#2980b9')])
        style.configure("TLabel", font=("Helvetica", 10))
        style.configure("Status.TLabel", font=("Helvetica", 12, "bold"))

        self.main_frame = ttk.Frame(self.root, padding=10)
        self.main_frame.pack(fill='both', expand=True)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(2, weight=1)

        # Control Frame
        control_frame = ttk.Frame(self.main_frame)
        control_frame.grid(row=0, column=0, sticky='ew', pady=(0, 10))
        controls = [
            ("Import Images", self.import_images),
            ("Select Save Folder", self.select_save_folder),
            ("Process Images", self.start_processing),
            ("End Process", self.end_processing),
            ("Remove All", self.remove_all)
        ]
        for text, cmd in controls:
            ttk.Button(control_frame, text=text, command=cmd, style="Cool.TButton").pack(
                side='right' if text == "Remove All" else 'left', padx=5
            )

        # Status Frame
        status_frame = ttk.Frame(self.main_frame)
        status_frame.grid(row=1, column=0, sticky='ew', pady=5)
        self.status_label = ttk.Label(status_frame, text="Ready", style="Status.TLabel")
        self.status_label.pack(side='top')
        self.progress = ttk.Progressbar(status_frame, length=300, mode='determinate')
        self.progress.pack(side='top', fill='x', padx=5, pady=5)

        # Paned Window: Image List & Preview
        self.paned_window = ttk.PanedWindow(self.main_frame, orient=tk.HORIZONTAL)
        self.paned_window.grid(row=2, column=0, sticky='nsew')

        # Left: List of Images
        list_frame = ttk.Frame(self.paned_window)
        self.paned_window.add(list_frame, weight=3)
        self.canvas = tk.Canvas(list_frame, bg="white", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Right: Preview Area
        preview_frame = ttk.Frame(self.paned_window)
        self.paned_window.add(preview_frame, weight=1)
        self.preview_canvas = tk.Canvas(preview_frame, bg="white", highlightthickness=0)
        self.preview_h_scroll = ttk.Scrollbar(preview_frame, orient="horizontal", command=self.preview_canvas.xview)
        self.preview_v_scroll = ttk.Scrollbar(preview_frame, orient="vertical", command=self.preview_canvas.yview)
        self.preview_canvas.configure(
            xscrollcommand=self.preview_h_scroll.set,
            yscrollcommand=self.preview_v_scroll.set
        )
        self.preview_canvas.pack(side="top", fill="both", expand=True)
        self.preview_h_scroll.pack(side="bottom", fill="x")
        self.preview_v_scroll.pack(side="right", fill="y")
        self.preview_label = ttk.Label(self.preview_canvas, text="Click an image to preview")
        self.preview_canvas.create_window((0, 0), window=self.preview_label, anchor="nw")

        # Zoom Controls
        zoom_frame = ttk.Frame(preview_frame)
        zoom_frame.pack(pady=5)
        ttk.Button(zoom_frame, text="+", command=self.zoom_in_preview, style="Cool.TButton").pack(side='left', padx=5)
        ttk.Button(zoom_frame, text="-", command=self.zoom_out_preview, style="Cool.TButton").pack(side='left', padx=5)

        # Bindings
        self.canvas.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<MouseWheel>", self._on_mousewheel_list)
        self.preview_canvas.bind("<MouseWheel>", self._on_mousewheel_preview)
        self.root.bind("<Control-plus>", lambda e: self.zoom_in_preview())
        self.root.bind("<Control-minus>", lambda e: self.zoom_out_preview())
        self.clear_preview()
        self.counter_label = ttk.Label(self.main_frame, text="0 Images", font=("Helvetica", 10))
        self.counter_label.grid(row=3, column=0, sticky='ew', pady=5)

    def _on_mousewheel_list(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_mousewheel_preview(self, event):
        if (event.state & 0x0004) != 0:
            if event.delta > 0:
                self.zoom_in_preview()
            else:
                self.zoom_out_preview()
        else:
            self.preview_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def import_images(self):
        files = filedialog.askopenfilenames(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp")])
        new_files = [f for f in files if f not in self.image_files]
        self.image_files.extend(new_files)
        for file in new_files:
            self.add_image_to_list(file)
        self.update_counter()
        if new_files:
            messagebox.showinfo("Import Complete", f"Imported {len(new_files)} new image(s).")

    def add_image_to_list(self, filepath):
        frame = ttk.Frame(self.scrollable_frame)
        frame.pack(fill='x', pady=2)
        frame.columnconfigure(1, weight=1)
        try:
            img = Image.open(filepath)
            img.thumbnail((50, 50))
            thumbnail = ImageTk.PhotoImage(img)
            self.thumbnails.append(thumbnail)
            ttk.Label(frame, image=thumbnail).grid(row=0, column=0, padx=5)
        except Exception:
            ttk.Label(frame, text="No Preview").grid(row=0, column=0, padx=5)
        label = ttk.Label(frame, text=os.path.basename(filepath))
        label.grid(row=0, column=1, sticky='ew', padx=5)
        ttk.Button(frame, text="Delete", image=self.delete_icon, compound="left",
                   command=lambda: self.delete_image(filepath), style="Cool.TButton").grid(row=0, column=2, padx=5)
        ttk.Button(frame, text="Change", image=self.change_icon, compound="left",
                   command=lambda: self.change_image(filepath), style="Cool.TButton").grid(row=0, column=3, padx=5)
        for widget in [frame, label]:
            widget.bind("<Button-1>", lambda e, f=filepath: self.show_preview(f))

    def show_preview(self, filepath):
        self.preview_filepath = filepath
        self.update_preview()

    def update_preview(self):
        if not self.preview_filepath or not os.path.exists(self.preview_filepath):
            self.preview_label.config(image="", text="Click an image to preview")
            self.preview_canvas.configure(scrollregion=(0, 0, 0, 0))
            return
        try:
            img = Image.open(self.preview_filepath)
            max_size = 400
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            base_dim = max(img.size)
            new_size = int(base_dim * self.preview_zoom_factor)
            w, h = img.size
            aspect_ratio = w / h
            if w > h:
                resized_width = new_size
                resized_height = int(new_size / aspect_ratio)
            else:
                resized_height = new_size
                resized_width = int(new_size * aspect_ratio)
            resized_img = img.resize((resized_width, resized_height), Image.Resampling.LANCZOS)
            self.preview_image = ImageTk.PhotoImage(resized_img)
            self.preview_label.config(image=self.preview_image, text="")
            self.preview_canvas.configure(scrollregion=(0, 0, resized_width, resized_height))
        except Exception as e:
            self.preview_label.config(image="", text=f"Error: {str(e)}")
            self.preview_canvas.configure(scrollregion=(0, 0, 0, 0))

    def zoom_in_preview(self):
        self.preview_zoom_factor = min(self.preview_zoom_factor * 1.1, 5.0)
        self.update_preview()

    def zoom_out_preview(self):
        self.preview_zoom_factor = max(self.preview_zoom_factor / 1.1, 0.2)
        self.update_preview()

    def clear_preview(self):
        self.preview_image = None
        self.preview_filepath = None
        self.preview_zoom_factor = 1.0
        self.preview_label.config(image="", text="Click an image to preview")
        self.preview_canvas.configure(scrollregion=(0, 0, 0, 0))

    def delete_image(self, filepath):
        if filepath in self.image_files:
            self.image_files.remove(filepath)
        for widget in self.scrollable_frame.winfo_children():
            lbl = widget.winfo_children()[1]
            if lbl['text'] == os.path.basename(filepath):
                widget.destroy()
                break
        self.update_counter()
        if self.preview_filepath == filepath:
            self.clear_preview()

    def change_image(self, filepath):
        new_image = filedialog.askopenfilename(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp")])
        if new_image and new_image != filepath:
            idx = self.image_files.index(filepath)
            self.image_files[idx] = new_image
            for widget in self.scrollable_frame.winfo_children():
                lbl = widget.winfo_children()[1]
                if lbl['text'] == os.path.basename(filepath):
                    widget.destroy()
                    self.add_image_to_list(new_image)
                    break
            if self.preview_filepath == filepath:
                self.show_preview(new_image)

    def remove_all(self):
        count = len(self.image_files)
        self.image_files.clear()
        self.thumbnails.clear()
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.update_counter()
        self.clear_preview()
        messagebox.showinfo("All Removed", f"Removed {count} image(s).")

    def update_counter(self):
        self.counter_label.config(text=f"{len(self.image_files)} Images")

    def select_save_folder(self):
        chosen = filedialog.askdirectory(initialdir=self.save_path)
        if chosen:
            self.save_path = chosen
            self.status_label.config(text=f"Save folder set to {self.save_path}")
        else:
            self.status_label.config(text="Folder selection cancelled.")

    def start_processing(self):
        if not self.save_path or not self.image_files:
            messagebox.showerror("Error", "Save folder or images not selected!")
            return
        self.stop_processing = False
        messagebox.showinfo("Processing", f"Starting to process {len(self.image_files)} image(s).")
        self.processing_thread = threading.Thread(target=self.process_images, daemon=True)
        self.processing_thread.start()

    def process_images(self):
        os.makedirs(self.save_path, exist_ok=True)
        self.progress['maximum'] = len(self.image_files)
        self.processed_files.clear()
        for i, filepath in enumerate(self.image_files):
            if self.stop_processing:
                self.status_label.config(text="Processing Stopped")
                return
            self.status_label.config(text=f"Processing image {i+1} of {len(self.image_files)}")
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
        messagebox.showinfo("Done", "All images have been processed.")
        self.open_save_folder()

    def end_processing(self):
        if self.processing_thread and self.processing_thread.is_alive():
            self.stop_processing = True
            messagebox.showinfo("Stopped", "Processing has been stopped.")

    def open_save_folder(self):
        if os.name == 'nt':
            os.startfile(self.save_path)
        elif os.name == 'posix':
            import sys
            subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', self.save_path])

    def smart_crop_images(self, width_ratio, height_ratio):
        if not self.save_path or not self.image_files:
            messagebox.showerror("Error", "Save folder or images not selected!")
            return
        self.stop_processing = False
        messagebox.showinfo("Smart Crop", f"Starting Smart Crop for {len(self.image_files)} image(s).")
        self.processing_thread = threading.Thread(
            target=self._smart_crop_thread, 
            args=(width_ratio, height_ratio), 
            daemon=True
        )
        self.processing_thread.start()

    def smart_crop_custom(self):
        ratio_str = simpledialog.askstring("Custom Crop Ratio", "Enter ratio (e.g., 4:3):")
        if ratio_str:
            try:
                w, h = map(int, ratio_str.split(':'))
                if w > 0 and h > 0:
                    self.smart_crop_images(w, h)
            except ValueError:
                messagebox.showerror("Error", "Invalid ratio format!")

    def _smart_crop_thread(self, width_ratio, height_ratio):
        os.makedirs(self.save_path, exist_ok=True)
        self.progress['maximum'] = len(self.image_files)
        self.processed_files.clear()
        for i, filepath in enumerate(self.image_files):
            if self.stop_processing:
                self.status_label.config(text="Cropping Stopped")
                return
            self.status_label.config(text=f"Smart Cropping {i+1} of {len(self.image_files)}")
            try:
                img = Image.open(filepath).convert("RGBA")
                width, height = img.size
                small_img = img.resize((int(width * 0.25), int(height * 0.25)), Image.Resampling.BILINEAR)
                small_array = np.array(small_img.convert("RGB"))
                face_locations = face_recognition.face_locations(small_array, model="hog")
                if face_locations:
                    top, right, bottom, left = [x * 4 for x in face_locations[0]]
                else:
                    mask = remove(img, only_mask=True)
                    coords = np.where(np.array(mask) > 0)
                    if len(coords[0]) == 0:
                        raise ValueError("No subject detected!")
                    top, bottom = coords[0].min(), coords[0].max()
                    left, right = coords[1].min(), coords[1].max()
                face_width = right - left
                face_height = bottom - top
                center_x, center_y = (left + right) // 2, (top + bottom) // 2
                aspect_ratio = width_ratio / height_ratio
                if face_width / face_height > aspect_ratio:
                    crop_height = min(face_height * 2, height)
                    crop_width = int(crop_height * aspect_ratio)
                else:
                    crop_width = min(face_width * 2, width)
                    crop_height = int(crop_width / aspect_ratio)
                crop_left = max(0, center_x - crop_width // 2)
                crop_right = min(width, crop_left + crop_width)
                crop_top = max(0, center_y - crop_height // 2)
                crop_bottom = min(height, crop_top + crop_height)
                if crop_right > width:
                    crop_left = width - crop_width
                if crop_bottom > height:
                    crop_top = height - crop_height
                if crop_left < 0:
                    crop_left = 0
                if crop_top < 0:
                    crop_top = 0
                cropped_img = img.crop((crop_left, crop_top, crop_right, crop_bottom))
                filename = os.path.splitext(os.path.basename(filepath))[0] + f"_crop_{width_ratio}x{height_ratio}.png"
                output_path = os.path.join(self.save_path, filename)
                cropped_img.save(output_path, format="PNG")
                self.processed_files.append(output_path)
                self.progress['value'] = i + 1
                self.root.update_idletasks()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to crop {os.path.basename(filepath)}: {str(e)}")
        self.status_label.config(text="Smart Cropping Completed!")
        messagebox.showinfo("Smart Crop Done", "All images have been smart-cropped.")
        self.open_save_folder()

    def fast_crop_images(self, width, height):
        if not self.save_path or not self.image_files:
            messagebox.showerror("Error", "Save folder or images not selected!")
            return
        self.stop_processing = False
        messagebox.showinfo("Fast Crop", f"Starting Fast Crop for {len(self.image_files)} image(s).")
        self.processing_thread = threading.Thread(
            target=self._fast_crop_thread, args=(width, height), daemon=True
        )
        self.processing_thread.start()

    def fast_crop_custom(self):
        size_str = simpledialog.askstring("Custom Crop Size", "Enter size (e.g., 200x300):")
        if size_str:
            try:
                w, h = map(int, size_str.split('x'))
                if w > 0 and h > 0:
                    self.fast_crop_images(w, h)
            except ValueError:
                messagebox.showerror("Error", "Invalid size format! Use 'widthxheight' (e.g., 200x300)")

    def _fast_crop_thread(self, width, height):
        os.makedirs(self.save_path, exist_ok=True)
        self.progress['maximum'] = len(self.image_files)
        self.processed_files.clear()
        for i, filepath in enumerate(self.image_files):
            if self.stop_processing:
                self.status_label.config(text="Cropping Stopped")
                return
            self.status_label.config(text=f"Fast Cropping {i+1} of {len(self.image_files)}")
            try:
                img = Image.open(filepath)
                img_width, img_height = img.size
                left = (img_width - width) // 2
                top = (img_height - height) // 2
                right = left + width
                bottom = top + height
                left = max(0, left)
                top = max(0, top)
                right = min(img_width, right)
                bottom = min(img_height, bottom)
                cropped_img = img.crop((left, top, right, bottom))
                filename = os.path.splitext(os.path.basename(filepath))[0] + f"_fastcrop_{width}x{height}.png"
                output_path = os.path.join(self.save_path, filename)
                cropped_img.save(output_path, format="PNG")
                self.processed_files.append(output_path)
                self.progress['value'] = i + 1
                self.root.update_idletasks()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to fast crop {os.path.basename(filepath)}: {str(e)}")
        self.status_label.config(text="Fast Cropping Completed!")
        messagebox.showinfo("Fast Crop Done", "All images have been fast-cropped.")
        self.open_save_folder()

    def resize_all(self):
        size_str = simpledialog.askstring("Resize All", "Enter new size (e.g., 800x600):")
        if size_str:
            try:
                w, h = map(int, size_str.split('x'))
                if w > 0 and h > 0:
                    self._resize_all_thread(w, h)
            except ValueError:
                messagebox.showerror("Error", "Invalid size format! Use 'widthxheight' (e.g., 800x600)")

    def _resize_all_thread(self, width, height):
        os.makedirs(self.save_path, exist_ok=True)
        self.progress['maximum'] = len(self.image_files)
        self.processed_files.clear()
        self.status_label.config(text="Resizing...")
        for i, filepath in enumerate(self.image_files):
            if self.stop_processing:
                self.status_label.config(text="Resizing Stopped")
                return
            self.status_label.config(text=f"Resizing {i+1} of {len(self.image_files)}")
            try:
                img = Image.open(filepath)
                resized_img = img.resize((width, height), Image.Resampling.LANCZOS)
                filename = os.path.splitext(os.path.basename(filepath))[0] + f"_resized_{width}x{height}.png"
                output_path = os.path.join(self.save_path, filename)
                resized_img.save(output_path, format="PNG")
                self.processed_files.append(output_path)
                self.progress['value'] = i + 1
                self.root.update_idletasks()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to resize {os.path.basename(filepath)}: {str(e)}")
        self.status_label.config(text="Resizing Completed!")
        messagebox.showinfo("Resize Done", "All images have been resized.")
        self.open_save_folder()

    def convert_to_jpg(self):
        if not self.save_path or not self.image_files:
            messagebox.showerror("Error", "Save folder or images not selected!")
            return
        color = colorchooser.askcolor(title="Select Background Color for JPG Conversion", initialcolor="#FFFFFF")
        if color[1] is None:
            return
        hex_color = color[1]
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        background_color = (r, g, b)
        self.stop_processing = False
        messagebox.showinfo("JPG Conversion", f"Starting JPG Conversion for {len(self.image_files)} image(s).")
        self.processing_thread = threading.Thread(
            target=self._convert_to_jpg_thread, 
            args=(background_color,), 
            daemon=True
        )
        self.processing_thread.start()

    def _convert_to_jpg_thread(self, background_color):
        os.makedirs(self.save_path, exist_ok=True)
        self.progress['maximum'] = len(self.image_files)
        self.processed_files.clear()
        for i, filepath in enumerate(self.image_files):
            if self.stop_processing:
                self.status_label.config(text="Conversion Stopped")
                return
            self.status_label.config(text=f"Converting {i+1} of {len(self.image_files)}")
            try:
                img = Image.open(filepath)
                if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                    background = Image.new('RGB', img.size, background_color)
                    if img.mode != 'RGBA':
                        img = img.convert('RGBA')
                    background.paste(img, (0, 0), img.split()[3])
                    img = background
                else:
                    img = img.convert("RGB")
                filename = os.path.splitext(os.path.basename(filepath))[0] + "_converted.jpg"
                output_path = os.path.join(self.save_path, filename)
                img.save(output_path, format="JPEG", quality=95)
                self.processed_files.append(output_path)
                self.progress['value'] = i + 1
                self.root.update_idletasks()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to convert {os.path.basename(filepath)}: {str(e)}")
        self.status_label.config(text="Conversion Completed!")
        messagebox.showinfo("Conversion Done", "All images have been converted to JPG.")
        self.open_save_folder()

    def show_processed_files(self):
        if not self.processed_files:
            messagebox.showinfo("Info", "No processed files yet.")
            return
        processed_window = tk.Toplevel(self.root)
        processed_window.title("Processed Files")
        processed_window.geometry("800x600")
        if os.path.exists(self.icon_path):
            processed_window.iconphoto(True, tk.PhotoImage(file=self.icon_path))
        canvas = tk.Canvas(processed_window, bg="white", highlightthickness=0)
        scrollbar = ttk.Scrollbar(processed_window, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")
        ttk.Button(processed_window, text="Delete All",
                   command=lambda: self.delete_all_processed(scrollable_frame),
                   style="Cool.TButton").pack(side='bottom', pady=5)
        for filepath in self.processed_files:
            frame = ttk.Frame(scrollable_frame)
            frame.pack(fill='x', pady=2)
            frame.columnconfigure(1, weight=1)
            try:
                img = Image.open(filepath)
                img.thumbnail((50, 50))
                thumbnail = ImageTk.PhotoImage(img)
                self.processed_thumbnails.append(thumbnail)
                ttk.Label(frame, image=thumbnail).grid(row=0, column=0, padx=5)
            except Exception:
                ttk.Label(frame, text="No Preview").grid(row=0, column=0, padx=5)
            label = ttk.Label(frame, text=os.path.basename(filepath))
            label.grid(row=0, column=1, sticky='ew', padx=5)
            ttk.Button(
                frame,
                text="View",
                image=self.view_icon,
                compound="left",
                command=lambda f=filepath: self.view_processed_file(f),
                style="Cool.TButton"
            ).grid(row=0, column=2, padx=5)
            ttk.Button(
                frame,
                text="Delete",
                image=self.delete_icon,
                compound="left",
                command=lambda f=filepath: self.delete_processed_file(f, frame),
                style="Cool.TButton"
            ).grid(row=0, column=3, padx=5)
            for widget in [frame, label]:
                widget.bind("<Button-1>", lambda e, f=filepath: self.show_preview(f))
        canvas.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

    def view_processed_file(self, filepath):
        if not os.path.exists(filepath):
            messagebox.showerror("Error", f"File {os.path.basename(filepath)} does not exist!")
            return
        try:
            view_window = tk.Toplevel(self.root)
            view_window.title(os.path.basename(filepath))
            view_window.geometry("600x500")
            if os.path.exists(self.icon_path):
                view_window.iconphoto(True, tk.PhotoImage(file=self.icon_path))
            canvas = tk.Canvas(view_window, bg="white", highlightthickness=0)
            h_scroll = ttk.Scrollbar(view_window, orient="horizontal", command=canvas.xview)
            v_scroll = ttk.Scrollbar(view_window, orient="vertical", command=canvas.yview)
            canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
            canvas.pack(side="top", fill="both", expand=True)
            h_scroll.pack(side="bottom", fill="x")
            v_scroll.pack(side="right", fill="y")
            label = ttk.Label(canvas)
            label_window_id = canvas.create_window((0, 0), window=label, anchor="center")
            img = Image.open(filepath)
            max_size = 400
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            base_size = max(img.size)
            zoom_factor = 1.0
            def update_image():
                nonlocal zoom_factor
                new_size = int(base_size * zoom_factor)
                w, h = img.size
                ratio = w / h
                if w > h:
                    new_w = new_size
                    new_h = int(new_size / ratio)
                else:
                    new_h = new_size
                    new_w = int(new_size * ratio)
                resized_img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(resized_img)
                label.config(image=photo)
                label.image = photo
                canvas.configure(scrollregion=(0, 0, new_w, new_h))
                canvas.coords(label_window_id, new_w // 2, new_h // 2)
            def zoom_in():
                nonlocal zoom_factor
                zoom_factor = min(zoom_factor * 1.1, 5.0)
                update_image()
            def zoom_out():
                nonlocal zoom_factor
                zoom_factor = max(zoom_factor / 1.1, 0.2)
                update_image()
            zoom_frame = ttk.Frame(view_window)
            zoom_frame.pack(pady=5)
            ttk.Button(zoom_frame, text="+", command=zoom_in, style="Cool.TButton").pack(side='left', padx=5)
            ttk.Button(zoom_frame, text="-", command=zoom_out, style="Cool.TButton").pack(side='left', padx=5)
            def on_mousewheel(e):
                if (e.state & 0x0004) != 0:
                    if e.delta > 0:
                        zoom_in()
                    else:
                        zoom_out()
                else:
                    canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
            canvas.bind("<MouseWheel>", on_mousewheel)
            view_window.bind("<Control-plus>", lambda e: zoom_in())
            view_window.bind("<Control-minus>", lambda e: zoom_out())
            update_image()
            def on_closing():
                canvas.delete("all")
                view_window.destroy()
            view_window.protocol("WM_DELETE_WINDOW", on_closing)
        except Exception as e:
            messagebox.showerror("Error", f"Could not view {os.path.basename(filepath)}: {str(e)}")

    def delete_processed_file(self, filepath, frame):
        if filepath in self.processed_files:
            self.processed_files.remove(filepath)
            frame.destroy()
            if os.path.exists(filepath):
                os.remove(filepath)

    def delete_all_processed(self, scrollable_frame):
        count = len(self.processed_files)
        for fp in self.processed_files[:]:
            if os.path.exists(fp):
                os.remove(fp)
        self.processed_files.clear()
        self.processed_thumbnails.clear()
        for widget in scrollable_frame.winfo_children():
            widget.destroy()
        scrollable_frame.winfo_toplevel().destroy()
        messagebox.showinfo("Deleted All", f"All {count} processed file(s) have been deleted.")

if __name__ == "__main__":
    root = ThemedTk(theme="arc")
    app = ImageProcessorApp(root)
    root.mainloop()
