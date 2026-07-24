import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import fitz                                                                                                                                                            
from PIL import Image, ImageTk                                                                                                                                                         #type:ignore
import zipfile
import xml.etree.ElementTree as ET
import tempfile
import os
import shutil
import html
import re

class UniversalViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Universal Document & Image Viewer")
        self.root.geometry("1000x900")

        self.doc = None
        self.current_page = 0
        self.current_filepath = ""
        self.original_filepath = "" 
        self.clipboard_text = ""
        
        self.undo_stack = []
        self.redo_stack = []

        toolbar_top = tk.Frame(root, bg="#f0f0f0", bd=1, relief=tk.RAISED)
        toolbar_top.pack(side=tk.TOP, fill=tk.X, pady=1)

        tk.Button(toolbar_top, text="Open File", command=self.open_file).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar_top, text="< Prev", command=self.prev_page).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar_top, text="Next >", command=self.next_page).pack(side=tk.LEFT, padx=2)
        
        tk.Label(toolbar_top, text="| History:").pack(side=tk.LEFT, padx=(10, 5))
        tk.Button(toolbar_top, text="↩ Undo", command=self.undo, bg="#fff3cd").pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar_top, text="↪ Redo", command=self.redo, bg="#fff3cd").pack(side=tk.LEFT, padx=2)

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.display_page())
        
        tk.Label(toolbar_top, text="| Search:").pack(side=tk.LEFT, padx=(20, 5))
        tk.Entry(toolbar_top, textvariable=self.search_var, width=15).pack(side=tk.LEFT, pady=5)
        tk.Button(toolbar_top, text="Find & Replace", command=self.find_and_replace).pack(side=tk.LEFT, padx=(5, 0))
        
        toolbar_bottom = tk.Frame(root, bg="#f0f0f0", bd=1, relief=tk.RAISED)
        toolbar_bottom.pack(side=tk.TOP, fill=tk.X, pady=1)

        tk.Label(toolbar_bottom, text="| Tools:").pack(side=tk.LEFT, padx=(10, 5))
        
        self.active_tool = tk.StringVar(value="read")
        
        tk.Radiobutton(toolbar_bottom, text="Select/Read", variable=self.active_tool, value="read", indicatoron=0, width=10, bg="lightgray").pack(side=tk.LEFT, padx=2)
        tk.Radiobutton(toolbar_bottom, text="Edit Text", variable=self.active_tool, value="edit", indicatoron=0, width=10, bg="lightgray").pack(side=tk.LEFT, padx=2)
        tk.Radiobutton(toolbar_bottom, text="Write Text", variable=self.active_tool, value="write", indicatoron=0, width=10, bg="lightgray").pack(side=tk.LEFT, padx=2)
        tk.Radiobutton(toolbar_bottom, text="Paste Text", variable=self.active_tool, value="paste", indicatoron=0, width=10, bg="lightgray").pack(side=tk.LEFT, padx=2)        
        tk.Radiobutton(toolbar_bottom, text="Insert Table", variable=self.active_tool, value="table", indicatoron=0, width=10, bg="lightgray").pack(side=tk.LEFT, padx=2)

        tk.Label(toolbar_bottom, text="| Native:").pack(side=tk.LEFT, padx=(10, 5))
        tk.Button(toolbar_bottom, text="↻ Refresh Preview", command=self.refresh_document).pack(side=tk.LEFT, padx=2)

        tk.Label(toolbar_bottom, text="| Transfer:").pack(side=tk.LEFT, padx=(10, 5))
        tk.Button(toolbar_bottom, text="Copy -> Paste", command=self.transfer_custom_text, bg="#d1e7dd").pack(side=tk.LEFT, padx=2)

        self.status_var = tk.StringVar(value=" Ready | Please open a document.")
        status_bar = tk.Label(root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W, bg="#e8e8e8", font=("Arial", 9))
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

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
        
        self.root.bind("<Control-z>", self.undo)
        self.root.bind("<Control-y>", self.redo)
        self.root.bind("<Control-Z>", self.redo) 

    def _save_state(self):
        if not self.original_filepath: return
        try:
            if self.original_filepath.lower().endswith('.pdf'):
                if not self.doc: return
                self.undo_stack.append(('pdf', self.doc.tobytes()))
            else:
                with open(self.original_filepath, 'rb') as f:
                    self.undo_stack.append(('native', f.read()))
                    
            if len(self.undo_stack) > 15:
                self.undo_stack.pop(0)
            self.redo_stack.clear()
        except Exception as e:
            print(f"Failed to capture state: {e}")

    def undo(self, event=None):
        if isinstance(self.root.focus_get(), tk.Entry): return 
        if not self.undo_stack or not self.original_filepath: return
            
        try:
            if self.original_filepath.lower().endswith('.pdf'):
                self.redo_stack.append(('pdf', self.doc.tobytes()))
            else:
                with open(self.original_filepath, 'rb') as f:
                    self.redo_stack.append(('native', f.read()))
                    
            file_type, old_state = self.undo_stack.pop()
            
            if self.doc:
                self.doc.close()
                self.doc = None
                
            if file_type == 'pdf':
                with open(self.current_filepath, 'wb') as f: f.write(old_state)
            else:
                with open(self.original_filepath, 'wb') as f: f.write(old_state)
                    
            self.open_file(path=self.original_filepath, is_refresh=True)
            self.status_var.set(" Action Undone")
        except Exception as e:
            messagebox.showerror("Undo Error", f"Could not undo: {e}")

    def redo(self, event=None):
        if isinstance(self.root.focus_get(), tk.Entry): return 
        if not self.redo_stack or not self.original_filepath: return
            
        try:
            if self.original_filepath.lower().endswith('.pdf'):
                self.undo_stack.append(('pdf', self.doc.tobytes()))
            else:
                with open(self.original_filepath, 'rb') as f:
                    self.undo_stack.append(('native', f.read()))
                    
            file_type, new_state = self.redo_stack.pop()
            
            if self.doc:
                self.doc.close()
                self.doc = None
                
            if file_type == 'pdf':
                with open(self.current_filepath, 'wb') as f: f.write(new_state)
            else:
                with open(self.original_filepath, 'wb') as f: f.write(new_state)
                    
            self.open_file(path=self.original_filepath, is_refresh=True)
            self.status_var.set(" Action Redone")
        except Exception as e:
            messagebox.showerror("Redo Error", f"Could not redo: {e}")

    def _on_mousewheel(self, event):
        if event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")

    def _on_master_click(self, event):
        if not self.doc: return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        pdf_x = cx / 1.5
        pdf_y = cy / 1.5
        mode = self.active_tool.get()
        
        if mode == "read": self.extract_column_data(pdf_x, pdf_y)
        elif mode == "edit": self.edit_pdf_text(pdf_x, pdf_y)
        elif mode == "write": self.insert_new_text(pdf_x, pdf_y)
        elif mode == "paste": self.paste_text_on_canvas(pdf_x, pdf_y)
        elif mode == "table": self.insert_table(pdf_x, pdf_y)

    def refresh_document(self):
        if not self.original_filepath: return
        self.doc = None
        self.canvas.delete("all")
        self.open_file(path=self.original_filepath, is_refresh=True)

    def _save_document_logic(self):
        file_path = self.current_filepath 
        if self.doc.is_stream:
            pdf_bytes = self.doc.tobytes()
            self.doc.close()
            with open(file_path, "wb") as f: f.write(pdf_bytes)
        else:
            try:
                self.doc.saveIncr()
                self.doc.close()
            except Exception as save_err:
                if "repaired file" in str(save_err).lower():
                    pdf_bytes = self.doc.tobytes() 
                    self.doc.close() 
                    with open(file_path, "wb") as f: f.write(pdf_bytes)
                else: raise save_err 
        self.doc = fitz.open(file_path)

    def extract_column_data(self, x, y):
        if not self.doc: return
        page = self.doc[self.current_page]
        tables = page.find_tables()
        if not tables: return
        
        for table in tables:
            tx0, ty0, tx1, ty1 = table.bbox
            if tx0 <= x <= tx1 and ty0 <= y <= ty1:
                clicked_col_index = -1
                if not hasattr(table, 'rows') or not table.rows: continue
                for col_idx, cell_bbox in enumerate(table.rows[0].cells):
                    if cell_bbox and cell_bbox[0] <= x <= cell_bbox[2]:
                        clicked_col_index = col_idx
                        break
                
                if clicked_col_index != -1:
                    extracted_data = []
                    for row in table.extract():
                        if row and len(row) > clicked_col_index and row[clicked_col_index]:
                            extracted_data.append(str(row[clicked_col_index]).replace('\n', ' ').strip())
                    
                    if extracted_data:
                        messagebox.showinfo("Data Extracted", f"Extracted {len(extracted_data)} items:\n\n" + "\n".join(extracted_data))
                    return 

    def native_xml_replace(self, filepath, search_term, replace_term):
        temp_dir = tempfile.mkdtemp()
        temp_file_path = os.path.join(temp_dir, "temp_doc.zip")
        safe_search = html.escape(search_term)
        safe_replace = html.escape(replace_term)
        
        try:
            with zipfile.ZipFile(filepath, 'r') as zin:
                with zipfile.ZipFile(temp_file_path, 'w') as zout:
                    for item in zin.infolist():
                        file_content = zin.read(item.filename)
                        if item.filename in ['content.xml', 'word/document.xml']:
                            xml_str = file_content.decode('utf-8')
                            xml_str = xml_str.replace(safe_search, safe_replace)
                            zout.writestr(item, xml_str.encode('utf-8'))
                        else:
                            zout.writestr(item, file_content)
            shutil.move(temp_file_path, filepath)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def edit_pdf_text(self, x, y):
        if not self.doc: return
        page = self.doc[self.current_page]
        word_found = False
        
        for w in page.get_text("words"):
            x0, y0, x1, y1, text, *_ = w
            if (x0 - 3) <= x <= (x1 + 3) and (y0 - 3) <= y <= (y1 + 3):
                word_found = True
                new_text = simpledialog.askstring("Edit Text", f"Replace '{text}' with:")
                if new_text is not None:
                    self._save_state() 
                    
                    if not self.original_filepath.lower().endswith('.pdf'):
                        try:
                            self.native_xml_replace(self.original_filepath, text, new_text)
                            self.refresh_document() 
                        except Exception as e: messagebox.showerror("Error", str(e))
                        return
                    try:
                        page.add_redact_annot((x0, y0, x1, y1))
                        page.apply_redactions()
                        page.insert_text((x0, y1 - 2), new_text, fontsize=11, color=(0, 0, 0))
                        self._save_document_logic()
                        self.display_page()
                    except Exception as e: messagebox.showerror("Save Error", str(e))
                return 
        
        if not word_found:
            if not self.original_filepath.lower().endswith('.pdf'):
                messagebox.showinfo("Tool Restricted", "Only supported for PDFs.")
                return
            new_text = simpledialog.askstring("Add Text", "Enter new text here:")
            if new_text and new_text.strip():
                self._save_state() 
                try:
                    page.insert_text((x, y), new_text, fontsize=11, color=(0, 0, 0))
                    self._save_document_logic()
                    self.display_page()
                except Exception as e: messagebox.showerror("Save Error", str(e))

    def insert_new_text(self, x, y):
        if not self.doc: return
        if not self.original_filepath.lower().endswith('.pdf'):
            messagebox.showinfo("Tool Restricted", "Only supported for native PDFs.")
            return
            
        new_text = simpledialog.askstring("Write Text", "Enter text:")
        if new_text and new_text.strip():
            self._save_state() 
            try:
                page = self.doc[self.current_page]
                page.insert_text((x, y), new_text, fontsize=11, color=(0, 0, 0))
                self._save_document_logic()
                self.display_page()
            except Exception as e: messagebox.showerror("Error", str(e))

    def paste_text_on_canvas(self, x, y):
        if not self.doc or not self.clipboard_text: return
        if not self.original_filepath.lower().endswith('.pdf'): return
            
        self._save_state()
        try:
            page = self.doc[self.current_page]
            page.insert_text((x, y), self.clipboard_text, fontsize=11, color=(0, 0, 0))
            self._save_document_logic()
            self.display_page()
            self.active_tool.set("read")
            self.clipboard_text = ""
        except Exception as e: messagebox.showerror("Error", str(e))

    def find_and_replace(self):
        if not self.original_filepath: return
        search_term = simpledialog.askstring("Find", "Word to find:")
        if not search_term: return 
        replace_term = simpledialog.askstring("Replace", f"Replace '{search_term}' with:")
        if replace_term is None: return 

        has_matches = False
        if self.original_filepath.lower().endswith('.pdf'):
            for page_num in range(len(self.doc)):
                if self.doc[page_num].search_for(search_term):
                    has_matches = True
                    break
            if not has_matches:
                messagebox.showinfo("Not Found", f"Could not find '{search_term}'.")
                return
        
        self._save_state()

        if not self.original_filepath.lower().endswith('.pdf'):
            try:
                self.native_xml_replace(self.original_filepath, search_term, replace_term)
                self.refresh_document() 
            except Exception as e: messagebox.showerror("Error", str(e))
            return

        total_replaced = 0
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            rects = page.search_for(search_term)
            if rects:
                for rect in rects: page.add_redact_annot(rect)
                page.apply_redactions()
                for rect in rects: page.insert_text((rect.x0, rect.y1 - 2), replace_term, fontsize=11, color=(0, 0, 0))
                total_replaced += len(rects)
                
        try:
            self._save_document_logic()
            self.display_page()
            messagebox.showinfo("Success", f"Replaced {total_replaced} instances.")
        except Exception as e: messagebox.showerror("Error", str(e))

    def transfer_custom_text(self):
        file1_path = filedialog.askopenfilename(title="Select File 1", filetypes=[("All", "*.pdf *.txt *.docx *.odt")])
        if not file1_path: return
            
        full_text = ""
        try:
            if file1_path.lower().endswith('.pdf'):
                doc = fitz.open(file1_path)
                for page in doc: full_text += page.get_text() + "\n"
                doc.close()
            elif file1_path.lower().endswith(('.odt', '.docx')):
                full_text = self.extract_odf_text(file1_path)
            elif file1_path.lower().endswith('.txt'):
                with open(file1_path, 'r', encoding='utf-8') as f: full_text = f.read()
                    
            if not full_text.strip(): return
        except Exception as e: messagebox.showerror("Error", str(e)); return

        selection_window = tk.Toplevel(self.root)
        selection_window.title("Select Text")
        selection_window.geometry("700x500")

        def on_confirm():
            try: selected_text = text_widget.selection_get()
            except tk.TclError: return
            selection_window.destroy()
            self._paste_into_file2(selected_text)

        tk.Button(selection_window, text="Confirm Selection", command=on_confirm, bg="#d1e7dd").pack(side=tk.BOTTOM, pady=15)
        text_widget = tk.Text(selection_window, wrap=tk.WORD, font=("Arial", 11))
        text_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=15, pady=5)
        text_widget.insert(tk.END, full_text)

    def _paste_into_file2(self, text_to_paste):
        self.clipboard_text = text_to_paste
        file2_path = filedialog.askopenfilename(title="Select File 2", filetypes=[("Supported", "*.pdf *.txt"), ("All", "*.*")])
        if not file2_path: return

        if file2_path.lower().endswith('.pdf'):
            self.open_file(path=file2_path)
            self.active_tool.set("paste")
            messagebox.showinfo("Active", "Click on the document to paste!")
        elif file2_path.lower().endswith('.txt'):
            try:
                with open(file2_path, 'a', encoding='utf-8') as f: f.write(f"\n\n{self.clipboard_text}")
                self.clipboard_text = ""
            except Exception as e: messagebox.showerror("Error", str(e))
        else:
            messagebox.showinfo("Restricted", "Only supported for PDF/TXT.")

    def extract_odf_text(self, filepath):
        try:
            with zipfile.ZipFile(filepath, 'r') as zf:
                if filepath.lower().endswith('.docx'): xml_content = zf.read('word/document.xml')
                else: xml_content = zf.read('content.xml')
                
            xml_str = re.sub(r'&(?!(?:apos|quot|amp|lt|gt);)', '&amp;', xml_content.decode('utf-8'))
            tree = ET.fromstring(xml_str)
            
            if filepath.lower().endswith('.ods'):
                text_lines = []
                for row in tree.iter():
                    if row.tag.endswith('}table-row'):
                        row_data = [ "".join(c.itertext()).strip() for c in row.iter() if c.tag.endswith('}table-cell')]
                        if any(row_data): text_lines.append(" | ".join(item.ljust(15) for item in row_data))
                return "\n".join(text_lines)
            elif filepath.lower().endswith('.docx'):
                return "\n\n".join(["".join(e.itertext()).strip() for e in tree.iter() if e.tag.endswith('}p') and "".join(e.itertext()).strip()])
            else:
                return "\n\n".join(["".join(e.itertext()).strip() for e in tree.iter() if (e.tag.endswith('}p') or e.tag.endswith('}h')) and "".join(e.itertext()).strip()])
        except Exception as e: raise Exception(str(e))
    def insert_table(self, x, y):
        if not self.doc: return
        
        if not self.original_filepath.lower().endswith('.pdf'):
            messagebox.showinfo("Tool Restricted", "Drawing interactive tables requires fixed visual coordinates, which are only supported on native PDF files.")
            return

        rows = simpledialog.askinteger("Table Size", "How many ROWS do you need?", minvalue=1, maxvalue=20)
        if not rows: return
        
        cols = simpledialog.askinteger("Table Size", "How many COLUMNS do you need?", minvalue=1, maxvalue=15)
        if not cols: return

        table_window = tk.Toplevel(self.root)
        table_window.title(f"Enter Table Data ({rows}x{cols})")
        table_window.geometry(f"{max(300, cols*110)}x{max(200, rows*40 + 70)}")

        tk.Label(table_window, text="Type your data below. Empty cells will be left blank.", font=("Arial", 9, "bold")).grid(row=0, column=0, columnspan=cols, pady=5)

        entries = []
        for r in range(rows):
            row_entries = []
            for c in range(cols):
                entry = tk.Entry(table_window, width=15)
                entry.grid(row=r+1, column=c, padx=3, pady=3)
                row_entries.append(entry)
            entries.append(row_entries)

        def on_confirm():
            self._save_state() 
            
            try:
                page = self.doc[self.current_page]
                
                cell_w = 90
                cell_h = 25

                for r in range(rows):
                    for c in range(cols):
                        cell_text = entries[r][c].get()
                        
                        rect_x0 = x + (c * cell_w)
                        rect_y0 = y + (r * cell_h)
                        rect_x1 = rect_x0 + cell_w
                        rect_y1 = rect_y0 + cell_h
                        
                        cell_rect = fitz.Rect(rect_x0, rect_y0, rect_x1, rect_y1)
                        
                        page.draw_rect(cell_rect, color=(0, 0, 0), width=0.5)
                        
                        if cell_text.strip():
                            text_rect = fitz.Rect(rect_x0 + 3, rect_y0 + 3, rect_x1 - 3, rect_y1 - 3)
                            page.insert_textbox(text_rect, cell_text, fontsize=10, color=(0, 0, 0), align=0)
                
                table_window.destroy()
                self._save_document_logic()
                self.display_page()
                
                self.active_tool.set("read")
                self.status_var.set(" Table inserted successfully.")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to draw table: {e}")

        tk.Button(table_window, text="Draw Table on Document", command=on_confirm, bg="#d1e7dd", font=("Arial", 10, "bold")).grid(row=rows+1, column=0, columnspan=cols, pady=15)

    def open_file(self, path=None, is_refresh=False):
        if not path:
            path = filedialog.askopenfilename(filetypes=[("All Supported", "*.pdf *.png *.jpg *.txt *.odt *.ods *.docx"), ("All Files", "*.*")])
        if path:
            if not is_refresh:
                self.undo_stack.clear()
                self.redo_stack.clear()

            self.original_filepath = path
            try:
                if path.lower().endswith(('.odt', '.ods', '.odp', '.odg')):
                    text_bytes = self.extract_odf_text(path).encode('utf-8')
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
            except Exception as e: messagebox.showerror("Unsupported File", str(e))

    def display_page(self):
        if not self.doc: return
        page = self.doc[self.current_page]
        try:
            for annot in page.annots():
                if annot.type[0] == 8: page.delete_annot(annot)
        except: pass 

        if self.search_var.get():
            try:
                for inst in page.search_for(self.search_var.get()): page.add_highlight_annot(inst)
            except: pass

        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        self.photo = ImageTk.PhotoImage(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))
        
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
        self.canvas.config(scrollregion=(0, 0, pix.width, pix.height))
        self.status_var.set(f" File: {os.path.basename(self.original_filepath)}   | Page {self.current_page + 1} of {len(self.doc)}")

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