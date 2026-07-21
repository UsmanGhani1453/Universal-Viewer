import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import fitz                                                                                                                                                            
from PIL import Image, ImageTk                                                                                                                                                         #type:ignore
import zipfile
import xml.etree.ElementTree as ET
import subprocess
import tempfile
import os
import shutil

class UniversalViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Universal Document & Image Viewer")
        self.root.geometry("1000x900")

        self.doc = None
        self.current_page = 0
        self.current_filepath = ""
        self.original_filepath = "" 

        toolbar = tk.Frame(root, bg="#f0f0f0", bd=1, relief=tk.RAISED)
        toolbar.pack(side=tk.TOP, fill=tk.X, pady=2)

        tk.Button(toolbar, text="Open File", command=self.open_file).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="< Prev", command=self.prev_page).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="Next >", command=self.next_page).pack(side=tk.LEFT, padx=2)

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.display_page())
        
        tk.Label(toolbar, text="Search:").pack(side=tk.LEFT, padx=(20, 5))
        tk.Entry(toolbar, textvariable=self.search_var, width=15).pack(side=tk.LEFT, pady=5)
        
        tk.Button(toolbar, text="Find & Replace", command=self.find_and_replace).pack(side=tk.LEFT, padx=(5, 0))
        
        tk.Label(toolbar, text="| Tools:").pack(side=tk.LEFT, padx=(10, 5))
        
        self.active_tool = tk.StringVar(value="read")
        
        tk.Radiobutton(toolbar, text="Select/Read", variable=self.active_tool, value="read", indicatoron=0, width=10, bg="lightgray").pack(side=tk.LEFT, padx=2)                                                                                                                                     #type:ignore
        tk.Radiobutton(toolbar, text="Edit Text", variable=self.active_tool, value="edit", indicatoron=0, width=10, bg="lightgray").pack(side=tk.LEFT, padx=2)                                                                                                                                     #type:ignore
        
        tk.Label(toolbar, text="| Native:").pack(side=tk.LEFT, padx=(10, 5))
        tk.Button(toolbar, text="↻ Refresh Preview", command=self.refresh_document).pack(side=tk.LEFT, padx=2)

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
        self.canvas.bind("<Button-1>", self._on_master_click)

    def _on_mousewheel(self, event):
        if event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")

    def _on_master_click(self, event):
        """Routes a left-click based on which UI Tool Mode is active."""
        if not self.doc:
            return

        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)

        scale_factor = 1.5
        pdf_x = cx / scale_factor
        pdf_y = cy / scale_factor

        current_mode = self.active_tool.get()
        
        if current_mode == "read":
            self.extract_column_data(pdf_x, pdf_y)
        elif current_mode == "edit":
            self.edit_pdf_text(pdf_x, pdf_y)

    
    def refresh_document(self):
        """Reloads the document from the hard drive after native editing."""
        if not self.original_filepath:
            return
            
        print("Refreshing document preview from hard drive...")
        self.doc = None
        self.canvas.delete("all")
        self.open_file(path=self.original_filepath)

    def _save_document_logic(self):
        file_path = self.current_filepath 
        
        if self.doc.is_stream:                                                                                                                                     #type:ignore
            pdf_bytes = self.doc.tobytes()                                                                                                                                     #type:ignore
            self.doc.close()                                                                                                                                     #type:ignore
            with open(file_path, "wb") as f:
                f.write(pdf_bytes)
        else:
            try:
                self.doc.saveIncr()                                                                                                                                     #type:ignore
                self.doc.close()                                                                                                                                     #type:ignore
            except Exception as save_err:
                if "repaired file" in str(save_err).lower():
                    pdf_bytes = self.doc.tobytes()                                                                                                                                     #type:ignore 
                    self.doc.close()                                                                                                                                     #type:ignore 
                    with open(file_path, "wb") as f:
                        f.write(pdf_bytes)
                else:
                    raise save_err 
        
        self.doc = fitz.open(file_path)

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

    def native_xml_replace(self, filepath, search_term, replace_term):
        """Directly modifies the actual .odt or .docx file without PDF conversion."""
        temp_dir = tempfile.mkdtemp()
        temp_file_path = os.path.join(temp_dir, "temp_doc.zip")
        
        try:
            with zipfile.ZipFile(filepath, 'r') as zin:
                with zipfile.ZipFile(temp_file_path, 'w') as zout:
                    
                    for item in zin.infolist():
                        file_content = zin.read(item.filename)
                        
                        if item.filename in ['content.xml', 'word/document.xml']:
                            xml_str = file_content.decode('utf-8')
                            
                            xml_str = xml_str.replace(search_term, replace_term)
                            
                            zout.writestr(item, xml_str.encode('utf-8'))
                        else:
                            zout.writestr(item, file_content)
            
            shutil.move(temp_file_path, filepath)
            
        except Exception as e:
            raise Exception(f"Failed to modify native XML: {e}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

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
                word_found = True
                new_text = simpledialog.askstring("Edit Text", f"Replace '{text}' with:")
                
                if new_text is not None:
                    if not self.original_filepath.lower().endswith('.pdf'):
                        try:
                            self.native_xml_replace(self.original_filepath, text, new_text)
                            self.refresh_document() 
                            messagebox.showinfo("Success", f"Successfully updated the native file.")
                        except Exception as e:
                            messagebox.showerror("Error", f"Failed to natively edit file.\nError: {e}")
                        return
                    
                    try:
                        page.add_redact_annot((x0, y0, x1, y1))
                        page.apply_redactions()
                        page.insert_text((x0, y1 - 2), new_text, fontsize=11, color=(0, 0, 0))
                        
                        self._save_document_logic()
                        self.display_page()
                    except Exception as e:
                        messagebox.showerror("Save Error", f"Could not update the PDF.\nError: {e}")
                return 
        
        if not word_found:
            if not self.original_filepath.lower().endswith('.pdf'):
                messagebox.showinfo("Tool Restricted", "Adding text to empty space is only supported for native PDF files.")
                return

            new_text = simpledialog.askstring("Add Text", "Enter new text to insert here:")
            if new_text is not None and new_text.strip():
                try:
                    page.insert_text((x, y), new_text, fontsize=11, color=(0, 0, 0))
                    self._save_document_logic()
                    self.display_page()
                except Exception as e:
                    messagebox.showerror("Save Error", f"Could not insert text.\nError: {e}")

    def find_and_replace(self):
        if not self.original_filepath:
            messagebox.showwarning("Warning", "Please open a document first.")
            return
            
        search_term = simpledialog.askstring("Find", "Enter the word to find:")
        if not search_term:
            return 
            
        replace_term = simpledialog.askstring("Replace", f"Replace all instances of '{search_term}' with:")
        if replace_term is None:
            return 

        if not self.original_filepath.lower().endswith('.pdf'):
            try:
                self.native_xml_replace(self.original_filepath, search_term, replace_term)
                self.refresh_document() 
                messagebox.showinfo("Success", f"Successfully updated the native file: {os.path.basename(self.original_filepath)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to replace text natively.\nError: {e}")
            return

        total_replaced = 0
        for page_num in range(len(self.doc)):                                                             #type:ignore
            page = self.doc[page_num]                                           #type:ignore
            rects = page.search_for(search_term)
            
            if rects:
                for rect in rects:
                    page.add_redact_annot(rect)
                page.apply_redactions()
                
                for rect in rects:
                    page.insert_text((rect.x0, rect.y1 - 2), replace_term, fontsize=11, color=(0, 0, 0))
                    
                total_replaced += len(rects)
                
        if total_replaced == 0:
            messagebox.showinfo("Not Found", f"Could not find any instances of '{search_term}' in the document.")
            return
            
        try:
            self._save_document_logic()
            self.display_page()
            messagebox.showinfo("Success", f"Successfully replaced {total_replaced} instances of '{search_term}' across all pages.")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to replace text.\nError: {e}")

    def extract_odf_text(self, filepath):
        try:
            with zipfile.ZipFile(filepath, 'r') as zf:
                xml_content = zf.read('content.xml')
                
            tree = ET.fromstring(xml_content)
            
            if filepath.lower().endswith('.ods'):
                text_lines = []
                for row in tree.iter():
                    if row.tag.endswith('}table-row'):
                        row_data = []
                        for cell in row.iter():
                            if cell.tag.endswith('}table-cell'):
                                cell_text = "".join(cell.itertext()).strip()
                                row_data.append(cell_text)
                        if any(row_data):
                            formatted_row = " | ".join(item.ljust(15) for item in row_data)
                            text_lines.append(formatted_row)
                return "\n".join(text_lines)
            else:
                text_lines = []
                for elem in tree.iter():
                    if elem.tag.endswith('}p') or elem.tag.endswith('}h'):
                        line = "".join(elem.itertext())
                        if line.strip():
                            text_lines.append(line.strip())
                return "\n\n".join(text_lines)
                
        except Exception as e:
            raise Exception(f"Failed to extract text from LibreOffice file: {e}")

    def open_file(self, path=None):
        """Opens a file. Accepts a direct path argument for the refresh logic."""
        if not path:
            filetypes = [
                ("All Supported", "*.pdf *.png *.jpg *.jpeg *.txt *.epub *.xps *.cbz *.odt *.ods *.odp *.odg *.docx"),
                ("PDF Files", "*.pdf"),
                ("Images", "*.png *.jpg *.jpeg *.bmp *.tiff"),
                ("LibreOffice Files", "*.odt *.ods *.odp *.odg"),
                ("Word Documents", "*.docx"),
                ("Text Files", "*.txt"),
                ("All Files", "*.*")
            ]
            path = filedialog.askopenfilename(filetypes=filetypes)
        
        if path:
            self.original_filepath = path
            try:
                if path.lower().endswith(('.odt', '.ods', '.odp', '.odg')):
                    raw_text = self.extract_odf_text(path)
                    text_bytes = raw_text.encode('utf-8')
                    
                    temp_doc = fitz.open(stream=text_bytes, filetype="txt")
                    pdf_bytes = temp_doc.convert_to_pdf()
                    temp_doc.close()
                    
                    self.doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                    self.current_filepath = path.rsplit('.', 1)[0] + ".pdf"
                    
                else:
                    self.doc = fitz.open(path)
                    self.current_filepath = path
                    
                    if not self.doc.is_pdf:
                        pdf_bytes = self.doc.convert_to_pdf()
                        self.doc.close()
                        
                        self.doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                        self.current_filepath = path.rsplit('.', 1)[0] + ".pdf"
                
                self.current_page = 0
                self.root.title(f"Universal Viewer - {self.original_filepath}")
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