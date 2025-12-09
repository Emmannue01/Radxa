import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import serial
import queue
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
        self.root.state('zoomed') # Maximizar la ventana al iniciar
        
        # Variables de control
        self.serial_conn = None
        self.is_reading = False
        self.is_paused = False
        self.is_recording_session = False # Para controlar la grabación de datos para CSV
        self.is_calibrating = False # Para controlar el modo calibración
        self.max_data_points = 200
        
        # Datos para cada potenciómetro
        self.pot_data = {
            'Pot1': {'values': deque(maxlen=self.max_data_points), 'times': deque(maxlen=self.max_data_points), 'all_values': [], 'all_times': [], 'enabled': False, 'color': '#e74c3c', 'offset': 0, 'min_session': None, 'max_session': None},
            'Pot2': {'values': deque(maxlen=self.max_data_points), 'times': deque(maxlen=self.max_data_points), 'all_values': [], 'all_times': [], 'enabled': False, 'color': '#3498db', 'offset': 0, 'min_session': None, 'max_session': None},
            'Pot3': {'values': deque(maxlen=self.max_data_points), 'times': deque(maxlen=self.max_data_points), 'all_values': [], 'all_times': [], 'enabled': False, 'color': '#2ecc71', 'offset': 0, 'min_session': None, 'max_session': None},
            'Pot4': {'values': deque(maxlen=self.max_data_points), 'times': deque(maxlen=self.max_data_points), 'all_values': [], 'all_times': [], 'enabled': False, 'color': '#f39c12', 'offset': 0, 'min_session': None, 'max_session': None},
            'Pot5': {'values': deque(maxlen=self.max_data_points), 'times': deque(maxlen=self.max_data_points), 'all_values': [], 'all_times': [], 'enabled': False, 'color': '#9b59b6', 'offset': 0, 'min_session': None, 'max_session': None}
        }
        
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
        
        # --- Estilos para botones más grandes y coloridos ---
        style = ttk.Style()
        style.theme_use('clam') # Usar un tema que permite mejor personalización de colores
        
        # Estilo general para botones grandes
        style.configure('TButton', font=('Arial', 11, 'bold'), padding=8, borderwidth=0)
        style.map('TButton',
                  relief=[('pressed', 'sunken'), ('!pressed', 'raised')])

        # Estilos por color/función
        style.configure('Connect.TButton', background='#2ecc71', foreground='white') # Verde
        style.map('Connect.TButton', background=[('active', '#27ae60')])

        style.configure('Disconnect.TButton', background='#e74c3c', foreground='white') # Rojo
        style.map('Disconnect.TButton', background=[('active', '#c0392b')])

        style.configure('Pause.TButton', background='#f39c12', foreground='white') # Naranja
        style.map('Pause.TButton', background=[('active', '#d35400')])

        style.configure('Action.TButton', background='#3498db', foreground='white') # Azul
        style.map('Action.TButton', background=[('active', '#2980b9')])

        style.configure('Report.TButton', background='#9b59b6', foreground='white') # Morado
        style.map('Report.TButton', background=[('active', '#8e44ad')])

        style.configure('Record.TButton', background='#2ecc71', foreground='white') # Verde (igual que conectar)
        style.map('Record.TButton', background=[('active', '#27ae60')])

        # Estilo para el botón "SET 0"
        style.configure('Small.TButton', font=('Arial', 9, 'bold'), padding=(8, 4), foreground='black', background='#ecf0f1')
        style.map('Small.TButton', background=[('active', '#bdc3c7')])
        
        # Frame de control superior - IZQUIERDA
        control_frame = ttk.LabelFrame(main_frame, text="Control de Conexión", padding="10")
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10), padx=(0, 10))
        
        # Puerto Serial
        ttk.Label(control_frame, text="Puerto:").grid(row=0, column=0, padx=5)
        self.port_combo = ttk.Combobox(control_frame, width=15, state='readonly', font=('Arial', 10))
        self.port_combo.grid(row=0, column=1, padx=5)
        
        ttk.Button(control_frame, text="Actualizar", command=self.update_ports, style='Action.TButton').grid(row=0, column=2, padx=5)
        
        # Botones de control
        self.connect_btn = ttk.Button(control_frame, text="Conectar", command=self.toggle_connection, style='Connect.TButton')
        self.connect_btn.grid(row=0, column=3, padx=5)
        
        self.pause_btn = ttk.Button(control_frame, text="Pausar", command=self.toggle_pause, state='disabled', style='Pause.TButton')
        self.pause_btn.grid(row=0, column=4, padx=5)
        
        ttk.Button(control_frame, text="Limpiar", command=self.clear_data, style='Action.TButton').grid(row=0, column=5, padx=5)
        
        # Botón para iniciar/detener la grabación de la sesión
        self.record_btn = ttk.Button(control_frame, text="Iniciar Grabación", command=self.toggle_recording, state='disabled', style='Record.TButton')
        self.record_btn.grid(row=0, column=6, padx=10)

        # Frame de reportes - DERECHA
        report_frame = ttk.LabelFrame(main_frame, text="Reportes", padding="10")
        report_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        ttk.Button(report_frame, text="Exportar CSV", command=self.export_csv, width=18, style='Report.TButton').pack(pady=5, padx=5, fill=tk.X)
        ttk.Button(report_frame, text="Generar PDF", command=self.generate_pdf_report, width=18, style='Report.TButton').pack(pady=5, padx=5, fill=tk.X)

        # El frame de control del Arduino se elimina de aquí, se moverá a cada gráfica individual.
        main_frame.columnconfigure(2, weight=0) # Ajustar columna
        
        # Frame de gráficas con checkboxes integrados (2x2)
        graph_frame = ttk.Frame(main_frame)
        graph_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configurar grid 2x2
        graph_frame.columnconfigure(0, weight=1)
        graph_frame.columnconfigure(1, weight=1)
        graph_frame.rowconfigure(0, weight=1)
        graph_frame.rowconfigure(1, weight=1)
        graph_frame.rowconfigure(2, weight=1) # Añadir una tercera fila para el Pot5
        
        # Crear cada cuadrante con checkbox + gráfica
        self.pot_vars = {}
        self.pot_labels = {}
        self.axes = {}
        self.lines = {}
        self.range_entries = {} # Para guardar las entradas de rango
        self.canvases = {}
        self.min_max_texts = {} # Para mostrar min/max en la gráfica
        
        positions = [
            ('Pot1', 0, 0, 1),
            ('Pot2', 0, 1, 1),
            ('Pot3', 1, 0, 1),
            ('Pot4', 1, 1, 1),
            ('Pot5', 2, 0, 1) # Pot5 irá en la tercera fila, primera columna
        ]
        
        for pot_name, row, col, colspan in positions:
            pot_info = self.pot_data[pot_name]
            
            # Frame contenedor para cada potenciómetro
            pot_container = ttk.LabelFrame(graph_frame, text="", padding="5")
            pot_container.grid(row=row, column=col, columnspan=colspan, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
            
            # --- Frame superior con checkbox, valor y botones de cero ---
            top_frame = ttk.Frame(pot_container)
            top_frame.pack(fill=tk.X, pady=(0, 2))
            
            # Checkbox
            var = tk.BooleanVar(value=False)
            self.pot_vars[pot_name] = var
            
            cb = ttk.Checkbutton(top_frame, text=pot_name, variable=var,
                                command=lambda p=pot_name: self.toggle_pot(p))
            cb.pack(side=tk.LEFT, padx=5)
            
            # Label de valor
            label = ttk.Label(top_frame, text="---", 
                            foreground=pot_info['color'], font=('Arial', 16, 'bold'))
            label.pack(side=tk.LEFT, padx=10)
            self.pot_labels[pot_name] = label
            
            # Botón para poner a cero (tare)
            tare_btn = ttk.Button(top_frame, text="Poner a 0", style='Small.TButton',
                                  command=lambda p=pot_name: self.set_zero(p))
            tare_btn.pack(side=tk.LEFT, padx=5)

            # Botón para reiniciar el offset
            reset_btn = ttk.Button(top_frame, text="Reset 0", style='Small.TButton',
                                   command=lambda p=pot_name: self.reset_offset(p))
            reset_btn.pack(side=tk.LEFT, padx=5)
            
            # --- Controles de rango (movidos al top_frame) ---
            ttk.Label(top_frame).pack(side=tk.LEFT, padx=(15, 2))
            range_entry = ttk.Entry(top_frame, width=6, font=('Arial', 9))
            range_entry.insert(0, "25.0")
            range_entry.pack(side=tk.LEFT, padx=2)
            self.range_entries[pot_name] = range_entry

            # El índice del potenciómetro (1-5)
            pot_index = int(pot_name.replace('Pot', ''))

            ttk.Button(top_frame, text="Establecer", style='Small.TButton',
                       command=lambda p=pot_name, i=pot_index: self.set_transducer_range(p, i)).pack(side=tk.LEFT, padx=2)


            # Crear figura de matplotlib individual
            fig = Figure(figsize=(5.5, 3.5), dpi=90)
            ax = fig.add_subplot(111)
            ax.set_xlabel('Tiempo (s)', fontsize=9)
            ax.set_ylabel('Valor', fontsize=9)
            ax.set_title(f'{pot_name}', fontsize=10, fontweight='bold', color=pot_info['color'])
            ax.grid(True, alpha=0.3, linestyle='--')
            # Ajustar el rango Y para milímetros (0-50mm) con un pequeño margen
            ax.set_ylim(-2, 52)
            ax.tick_params(labelsize=8)
            
            line, = ax.plot([], [], color=pot_info['color'], linewidth=2.5)
            
            # Canvas para la gráfica
            canvas = FigureCanvasTkAgg(fig, master=pot_container)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            self.axes[pot_name] = ax
            self.lines[pot_name] = line
            self.canvases[pot_name] = canvas
            
            # Añadir el objeto de texto para min/max
            min_max_text = ax.text(0.02, 0.98, '', transform=ax.transAxes, fontsize=9,
                                   verticalalignment='top', bbox=dict(boxstyle='round,pad=0.3', fc='wheat', alpha=0.5))
            self.min_max_texts[pot_name] = min_max_text

        # --- Panel de Calibración Integrado ---
        cal_container = ttk.LabelFrame(graph_frame, text="Panel de Calibración", padding="10")
        cal_container.grid(row=2, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        cal_container.rowconfigure(0, weight=1)
        cal_container.columnconfigure(0, weight=1)

        # Terminal de Salida
        self.terminal_text = tk.Text(cal_container, wrap=tk.WORD, height=10, font=("Courier New", 10), bg="#2c3e50", fg="#ecf0f1", insertbackground="white")
        self.terminal_text.grid(row=0, column=0, sticky="nsew", pady=(0, 5))

        scrollbar = ttk.Scrollbar(cal_container, command=self.terminal_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.terminal_text.config(yscrollcommand=scrollbar.set)

        # Frame de Comandos
        command_frame = ttk.Frame(cal_container)
        command_frame.grid(row=1, column=0, columnspan=2, sticky="ew")

        # Botones de acceso rápido
        btn_frame = ttk.Frame(command_frame)
        btn_frame.pack(fill=tk.X, pady=5)

        ttk.Label(btn_frame, text="Calibrar T:").pack(side=tk.LEFT, padx=(0, 5))
        for i in range(1, 6): # Crear los 5 botones
            ttk.Button(btn_frame, text=str(i), width=3, style='Small.TButton', command=lambda i=i: self.send_calibration_command(str(i))).pack(side=tk.LEFT, padx=2)

        ttk.Button(btn_frame, text="Guardar (S)", style='Small.TButton', command=lambda: self.send_calibration_command('S')).pack(side=tk.LEFT, padx=(10, 2))
        ttk.Button(btn_frame, text="ENTER", style='Small.TButton', command=lambda: self.send_calibration_command('\n')).pack(side=tk.LEFT, padx=2)

        # Entrada manual
        manual_frame = ttk.Frame(command_frame)
        manual_frame.pack(fill=tk.X, pady=5)

        ttk.Label(manual_frame, text="Manual:").pack(side=tk.LEFT, padx=(0, 5))
        self.cmd_entry = ttk.Entry(manual_frame, width=20)
        self.cmd_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.cmd_entry.bind("<Return>", self.send_entry_command)

        send_btn = ttk.Button(manual_frame, text="Enviar", style='Small.TButton', command=self.send_entry_command)
        send_btn.pack(side=tk.LEFT, padx=5)

        # Botón para iniciar el modo de calibración general
        ttk.Button(command_frame, text="Iniciar Calibración (C)", style='Action.TButton', command=lambda: self.send_calibration_command('C')).pack(fill=tk.X, pady=(10,0))

    def send_calibration_command(self, cmd):
        if self.send_command(cmd + '\n'):
            self.terminal_text.insert(tk.END, f">>> {cmd}\n", "command_sent")
            self.terminal_text.tag_config("command_sent", foreground="#3498db", font=("Courier New", 10, "bold"))
            self.terminal_text.see(tk.END)
        
    def update_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports:
            self.port_combo.current(0)

    def send_command(self, command):
        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.write(command.encode('utf-8', errors='ignore'))
                print(f"Comando enviado: {command}")
                return True
            except Exception as e:
                messagebox.showerror("Error de Comunicación", f"No se pudo enviar el comando: {e}")
                return False
        else:
            messagebox.showwarning("Desconectado", "No se puede enviar el comando. Conéctate a un puerto primero.")
            return False
    
    def send_entry_command(self, event=None):
        cmd = self.cmd_entry.get()
        if cmd:
            self.send_calibration_command(cmd)
            self.cmd_entry.delete(0, tk.END)

    def set_transducer_range(self, pot_name, pot_index):
        new_range = self.range_entries[pot_name].get()
        # Nuevo formato de comando: R<index>,<range> ej: "R1,50.0"
        if self.send_command(f'R{pot_index},{new_range}\n'):
            messagebox.showinfo("Comando Enviado", f"Se envió el comando para establecer el rango a {new_range} mm.")
    
    def toggle_connection(self):
        # Al conectar, limpiar los rangos actuales para forzar la actualización desde el Arduino
        if not self.is_reading:
            for pot_name in self.pot_data.keys():
                if pot_name in self.range_entries:
                    self.range_entries[pot_name].delete(0, tk.END)
                    self.range_entries[pot_name].insert(0, "...") # Indicador visual

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
            self.connect_btn.config(text="Desconectar", style='Disconnect.TButton')
            self.pause_btn.config(state='normal')
            self.record_btn.config(state='normal')
            
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
        self.connect_btn.config(text="Conectar", style='Connect.TButton')
        self.pause_btn.config(state='disabled', text="Pausar")
        self.is_paused = False

        # Detener y deshabilitar grabación
        self.is_recording_session = False
        self.record_btn.config(state='disabled', text="Iniciar Grabación", style='Record.TButton')

    
    def toggle_pause(self):
        self.is_paused = not self.is_paused
        self.pause_btn.config(text="Reanudar" if self.is_paused else "Pausar")
    
    def toggle_pot(self, pot_name):
        is_enabled = self.pot_vars[pot_name].get()
        self.pot_data[pot_name]['enabled'] = is_enabled
        
        pot_index = int(pot_name.replace('Pot', ''))
        
        if is_enabled:
            self.send_command(f'E{pot_index}\n') # Enviar comando para Habilitar
        else:
            self.send_command(f'D{pot_index}\n') # Enviar comando para Deshabilitar

    def toggle_recording(self):
        self.is_recording_session = not self.is_recording_session
        if self.is_recording_session:
            # Al iniciar una nueva grabación, limpiar los datos de la sesión anterior
            for pot_info in self.pot_data.values():
                pot_info['all_values'].clear()
                pot_info['all_times'].clear()
            
            self.record_btn.config(text="Detener Grabación", style='Disconnect.TButton')
            messagebox.showinfo("Grabación Iniciada", "Se ha iniciado la grabación de datos para el reporte.")
        else:
            self.record_btn.config(text="Iniciar Grabación", style='Record.TButton')
            messagebox.showinfo("Grabación Detenida", "Se ha detenido la grabación. Los datos capturados están listos para ser exportados.")

    
    def read_serial(self):
        while self.is_reading:
            try:
                if self.serial_conn and self.serial_conn.in_waiting and not self.is_paused:
                    # Usamos readline para capturar líneas completas
                    line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                    if not line:
                        continue

                    # Si la línea contiene datos de potenciómetro, la procesamos.
                    if line.startswith("Pot"):
                        self.process_data(line)
                    else: # Si no, es un mensaje del sistema o de calibración, lo mostramos en la terminal.
                        # --- NUEVA LÓGICA PARA ACTUALIZAR RANGO ---
                        # Buscar mensajes de configuración de rango del Arduino.
                        # Formato esperado: "T1: Min=100 Max=950 Rango=50.0mm"
                        # O el nuevo formato: "✓ Rango T1 actualizado a 50.0mm"
                        if "Rango=" in line or "Rango T" in line:
                            try:
                                parts = line.split()
                                t_index = -1
                                r_value = ""
                                if line.startswith("T"): # Formato "T1: ... Rango=25.0mm"
                                    t_index = int(parts[0].replace('T', '').replace(':', ''))
                                    r_value = parts[-1].replace('mm', '').replace('Rango=', '')
                                elif "Rango T" in line: # Formato "✓ Rango T1 actualizado a 50.0mm"
                                    t_index = int(parts[2].replace('T', ''))
                                    r_value = parts[4]

                                if t_index != -1 and r_value:
                                    pot_name = f"Pot{t_index}"
                                    self.range_entries[pot_name].delete(0, tk.END)
                                    self.range_entries[pot_name].insert(0, r_value)
                            except (ValueError, IndexError) as e:
                                print(f"No se pudo parsear la línea de rango: '{line}'. Error: {e}")

                        self.terminal_text.insert(tk.END, line + '\n')
                        self.terminal_text.see(tk.END) # Auto-scroll
            except Exception as e:
                print(f"Error leyendo serial: {e}")
            time.sleep(0.05)
    
    def process_data(self, line):
        try:
            # Parsear datos: soporta separadores por coma (,) o por pipe (|)
            parts = line.replace('|', ',').split(',')
            for part in parts:
                part = part.strip() # Eliminar espacios en blanco al inicio/final
                if ':' in part: # Asegurarse de que el fragmento tiene el formato PotX:valor
                    split_part = part.split(':')
                    if len(split_part) != 2:
                        print(f"Skipping malformed data part: {part}")
                        continue  # Skip this part and move to the next
                    pot_name, value_str = [s.strip() for s in split_part] # Limpiar espacios
                    
                    if pot_name in self.pot_data:
                        pot_info = self.pot_data[pot_name]

                        # ¡CORRECCIÓN CLAVE! Convertir a float, no a int.
                        raw_value = float(value_str)

                        # Ya no es necesario verificar si está habilitado o si el valor es -1.0,
                        # porque el Arduino solo enviará datos válidos de transductores habilitados.

                        # Aplicar offset
                        adjusted_value = raw_value - pot_info['offset']
                        current_time = time.time() - self.start_time
                        
                        pot_info['values'].append(adjusted_value)
                        pot_info['times'].append(current_time)
                        
                        if self.is_recording_session:
                            pot_info['all_values'].append(adjusted_value)
                            pot_info['all_times'].append(current_time)
       
                        # Actualizar label
                        self.pot_labels[pot_name].config(text=f"{adjusted_value:.3f} mm")
        except Exception as e:
            print(f"Error procesando datos: {e}")
    
    def update_plot(self):
        if not self.is_reading:
            return
        
        for pot_name, pot_info in self.pot_data.items():
            ax = self.axes[pot_name]
            line = self.lines[pot_name]
            canvas = self.canvases[pot_name]
            min_max_text = self.min_max_texts[pot_name]
            
            if pot_info['enabled'] and pot_info['values']:
                x_data = list(pot_info['times'])
                y_data = list(pot_info['values'])
                line.set_data(x_data, y_data)
                
                # Ajustar límites X
                if x_data:
                    ax.set_xlim(max(0, x_data[-1] - 30), x_data[-1] + 1)
                
                line.set_visible(True)
                ax.set_facecolor('white')

                # Actualizar texto de min/max
                min_val = pot_info['min_session']
                max_val = pot_info['max_session']
                if min_val is not None and max_val is not None:
                    min_max_text.set_text(f'Min: {min_val:.2f}\nMax: {max_val:.2f}')
                else:
                    min_max_text.set_text('')
                min_max_text.set_visible(True)
            else:
                line.set_data([], [])
                line.set_visible(False)
                ax.set_facecolor('#f5f5f5')
                min_max_text.set_visible(False)
            
            canvas.draw()
        
        self.root.after(100, self.update_plot)
    
    def clear_data(self):
        for pot_info in self.pot_data.values():
            pot_info['values'].clear()
            pot_info['times'].clear()
            pot_info['all_values'].clear()
            pot_info['all_times'].clear()
            pot_info['offset'] = 0 # Restablecer el offset
            pot_info['min_session'] = None # Restablecer min/max
            pot_info['max_session'] = None
        self.start_time = time.time()

        # Reiniciar estado de grabación si la conexión está activa
        if self.is_reading:
            self.is_recording_session = False
            self.record_btn.config(text="Iniciar Grabación", style='Record.TButton')
        
        for label in self.pot_labels.values():
            label.config(text="--- mm")
    
    def set_zero(self, pot_name):
        pot_info = self.pot_data[pot_name]
        if pot_info['values']:
            # El offset es la suma del offset actual más el último valor ajustado
            last_adjusted_value = list(pot_info['values'])[-1]
            pot_info['offset'] += last_adjusted_value
            messagebox.showinfo("Punto Cero Establecido", f"El nuevo cero para {pot_name} se ha establecido en el valor actual.")

    def reset_offset(self, pot_name):
        pot_info = self.pot_data[pot_name]
        pot_info['offset'] = 0
        messagebox.showinfo("Offset Reiniciado", f"El offset para {pot_name} ha sido reiniciado a 0.")

    
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
                
                # Usar el historial completo ('all_values') para la exportación
                # Usamos el primer potenciómetro habilitado para obtener los tiempos
                if not enabled_pots:
                    messagebox.showwarning("Advertencia", "No hay potenciómetros habilitados para exportar.")
                    return

                first_pot_info = self.pot_data[enabled_pots[0]]
                max_len = len(first_pot_info['all_values'])

                for i in range(max_len):
                    # Usar el tiempo del primer potenciómetro como referencia
                    row = [f"{first_pot_info['all_times'][i]:.2f}"]
                    for pot_name in enabled_pots:
                        pot_info = self.pot_data[pot_name]
                        row.append(pot_info['all_values'][i] if i < len(pot_info['all_values']) else '')
                    writer.writerow(row)
            
            messagebox.showinfo("Exportado", f"Datos exportados exitosamente:\n{filename}\n\nSe guardaron {len(enabled_pots)} potenciómetros seleccionados.")
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
                if pot_info['enabled'] and pot_info['values']:
                    data = list(pot_info['values'])
                    # Los valores en 'data' ya están ajustados por el offset.
                    avg = sum(data) / len(data)
                    min_val = min(data)
                    max_val = max(data)
                    current = data[-1]
                    
                    table_data.append([
                        f"{pot_name} (offset: {pot_info['offset']})",
                        f"{current:.3f}",
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
                if pot_info['enabled'] and pot_info['values']:
                    # Crear figura individual para cada potenciómetro
                    fig_individual = Figure(figsize=(7, 3.5))
                    ax_individual = fig_individual.add_subplot(111)
                    
                    x_data = list(pot_info['times'])
                    y_data = list(pot_info['values'])
                    
                    ax_individual.plot(x_data, y_data, color=pot_info['color'], linewidth=2, label=pot_name)
                    ax_individual.set_xlabel('Tiempo (s)', fontsize=10)
                    ax_individual.set_ylabel('Valor', fontsize=10)
                    ax_individual.set_title(f'{pot_name}', fontsize=12, fontweight='bold', color=pot_info['color'])
                    ax_individual.grid(True, alpha=0.3, linestyle='--')
                    #ax_individual.set_ylim(0, 1100) # Se deja auto-escala para mejor visualización
                    
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
            
            messagebox.showinfo("Reporte Generado", f"Reporte PDF generado exitosamente:\n{filename}\n\nIncluye gráficas de {len(enabled_list)} potenciómetros seleccionados.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar el reporte: {str(e)}")

def main():
    root = tk.Tk()
    app = ArduinoMonitor(root)
    root.mainloop()

if __name__ == "__main__":
    main()