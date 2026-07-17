import tkinter as tk
from tkinter import filedialog, messagebox
import fitz                                                                                                                                                            #type:ignore
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
        
        # Bind left-click for table extraction
        self.canvas.bind("<Button-1>", self._on_canvas_click)

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