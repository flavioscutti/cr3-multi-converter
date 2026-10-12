# -*- coding: utf-8 -*-

"""
Canon CR3 Multi Converter
A graphical batch conversion tool for Canon .CR3 files on Raspberry Pi.
Author: Flavio Scutti
"""

import os
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox

class RoundedButton(tk.Canvas):
    """Custom button with rounded corners (radius=4px) and full-width toggle effect matching the app style"""
    def __init__(self, parent, text, command, font=("Inter", 26, "bold"), padx=15, pady=14, bg_off="#0d1117", fg_off="#ffffff", bg_on="#ffffff", fg_on="#0d1117"):
        super().__init__(parent, bg="#0d1117", highlightthickness=0, bd=0)
        self.command = command
        self.text = text
        self.font = font
        self.padx = padx
        self.pady = pady
        self.bg_off = bg_off
        self.fg_off = fg_off
        self.bg_on = bg_on
        self.fg_on = fg_on
        self.is_selected = False

        # Calculate height based on font
        self.temp_txt = self.create_text(0, 0, text="Ay", font=font)
        bbox = self.bbox(self.temp_txt)
        self.delete(self.temp_txt)
        self.text_height = bbox[3] - bbox[1]
        self.height = self.text_height + (pady * 2)
        
        # Initial safe width
        self.width = 980
        self.configure(width=self.width, height=self.height)
        
        self.bind("<Configure>", self._on_configure)
        self.bind("<Button-1>", self._on_click)

    def _on_configure(self, event):
        if event.width > 1:
            self.width = event.width
            self.draw(self.is_selected)

    def draw(self, selected):
        self.is_selected = selected
        self.delete("all")

        bg_color = self.bg_on if selected else self.bg_off
        fg_color = self.fg_on if selected else self.fg_off
        border_color = "#30363d" if not selected else "#ffffff"

        # Draw rounded rectangle (radius = 4px)
        self.create_rounded_rect(2, 2, self.width - 2, self.height - 2, radius=4, fill=bg_color, outline=border_color, width=1)

        # Left-aligned text with padding
        self.create_text(self.padx, self.height / 2, text=self.text, font=self.font, fill=fg_color, anchor="w")

    def create_rounded_rect(self, x1, y1, x2, y2, radius=4, **kwargs):
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1
        ]
        return self.create_polygon(points, **kwargs, smooth=True)

    def _on_click(self, event):
        if self.command:
            self.command()

class AutoHideScrollbar(tk.Scrollbar):
    """Overlay-style auto-hiding scrollbar (Raspberry Pi OS / GTK style)."""
    def __init__(self, parent, target, hide_delay=1000, **kwargs):
        super().__init__(parent, orient="vertical", **kwargs)
        self.target = target
        self.hide_delay = hide_delay
        self._after_id = None
        self._visible = False
        self._hover = False
        self._needed = False

        self.configure(command=target.yview)
        target.configure(yscrollcommand=self.set)

        # Text area events: show the scrollbar when needed
        for seq in ("<Motion>", "<MouseWheel>", "<Button-4>", "<Button-5>", "<KeyPress>"):
            target.bind(seq, self._on_activity, add="+")

        # Scrollbar events: stay visible while hovering over it
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def set(self, lo, hi):
        super().set(lo, hi)
        self._needed = not (float(lo) <= 0.0 and float(hi) >= 1.0)
        if self._needed:
            self._show()
        else:
            self._hide()

    def _on_activity(self, event=None):
        if self._needed:
            self._show()

    def _on_enter(self, event=None):
        self._hover = True
        self._cancel_timer()

    def _on_leave(self, event=None):
        self._hover = False
        self._schedule_hide()

    def _show(self):
        if not self._visible:
            self.place(relx=1.0, rely=0.0, relheight=1.0, anchor="ne")
            self.tkraise()
            self._visible = True
        self._schedule_hide()

    def _hide(self):
        self._cancel_timer()
        if self._visible:
            self.place_forget()
            self._visible = False

    def _schedule_hide(self):
        self._cancel_timer()
        if not self._hover:
            self._after_id = self.after(self.hide_delay, self._hide)

    def _cancel_timer(self):
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None

class FileSelectorDialog(tk.Toplevel):
    def __init__(self, parent, initial_dir):
        super().__init__(parent)
        self.title("Select .CR3 Files")
        self.geometry("1024x768")
        self.transient(parent)
        self.grab_set()
        
        self.configure(bg="#0d1117")
        
        self.selected_files = []
        self.current_dir = initial_dir if (initial_dir and os.path.exists(initial_dir)) else os.path.expanduser("~")
        self.is_closing = False
        
        main_frame = tk.Frame(self, bg="#0d1117", padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.lbl_path = tk.Label(main_frame, text="", font=("Inter", 22, "bold"), bg="#0d1117", fg="#ffffff", anchor="w")
        self.lbl_path.pack(fill=tk.X, pady=8)
        
        btn_up = tk.Button(main_frame, text="⬆ Parent Folder (← Left Arrow)", command=self.go_parent_dir,
                           bg="#21262d", fg="#ffffff", font=("Inter", 22, "bold"), bd=1, relief="solid", highlightthickness=0, padx=15, pady=15)
        btn_up.pack(anchor=tk.W, pady=8)
        
        list_frame = tk.Frame(main_frame, bg="#161b22", bd=1, relief="solid")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=8)
        
        self.listbox = tk.Listbox(list_frame, selectmode=tk.EXTENDED, font=("Inter", 26),
                                  bg="#161b22", fg="#ffffff", selectbackground="#30363d", selectforeground="#ffffff", bd=0, highlightthickness=0)
        
        # Scrollbar with track and elements fully integrated into the #161b22 background
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview, width=28,
                                 bg="#161b22", troughcolor="#161b22", activebackground="#30363d", bd=0, highlightthickness=0)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.listbox.bind("<Double-1>", self.on_item_action)
        self.listbox.bind("<Return>", self.on_return_key)
        self.listbox.bind("<Right>", self.on_right_arrow)
        self.listbox.bind("<Left>", lambda e: self.go_parent_dir())
        self.listbox.bind("<Escape>", lambda e: self.safe_destroy())
        
        btn_frame = tk.Frame(main_frame, bg="#0d1117")
        btn_frame.pack(fill=tk.X, pady=12)
        
        btn_confirm = tk.Button(btn_frame, text="Confirm Selection", command=self.confirm_selection,
                                bg="#ffffff", fg="#0d1117", font=("Inter", 22, "bold"), bd=1, relief="solid", highlightthickness=0, padx=20, pady=15)
        btn_confirm.pack(side=tk.LEFT, padx=5)
        
        btn_cancel = tk.Button(btn_frame, text="Cancel (Esc)", command=self.safe_destroy,
                               bg="#21262d", fg="#ffffff", font=("Inter", 22, "bold"), bd=1, relief="solid", highlightthickness=0, padx=20, pady=15)
        btn_cancel.pack(side=tk.RIGHT, padx=5)
        
        self.load_directory(self.current_dir)
        self.listbox.focus_set()

    def load_directory(self, path):
        try:
            if os.path.exists(path):
                self.current_dir = path
                self.lbl_path.config(text=f"Path: {path}")
                self.listbox.delete(0, tk.END)
                items = sorted(os.listdir(path), key=lambda x: (not os.path.isdir(os.path.join(path, x)), x.lower()))
                for item in items:
                    full_path = os.path.join(path, item)
                    if os.path.isdir(full_path):
                        self.listbox.insert(tk.END, f"[DIR]  {item}")
                    elif item.lower().endswith(".cr3"):
                        self.listbox.insert(tk.END, f"[CR3]  {item}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def go_parent_dir(self):
        if self.is_closing: return
        parent = os.path.dirname(self.current_dir)
        if parent and parent != self.current_dir: 
            self.load_directory(parent)

    def get_current_text(self):
        sel = self.listbox.curselection()
        if sel:
            return self.listbox.get(sel[0])
        try:
            active_idx = self.listbox.index(tk.ACTIVE)
            return self.listbox.get(active_idx)
        except Exception:
            return None

    def on_item_action(self, event):
        if self.is_closing: return "break"
        sel = self.listbox.curselection()
        if len(sel) > 1:
            self.confirm_selection()
            return "break"
            
        text = self.get_current_text()
        if not text: return "break"
        if text.startswith("[DIR]"):
            folder_name = text.split("]  ")[1] if "]  " in text else text[6:].strip()
            self.load_directory(os.path.join(self.current_dir, folder_name))
        elif text.startswith("[CR3]"):
            self.confirm_selection()
        return "break"

    def on_return_key(self, event):
        if self.is_closing: return "break"
        return self.on_item_action(event)

    def on_right_arrow(self, event):
        if self.is_closing: return "break"
        text = self.get_current_text()
        if not text: return
        if text.startswith("[DIR]"):
            folder_name = text.split("]  ")[1] if "]  " in text else text[6:].strip()
            self.load_directory(os.path.join(self.current_dir, folder_name))

    def confirm_selection(self):
        if self.is_closing: return
        sel = self.listbox.curselection()
        chosen = []
        for i in sel:
            text = self.listbox.get(i)
            if text.startswith("[CR3]"):
                file_name = text.split("]  ")[1] if "]  " in text else text[6:].strip()
                chosen.append(os.path.join(self.current_dir, file_name))
        
        if not chosen:
            text = self.get_current_text()
            if text and text.startswith("[CR3]"):
                file_name = text.split("]  ")[1] if "]  " in text else text[6:].strip()
                chosen.append(os.path.join(self.current_dir, file_name))
                
        if chosen: 
            self.is_closing = True
            self.selected_files = chosen
            self.after(50, self._finalize_destroy)
        else: 
            messagebox.showwarning("Warning", "Please select at least one .CR3 file.")

    def safe_destroy(self):
        if self.is_closing: return
        self.is_closing = True
        self.selected_files = []
        self.after(50, self._finalize_destroy)

    def _finalize_destroy(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

class CR3ToDNGApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Canon R50V Multiple Converter")
        self.root.geometry("1024x768")
        self.root.minsize(800, 680)
        self.root.resizable(True, True)
        self.root.configure(bg="#0d1117")

        self.files_to_convert = []
        self.last_dir = os.path.expanduser("~")

        main_frame = tk.Frame(root, bg="#0d1117", padx=15, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        lbl_title = tk.Label(main_frame, text="CANON R50V MULTIPLE CONVERTER", font=("Inter", 22, "bold"), bg="#0d1117", fg="#ffffff")
        lbl_title.pack(pady=4)

        self.btn_select = tk.Button(main_frame, text="1. Select .CR3 Files", command=self.select_files,
                                    bg="#21262d", fg="#ffffff", font=("Inter", 24, "bold"), bd=1, relief="solid", highlightthickness=0, padx=15, pady=14)
        self.btn_select.pack(fill=tk.X, pady=6)

        self.lbl_status = tk.Label(main_frame, text="No files selected", font=("Inter", 20, "bold"), bg="#0d1117", fg="#ffffff")
        self.lbl_status.pack(pady=4)

        options_container = tk.Frame(main_frame, bg="#0d1117")
        options_container.pack(fill=tk.X, pady=6)

        self.var_tiff = tk.BooleanVar(value=True)        
        self.var_dng_16 = tk.BooleanVar(value=False)  

        self.btn_tiff = RoundedButton(options_container, text="16-bit TIFF", command=lambda: self.toggle_option('tiff'), font=("Inter", 24, "bold"), padx=15, pady=14)
        self.btn_tiff.pack(fill=tk.X, pady=4)

        self.btn_dng = RoundedButton(options_container, text="DNG Version 1.6", command=lambda: self.toggle_option('dng'), font=("Inter", 24, "bold"), padx=15, pady=14)
        self.btn_dng.pack(fill=tk.X, pady=4)

        self.update_toggle_ui()

        self.btn_convert = tk.Button(main_frame, text="2. Start Conversion", command=self.start_conversion, state=tk.DISABLED,
                                     bg="#ffffff", fg="#0d1117", font=("Inter", 24, "bold"), bd=1, relief="solid", highlightthickness=0, padx=15, pady=14)
        self.btn_convert.pack(fill=tk.X, pady=6)

        # Log area with auto-hiding scrollbar superimposed over the text
        log_container = tk.Frame(main_frame, bg="#161b22", bd=1, relief="solid")
        log_container.pack(fill=tk.BOTH, expand=True, pady=6)

        self.txt_log = tk.Text(log_container, font=("Inter", 13), bg="#161b22", fg="#e6edf3", bd=0, highlightthickness=0, state="disabled")
        self.txt_log.pack(fill=tk.BOTH, expand=True)

        # Auto-hiding scrollbar superimposed over the text
        self.log_scroll = AutoHideScrollbar(log_container, self.txt_log, hide_delay=1000, width=14,
                                            bg="#30363d", troughcolor="#161b22", activebackground="#484f58",
                                            bd=0, highlightthickness=0)

    def toggle_option(self, opt):
        if opt == 'tiff':
            self.var_tiff.set(not self.var_tiff.get())
        elif opt == 'dng':
            self.var_dng_16.set(not self.var_dng_16.get())
        self.update_toggle_ui()

    def update_toggle_ui(self):
        if self.var_tiff.get():
            self.btn_tiff.text = "✔ 16-bit TIFF"
            self.btn_tiff.draw(True)
        else:
            self.btn_tiff.text = "  16-bit TIFF"
            self.btn_tiff.draw(False)

        if self.var_dng_16.get():
            self.btn_dng.text = "✔ DNG Version 1.6"
            self.btn_dng.draw(True)
        else:
            self.btn_dng.text = "  DNG Version 1.6"
            self.btn_dng.draw(False)

    def log_safe(self, message):
        self.txt_log.config(state="normal")
        self.txt_log.insert(tk.END, message + "\n")
        self.txt_log.see(tk.END)
        self.txt_log.config(state="disabled")

    def status_safe(self, message):
        self.lbl_status.config(text=message)

    def select_files(self):
        dialog = FileSelectorDialog(self.root, self.last_dir)
        self.root.wait_window(dialog)
        
        if hasattr(dialog, 'current_dir') and os.path.exists(dialog.current_dir):
            self.last_dir = dialog.current_dir

        if dialog.selected_files:
            self.files_to_convert = dialog.selected_files
            self.lbl_status.config(text=f"{len(self.files_to_convert)} .CR3 files ready")
            self.btn_convert.config(state=tk.NORMAL)
            self.log_safe(f"Loaded {len(self.files_to_convert)} .CR3 files from: {self.last_dir}")

    def start_conversion(self):
        if not (self.var_tiff.get() or self.var_dng_16.get()):
            messagebox.showwarning("Warning", "Please select at least one output format to generate!")
            return

        self.btn_select.config(state=tk.DISABLED)
        self.btn_convert.config(state=tk.DISABLED)

        threading.Thread(target=self.convert_process_background, daemon=True).start()

    def convert_process_background(self):
        success_count = 0
        do_tiff = self.var_tiff.get()
        do_dng_16 = self.var_dng_16.get()
        total = len(self.files_to_convert)

        for idx, src_path in enumerate(self.files_to_convert, 1):
            dir_name, file_name = os.path.split(src_path)
            base_name = os.path.splitext(file_name)[0]
            
            status_text = f"Processing [{idx}/{total}]: {file_name}"
            self.root.after(0, lambda s=status_text: self.status_safe(s))
            self.root.after(0, lambda s=status_text: self.log_safe(f"\n{s}"))
            
            file_success = False

            try:
                if do_dng_16:
                    out_dng = os.path.join(dir_name, f"{base_name}.dng")
                    c = 1
                    while os.path.exists(out_dng):
                        out_dng = os.path.join(dir_name, f"{base_name}_{c}.dng")
                        c += 1
                    
                    res_dng = subprocess.run(["dnglab", "convert", src_path, out_dng], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
                    if res_dng.returncode == 0:
                        self.root.after(0, lambda f=os.path.basename(out_dng): self.log_safe(f"  [OK] DNG Version 1.6: {f}"))
                        file_success = True
                    else:
                        err = res_dng.stderr.strip()
                        self.root.after(0, lambda e=err: self.log_safe(f"  [ERROR] dnglab: {e}"))

                if do_tiff:
                    temp_dng = os.path.join(dir_name, f"{base_name}_temp_conversion.dng")
                    res_dnglab = subprocess.run(["dnglab", "convert", src_path, temp_dng], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
                    
                    if res_dnglab.returncode == 0:
                        out_tiff = os.path.join(dir_name, f"{base_name}.tiff")
                        c = 1
                        while os.path.exists(out_tiff):
                            out_tiff = os.path.join(dir_name, f"{base_name}_{c}.tiff")
                            c += 1

                        res_dcraw = subprocess.run(["dcraw", "-T", "-6", "-w", temp_dng], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
                        
                        if res_dcraw.returncode == 0:
                            generated_dcraw_tiff = os.path.splitext(temp_dng)[0] + ".tiff"
                            if generated_dcraw_tiff != out_tiff and os.path.exists(generated_dcraw_tiff):
                                if os.path.exists(out_tiff): os.remove(out_tiff)
                                os.rename(generated_dcraw_tiff, out_tiff)

                            subprocess.run(["exiftool", "-TagsFromFile", temp_dng, "-all:all", "-overwrite_original", out_tiff], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)

                            self.root.after(0, lambda f=os.path.basename(out_tiff): self.log_safe(f"  [OK] 16-bit TIFF: {f}"))
                            file_success = True
                        else:
                            err = res_dcraw.stderr.strip()
                            self.root.after(0, lambda e=err: self.log_safe(f"  [ERROR] dcraw TIFF: {e}"))

                        if os.path.exists(temp_dng):
                            os.remove(temp_dng)
                    else:
                        err = res_dnglab.stderr.strip()
                        self.root.after(0, lambda e=err: self.log_safe(f"  [ERROR] dnglab for TIFF: {e}"))

            except Exception as e:
                err_str = str(e)
                self.root.after(0, lambda err=err_str: self.log_safe(f"  [EXCEPTION]: {err}"))

            if file_success:
                success_count += 1

        finish_text = f"Completed! {success_count}/{total} files processed."
        self.root.after(0, lambda: self.status_safe(finish_text))
        self.root.after(0, lambda: self.log_safe(f"\nSession completed! Processed {success_count}/{total} files."))
        self.root.after(0, lambda: messagebox.showinfo("Completed", f"Multiple conversion completed ({success_count} files processed)."))
        self.root.after(0, lambda: self.btn_select.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.btn_convert.config(state=tk.NORMAL))

if __name__ == "__main__":
    root = tk.Tk()
    app = CR3ToDNGApp(root)
    root.mainloop()
