import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import serial
import serial.tools.list_ports
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import threading
import time
from datetime import datetime
from collections import deque
import csv
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
import os

class ArduinoMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("Monitor de Potenciómetros Arduino")
        self.root.geometry("1400x850")
        
        # Variables de control
        self.serial_conn = None
        self.is_reading = False
        self.is_paused = False
        self.max_data_points = 200
        
        # Datos para cada potenciómetro
        self.pot_data = {
            'Pot1': {'data': deque(maxlen=self.max_data_points), 'enabled': True, 'color': '#e74c3c'},
            'Pot2': {'data': deque(maxlen=self.max_data_points), 'enabled': True, 'color': '#3498db'},
            'Pot3': {'data': deque(maxlen=self.max_data_points), 'enabled': True, 'color': '#2ecc71'},
            'Pot4': {'data': deque(maxlen=self.max_data_points), 'enabled': True, 'color': '#f39c12'}
        }
        
        self.time_data = deque(maxlen=self.max_data_points)
        self.start_time = time.time()
        
        self.setup_ui()
        self.update_ports()
        
    def setup_ui(self):
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configurar el grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=0)
        main_frame.rowconfigure(1, weight=1)
        
        # Frame de control superior - IZQUIERDA
        control_frame = ttk.LabelFrame(main_frame, text="Control de Conexión", padding="10")
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10), padx=(0, 10))
        
        # Puerto Serial
        ttk.Label(control_frame, text="Puerto:").grid(row=0, column=0, padx=5)
        self.port_combo = ttk.Combobox(control_frame, width=15, state='readonly')
        self.port_combo.grid(row=0, column=1, padx=5)
        
        ttk.Button(control_frame, text="🔄 Actualizar", command=self.update_ports).grid(row=0, column=2, padx=5)
        
        # Botones de control
        self.connect_btn = ttk.Button(control_frame, text="🔌 Conectar", command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=3, padx=5)
        
        self.pause_btn = ttk.Button(control_frame, text="⏸ Pausar", command=self.toggle_pause, state='disabled')
        self.pause_btn.grid(row=0, column=4, padx=5)
        
        ttk.Button(control_frame, text="🗑 Limpiar", command=self.clear_data).grid(row=0, column=5, padx=5)
        
        # Frame de reportes - DERECHA
        report_frame = ttk.LabelFrame(main_frame, text="Reportes", padding="10")
        report_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        ttk.Button(report_frame, text="📄 Exportar CSV", command=self.export_csv, width=18).pack(pady=5)
        ttk.Button(report_frame, text="📊 Generar PDF", command=self.generate_pdf_report, width=18).pack(pady=5)
        
        # Frame de gráficas con checkboxes integrados (2x2)
        graph_frame = ttk.Frame(main_frame)
        graph_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configurar grid 2x2
        graph_frame.columnconfigure(0, weight=1)
        graph_frame.columnconfigure(1, weight=1)
        graph_frame.rowconfigure(0, weight=1)
        graph_frame.rowconfigure(1, weight=1)
        
        # Crear cada cuadrante con checkbox + gráfica
        self.pot_vars = {}
        self.pot_labels = {}
        self.axes = {}
        self.lines = {}
        self.canvases = {}
        
        positions = [
            ('Pot1', 0, 0),
            ('Pot2', 0, 1),
            ('Pot3', 1, 0),
            ('Pot4', 1, 1)
        ]
        
        for pot_name, row, col in positions:
            pot_info = self.pot_data[pot_name]
            
            # Frame contenedor para cada potenciómetro
            pot_container = ttk.LabelFrame(graph_frame, text="", padding="5")
            pot_container.grid(row=row, column=col, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
            
            # Frame superior con checkbox y valor
            top_frame = ttk.Frame(pot_container)
            top_frame.pack(fill=tk.X, pady=(0, 5))
            
            # Checkbox
            var = tk.BooleanVar(value=True)
            self.pot_vars[pot_name] = var
            
            cb = ttk.Checkbutton(top_frame, text=pot_name, variable=var,
                                command=lambda p=pot_name: self.toggle_pot(p))
            cb.pack(side=tk.LEFT, padx=5)
            
            # Label de valor
            label = ttk.Label(top_frame, text="---", 
                            foreground=pot_info['color'], font=('Arial', 12, 'bold'))
            label.pack(side=tk.LEFT, padx=10)
            self.pot_labels[pot_name] = label
            
            # Crear figura de matplotlib individual
            fig = Figure(figsize=(5.5, 3.5), dpi=90)
            ax = fig.add_subplot(111)
            ax.set_xlabel('Tiempo (s)', fontsize=9)
            ax.set_ylabel('Valor', fontsize=9)
            ax.set_title(f'{pot_name}', fontsize=10, fontweight='bold', color=pot_info['color'])
            ax.grid(True, alpha=0.3, linestyle='--')
            ax.set_ylim(0, 1023)
            ax.tick_params(labelsize=8)
            
            line, = ax.plot([], [], color=pot_info['color'], linewidth=2.5)
            
            # Canvas para la gráfica
            canvas = FigureCanvasTkAgg(fig, master=pot_container)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            self.axes[pot_name] = ax
            self.lines[pot_name] = line
            self.canvases[pot_name] = canvas
        
    def update_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports:
            self.port_combo.current(0)
    
    def toggle_connection(self):
        if not self.is_reading:
            self.connect()
        else:
            self.disconnect()
    
    def connect(self):
        port = self.port_combo.get()
        if not port:
            messagebox.showerror("Error", "Selecciona un puerto serial")
            return
        
        try:
            self.serial_conn = serial.Serial(port, 9600, timeout=1)
            time.sleep(2)  # Esperar a que Arduino se inicialice
            self.is_reading = True
            self.connect_btn.config(text="🔌 Desconectar")
            self.pause_btn.config(state='normal')
            
            # Iniciar thread de lectura
            self.read_thread = threading.Thread(target=self.read_serial, daemon=True)
            self.read_thread.start()
            
            # Iniciar actualización de gráfica
            self.update_plot()
            
            messagebox.showinfo("Conectado", f"Conectado exitosamente a {port}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo conectar: {str(e)}")
    
    def disconnect(self):
        self.is_reading = False
        if self.serial_conn:
            self.serial_conn.close()
            self.serial_conn = None
        self.connect_btn.config(text="🔌 Conectar")
        self.pause_btn.config(state='disabled')
    
    def toggle_pause(self):
        self.is_paused = not self.is_paused
        self.pause_btn.config(text="▶ Reanudar" if self.is_paused else "⏸ Pausar")
    
    def toggle_pot(self, pot_name):
        self.pot_data[pot_name]['enabled'] = self.pot_vars[pot_name].get()
    
    def read_serial(self):
        while self.is_reading:
            try:
                if self.serial_conn and self.serial_conn.in_waiting and not self.is_paused:
                    line = self.serial_conn.readline().decode('utf-8').strip()
                    if line:
                        self.process_data(line)
            except Exception as e:
                print(f"Error leyendo serial: {e}")
            time.sleep(0.05)
    
    def process_data(self, line):
        try:
            current_time = time.time() - self.start_time
            self.time_data.append(current_time)
            
            # Parsear datos
            parts = line.split(',')
            for part in parts:
                if ':' in part:
                    pot_id, value = part.split(':')
                    pot_name = f'Pot{pot_id[1]}'  # P1 -> Pot1
                    
                    if pot_name in self.pot_data:
                        value = int(value)
                        self.pot_data[pot_name]['data'].append(value)
                        
                        # Actualizar label
                        self.pot_labels[pot_name].config(text=f"{value}")
        except Exception as e:
            print(f"Error procesando datos: {e}")
    
    def update_plot(self):
        if not self.is_reading:
            return
        
        if self.time_data:
            for pot_name, pot_info in self.pot_data.items():
                ax = self.axes[pot_name]
                line = self.lines[pot_name]
                canvas = self.canvases[pot_name]
                
                if pot_info['enabled'] and pot_info['data']:
                    x_data = list(self.time_data)[-len(pot_info['data']):]
                    y_data = list(pot_info['data'])
                    line.set_data(x_data, y_data)
                    
                    # Ajustar límites X
                    if x_data:
                        ax.set_xlim(max(0, x_data[-1] - 30), x_data[-1] + 1)
                    
                    line.set_visible(True)
                    ax.set_facecolor('white')
                else:
                    line.set_data([], [])
                    line.set_visible(False)
                    ax.set_facecolor('#f5f5f5')
                
                canvas.draw()
        
        self.root.after(100, self.update_plot)
    
    def clear_data(self):
        for pot_info in self.pot_data.values():
            pot_info['data'].clear()
        self.time_data.clear()
        self.start_time = time.time()
        
        for label in self.pot_labels.values():
            label.config(text="---")
    
    def export_csv(self):
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"datos_potenciometros_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        if not filename:
            return
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Encabezados - SOLO potenciómetros habilitados
                headers = ['Tiempo (s)']
                enabled_pots = []
                
                for pot_name, pot_info in self.pot_data.items():
                    if pot_info['enabled']:
                        headers.append(pot_name)
                        enabled_pots.append(pot_name)
                
                writer.writerow(headers)
                
                # Escribir datos solo de potenciómetros habilitados
                max_len = len(self.time_data)
                for i in range(max_len):
                    row = [f"{self.time_data[i]:.2f}"]
                    
                    for pot_name in enabled_pots:
                        pot_info = self.pot_data[pot_name]
                        if i < len(pot_info['data']):
                            row.append(pot_info['data'][i])
                        else:
                            row.append('')
                    
                    writer.writerow(row)
            
            messagebox.showinfo("✅ Exportado", f"Datos exportados exitosamente:\n{filename}\n\nSe guardaron {len(enabled_pots)} potenciómetros seleccionados.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar: {str(e)}")
    
    def generate_pdf_report(self):
        filename = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialfile=f"reporte_potenciometros_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        )
        
        if not filename:
            return
        
        try:
            doc = SimpleDocTemplate(filename, pagesize=letter)
            elements = []
            styles = getSampleStyleSheet()
            
            # Título
            title = Paragraph("Reporte de Monitoreo de Potenciómetros", styles['Title'])
            elements.append(title)
            elements.append(Spacer(1, 12))
            
            # Fecha y hora
            date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            date_p = Paragraph(f"<b>Fecha de generación:</b> {date_str}", styles['Normal'])
            elements.append(date_p)
            elements.append(Spacer(1, 8))
            
            # Información de potenciómetros habilitados
            enabled_list = [pot for pot, info in self.pot_data.items() if info['enabled']]
            enabled_text = f"<b>Potenciómetros monitoreados:</b> {', '.join(enabled_list)}"
            elements.append(Paragraph(enabled_text, styles['Normal']))
            elements.append(Spacer(1, 20))
            
            # Tabla de estadísticas - SOLO potenciómetros habilitados
            table_data = [['Potenciómetro', 'Valor Actual', 'Promedio', 'Mínimo', 'Máximo', 'Muestras']]
            
            for pot_name, pot_info in self.pot_data.items():
                if pot_info['enabled'] and pot_info['data']:
                    data = list(pot_info['data'])
                    avg = sum(data) / len(data)
                    min_val = min(data)
                    max_val = max(data)
                    current = data[-1]
                    
                    table_data.append([
                        pot_name,
                        str(current),
                        f"{avg:.2f}",
                        str(min_val),
                        str(max_val),
                        str(len(data))
                    ])
            
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ecf0f1')]),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey)
            ]))
            
            elements.append(table)
            elements.append(Spacer(1, 25))
            
            # Guardar gráficas individuales - SOLO potenciómetros habilitados
            temp_images = []
            
            elements.append(Paragraph("Gráficas Individuales", styles['Heading2']))
            elements.append(Spacer(1, 15))
            
            for pot_name, pot_info in self.pot_data.items():
                if pot_info['enabled'] and pot_info['data']:
                    # Crear figura individual para cada potenciómetro
                    fig_individual = Figure(figsize=(7, 3.5))
                    ax_individual = fig_individual.add_subplot(111)
                    
                    x_data = list(self.time_data)[-len(pot_info['data']):]
                    y_data = list(pot_info['data'])
                    
                    ax_individual.plot(x_data, y_data, color=pot_info['color'], linewidth=2, label=pot_name)
                    ax_individual.set_xlabel('Tiempo (s)', fontsize=10)
                    ax_individual.set_ylabel('Valor', fontsize=10)
                    ax_individual.set_title(f'{pot_name}', fontsize=12, fontweight='bold', color=pot_info['color'])
                    ax_individual.grid(True, alpha=0.3, linestyle='--')
                    ax_individual.set_ylim(0, 1023)
                    
                    # Guardar imagen temporal
                    temp_img = f"temp_{pot_name}_{int(time.time())}.png"
                    fig_individual.savefig(temp_img, dpi=150, bbox_inches='tight')
                    temp_images.append(temp_img)
                    
                    # Agregar al PDF
                    elements.append(Image(temp_img, width=460, height=230))
                    elements.append(Spacer(1, 15))
                    
                    plt.close(fig_individual)
            
            # Construir PDF
            doc.build(elements)
            
            # Eliminar imágenes temporales
            for temp_img in temp_images:
                if os.path.exists(temp_img):
                    os.remove(temp_img)
            
            messagebox.showinfo("✅ Reporte Generado", f"Reporte PDF generado exitosamente:\n{filename}\n\nIncluye gráficas de {len(enabled_list)} potenciómetros seleccionados.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar el reporte: {str(e)}")

def main():
    root = tk.Tk()
    app = ArduinoMonitor(root)
    root.mainloop()

if __name__ == "__main__":
    main()