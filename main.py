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
        
        # Bind right-click for text editing
        self.canvas.bind("<Button-3>", self._on_right_click)

    def _on_mousewheel(self, event):
        if event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")

    def _on_canvas_click(self, event):
        if not self.doc:
            return

        # 1. Capture absolute canvas coordinates (accounting for scrollbars)
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)

        # 2. Apply coordinate transformation (Reverse the 1.5x zoom matrix)
        scale_factor = 1.5
        pdf_x = cx / scale_factor
        pdf_y = cy / scale_factor

        # 3. Trigger the extraction logic
        self.extract_column_data(pdf_x, pdf_y)

    def extract_column_data(self, x, y):
        # Guard to ensure the document exists
        if not self.doc:
            return
            
        page = self.doc[self.current_page]
        
        # Scan the page for tabular structures
        tables = page.find_tables()
        
        # Guard to prevent crashes if no tables are found
        if not tables:
            return
        
        for table in tables:
            # table.bbox contains (x0, y0, x1, y1) bounding box of the entire table
            tx0, ty0, tx1, ty1 = table.bbox
            
            # Check if the click falls inside this table's boundaries
            if tx0 <= x <= tx1 and ty0 <= y <= ty1:
                
                clicked_col_index = -1
                
                # Safely access the first row using PyMuPDF's .rows property
                if not hasattr(table, 'rows') or not table.rows:
                    continue
                    
                first_row_cells = table.rows[0].cells
                
                for col_idx, cell_bbox in enumerate(first_row_cells):
                    if cell_bbox is None: 
                        continue
                    
                    # Unpack the bounding box for this specific column cell
                    cx0, cy0, cx1, cy1 = cell_bbox
                    
                    # If the click's X coordinate is within this column's width
                    if cx0 <= x <= cx1:
                        clicked_col_index = col_idx
                        break
                
                # If a valid column was identified, extract the text
                if clicked_col_index != -1:
                    extracted_data = []
                    
                    table_data = table.extract()
                    
                    for row in table_data:
                        # Ensure the row has data for this column index
                        if row and len(row) > clicked_col_index:
                            cell_text = row[clicked_col_index]
                            
                            # Clean up newlines and ensure it is not an empty string
                            if cell_text is not None and str(cell_text).strip():
                                extracted_data.append(str(cell_text).replace('\n', ' ').strip())
                    
                    # Display the results in a message box
                    if extracted_data:
                        result_text = f"Extracted {len(extracted_data)} items from column {clicked_col_index + 1}:\n\n"
                        
                        # Join ALL items in the list without the [:15] slice
                        result_text += "\n".join(extracted_data) 
                        
                        messagebox.showinfo("Column Data Extracted", result_text)
                    return # Exit after processing the clicked table

    def _on_right_click(self, event):
        print(f"Right-click registered at Canvas X:{event.x}, Y:{event.y}")
        
        # Only allow editing on PDFs
        if not self.doc:
            print("Error: No document is currently open.")
            return
        if not self.doc.is_pdf:
            print("Error: This file is not a PDF. Editing is disabled.")
            return

        # 1. Capture absolute canvas coordinates
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)

        # 2. Reverse the 1.5x zoom matrix
        scale_factor = 1.5
        pdf_x = cx / scale_factor
        pdf_y = cy / scale_factor

        print(f"Translating to PDF coordinates - X:{pdf_x}, Y:{pdf_y}")

        # 3. Trigger the text replacement logic
        self.edit_pdf_text(pdf_x, pdf_y)

    def edit_pdf_text(self, x, y):
        page = self.doc[self.current_page]  #type:ignore
        words = page.get_text("words")
        
        word_found = False
        padding = 3 # Adds a 3-pixel invisible buffer around words to make clicking easier
        
        for w in words:
            # Unpack the word data
            x0, y0, x1, y1, text, block_no, line_no, word_no = w
            
            # Check if the right-click falls inside this word's padded boundaries
            if (x0 - padding) <= x <= (x1 + padding) and (y0 - padding) <= y <= (y1 + padding):#type:ignore
                print(f"Target locked! You clicked on the word: '{text}'")
                word_found = True
                
                # Prompt the user for the new text
                new_text = simpledialog.askstring("Edit Text", f"Replace '{text}' with:")
                
                if new_text is not None:
                    try:
                        # 1. Whiteout (redact) the original word completely
                        page.add_redact_annot((x0, y0, x1, y1))
                        page.apply_redactions()
                        
                        # 2. Insert the new text at the same baseline coordinates
                        page.insert_text((x0, y1 - 2), new_text, fontsize=11, color=(0, 0, 0))  #type:ignore
                        
                        # 3. Save changes directly to the original file
                        self.doc.saveIncr()  #type:ignore
                        print("Success: Original PDF file updated on the hard drive.")
                        
                        # 4. Refresh the canvas to render the edit
                        self.display_page()
                        
                    except Exception as e:
                        print(f"Critical Save Error: {e}")
                        messagebox.showerror("Save Error", f"Could not update the original file.\nError: {e}")
                
                return # Exit loop once the target word is processed
        
        if not word_found:
            print("Missed! The click did not hit a word bounding box.")

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