import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import fitz                                                                                                                                                            
from PIL import Image, ImageTk                                                                                                                                                         #type:ignore

class UniversalViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Universal Document & Image Viewer")
        self.root.geometry("800x900")

        self.doc = None
        self.current_page = 0

        toolbar = tk.Frame(root, bg="#f0f0f0", bd=1, relief=tk.RAISED)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        tk.Button(toolbar, text="Open File", command=self.open_file).pack(side=tk.LEFT)
        tk.Button(toolbar, text="< Prev", command=self.prev_page).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Next >", command=self.next_page).pack(side=tk.LEFT)

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.display_page())
        
        tk.Label(toolbar, text="Search:").pack(side=tk.LEFT, padx=(20, 5))
        tk.Entry(toolbar, textvariable=self.search_var, width=30).pack(side=tk.LEFT, pady=5)

        tk.Button(toolbar, text="Find & Replace", command=self.find_and_replace).pack(side=tk.LEFT, padx=(10, 0)) 

        display_frame = tk.Frame(root)
        display_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

        v_scroll = tk.Scrollbar(display_frame, orient=tk.VERTICAL)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        h_scroll = tk.Scrollbar(display_frame, orient=tk.HORIZONTAL)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        self.canvas = tk.Canvas(display_frame, bg="gray", 
                                yscrollcommand=v_scroll.set, 
                                xscrollcommand=h_scroll.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        v_scroll.config(command=self.canvas.yview)
        h_scroll.config(command=self.canvas.xview)

        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel) 
        self.canvas.bind_all("<Button-5>", self._on_mousewheel) 
        
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        
        self.canvas.bind("<Button-3>", self._on_right_click)

    def _on_mousewheel(self, event):
        if event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")

    def _on_canvas_click(self, event):
        if not self.doc:
            return

        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)

        scale_factor = 1.5
        pdf_x = cx / scale_factor
        pdf_y = cy / scale_factor

        self.extract_column_data(pdf_x, pdf_y)

    def extract_column_data(self, x, y):
        if not self.doc:
            return
            
        page = self.doc[self.current_page]
        
        tables = page.find_tables()
        
        if not tables:
            return
        
        for table in tables:
            tx0, ty0, tx1, ty1 = table.bbox
            
            if tx0 <= x <= tx1 and ty0 <= y <= ty1:
                
                clicked_col_index = -1
                
                if not hasattr(table, 'rows') or not table.rows:
                    continue
                    
                first_row_cells = table.rows[0].cells
                
                for col_idx, cell_bbox in enumerate(first_row_cells):
                    if cell_bbox is None: 
                        continue
                    
                    cx0, cy0, cx1, cy1 = cell_bbox
                    
                    if cx0 <= x <= cx1:
                        clicked_col_index = col_idx
                        break
                
                if clicked_col_index != -1:
                    extracted_data = []
                    
                    table_data = table.extract()
                    
                    for row in table_data:
                        if row and len(row) > clicked_col_index:
                            cell_text = row[clicked_col_index]
                            
                            if cell_text is not None and str(cell_text).strip():
                                extracted_data.append(str(cell_text).replace('\n', ' ').strip())
                    
                    if extracted_data:
                        result_text = f"Extracted {len(extracted_data)} items from column {clicked_col_index + 1}:\n\n"
                        
                        result_text += "\n".join(extracted_data) 
                        
                        messagebox.showinfo("Column Data Extracted", result_text)
                    return 

    def _on_right_click(self, event):
        print(f"Right-click registered at Canvas X:{event.x}, Y:{event.y}")
        
        if not self.doc:
            print("Error: No document is currently open.")
            return
        if not self.doc.is_pdf:
            print("Error: This file is not a PDF. Editing is disabled.")
            return

        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)

        scale_factor = 1.5
        pdf_x = cx / scale_factor
        pdf_y = cy / scale_factor

        print(f"Translating to PDF coordinates - X:{pdf_x}, Y:{pdf_y}")

        self.edit_pdf_text(pdf_x, pdf_y)

    def edit_pdf_text(self, x, y):
        if not self.doc:
            return
            
        page = self.doc[self.current_page]
        words = page.get_text("words")
        
        word_found = False
        padding = 3 
        
        for w in words:
            x0, y0, x1, y1, text, block_no, line_no, word_no = w
            
            x0, y0, x1, y1 = float(x0), float(y0), float(x1), float(y1)
            
            if (x0 - padding) <= x <= (x1 + padding) and (y0 - padding) <= y <= (y1 + padding):
                print(f"Target locked! You clicked on the word: '{text}'")
                word_found = True
                
                new_text = simpledialog.askstring("Edit Text", f"Replace '{text}' with:")
                
                if new_text is not None:
                    try:
                        page.add_redact_annot((x0, y0, x1, y1))
                        page.apply_redactions()
                        
                        page.insert_text((x0, y1 - 2), new_text, fontsize=11, color=(0, 0, 0))
                        
                        file_path = str(self.doc.name) 
                        
                        try:
                            self.doc.saveIncr()
                            print("Success: Incremental save completed.")
                            self.doc.close()
                        except Exception as save_err:
                            if "repaired file" in str(save_err).lower():
                                print("Repaired file detected. Performing a full save to memory...")
                                pdf_bytes = self.doc.tobytes() 
                                self.doc.close() 
                                
                                with open(file_path, "wb") as f:
                                    f.write(pdf_bytes)
                                print("Success: Full save completed and original file overwritten.")
                            else:
                                raise save_err
                        
                        self.doc = fitz.open(file_path)
                        
                        self.display_page()
                        
                    except Exception as e:
                        print(f"Critical Save Error: {e}")
                        messagebox.showerror("Save Error", f"Could not update the original file.\nError: {e}")
                
                return 
        
        if not word_found:
            print("Missed! The click did not hit a word bounding box.")

    def find_and_replace(self):
        # 1. Safety guards
        if not self.doc:
            messagebox.showwarning("Warning", "Please open a document first.")
            return
        if not self.doc.is_pdf:
            messagebox.showwarning("Warning", "Find and Replace is only supported for PDFs.")
            return
            
        # 2. Ask the user what to find and what to replace it with
        search_term = simpledialog.askstring("Find", "Enter the word to find:")
        if not search_term:
            return # User canceled
            
        replace_term = simpledialog.askstring("Replace", f"Replace all instances of '{search_term}' with:")
        if replace_term is None:
            return # User canceled
            
        page = self.doc[self.current_page]
        
        # 3. Find every instance of the search term on the current page
        # This returns a list of bounding box coordinates (fitz.Rect)
        rects = page.search_for(search_term)
        
        if not rects:
            messagebox.showinfo("Not Found", f"Could not find any instances of '{search_term}' on this page.")
            return
            
        try:
            # 4. Redact (erase) all found instances
            for rect in rects:
                page.add_redact_annot(rect)
            page.apply_redactions()
            
            # 5. Insert the new text at the same coordinates
            for rect in rects:
                # rect.x0 and rect.y1 represent the bottom-left baseline of the old text
                page.insert_text((rect.x0, rect.y1 - 2), replace_term, fontsize=11, color=(0, 0, 0))
                
            # 6. Handle saving for both standard and "repaired" PDFs
            file_path = str(self.doc.name) 
            
            try:
                self.doc.saveIncr()
                self.doc.close()
            except Exception as save_err:
                if "repaired file" in str(save_err).lower():
                    pdf_bytes = self.doc.tobytes() 
                    self.doc.close() 
                    
                    with open(file_path, "wb") as f:
                        f.write(pdf_bytes)
                else:
                    raise save_err 
            
            # 7. Reload to show the newly replaced text
            self.doc = fitz.open(file_path)
            self.display_page()
            
            # 8. Success confirmation
            messagebox.showinfo("Success", f"Successfully replaced {len(rects)} instances of '{search_term}'.")
            
        except Exception as e:
            print(f"Critical Find/Replace Error: {e}")
            messagebox.showerror("Error", f"Failed to replace text.\nError: {e}")
                    
    def open_file(self):
        filetypes = [
            ("All Supported", "*.pdf *.png *.jpg *.jpeg *.txt *.epub *.xps *.cbz"),
            ("PDF Files", "*.pdf"),
            ("Images", "*.png *.jpg *.jpeg *.bmp *.tiff"),
            ("Text Files", "*.txt"),
            ("All Files", "*.*")
        ]
        
        path = filedialog.askopenfilename(filetypes=filetypes)
        
        if path:
            try:
                self.doc = fitz.open(path)
                self.current_page = 0
                
                self.root.title(f"Universal Viewer - {path}")
                
                self.display_page()
            except Exception as e:
                messagebox.showerror("Unsupported File", f"Cannot open this file.\n\nError: {e}")

    def display_page(self):
        if not self.doc:
            return

        page = self.doc[self.current_page]

        try:
            for annot in page.annots():
                if annot.type[0] == 8:
                    page.delete_annot(annot)
        except Exception:
            pass 

        search_term = self.search_var.get()
        if search_term:
            try:
                for inst in page.search_for(search_term):
                    page.add_highlight_annot(inst)
            except Exception:
                pass

        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples) #type:ignore
        
        self.photo = ImageTk.PhotoImage(img)
        
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
        self.canvas.config(scrollregion=(0, 0, pix.width, pix.height))

    def prev_page(self):
        if self.doc and self.current_page > 0:
            self.current_page -= 1
            self.display_page()

    def next_page(self):
        if self.doc and self.current_page < len(self.doc) - 1:
            self.current_page += 1
            self.display_page()

if __name__ == "__main__":
    root = tk.Tk()
    app = UniversalViewer(root) 
    root.mainloop()