import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import serial
import queue
import serial.tools.list_ports
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FormatStrFormatter
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
        self.root.title("Monitor de Transductores Arduino")
        self.root.geometry("1400x850")
        self.root.state('zoomed')
        
        self.serial_conn = None
        self.is_reading = False
        self.is_recording_session = False
        self.is_calibrating = False
        
        self.pot_data = {
            'Pot1': {'values': deque(), 'times': deque(), 'all_values': [], 'all_times': [], 'enabled': False, 'color': '#e74c3c', 'offset': 0, 'min_session': None, 'max_session': None, 'is_tared': False},
            'Pot2': {'values': deque(), 'times': deque(), 'all_values': [], 'all_times': [], 'enabled': False, 'color': '#3498db', 'offset': 0, 'min_session': None, 'max_session': None, 'is_tared': False},
            'Pot3': {'values': deque(), 'times': deque(), 'all_values': [], 'all_times': [], 'enabled': False, 'color': '#2ecc71', 'offset': 0, 'min_session': None, 'max_session': None, 'is_tared': False},
            'Pot4': {'values': deque(), 'times': deque(), 'all_values': [], 'all_times': [], 'enabled': False, 'color': '#f39c12', 'offset': 0, 'min_session': None, 'max_session': None, 'is_tared': False},
            'Pot5': {'values': deque(), 'times': deque(), 'all_values': [], 'all_times': [], 'enabled': False, 'color': '#9b59b6', 'offset': 0, 'min_session': None, 'max_session': None, 'is_tared': False}
        }
        
        self.start_time = time.time()
        self.terminal_text = None
        self.main_terminal_text = None
        
        self.setup_ui()
        self.update_ports()
        
    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=0)
        main_frame.rowconfigure(1, weight=1)
        
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure('TButton', font=('Arial', 11, 'bold'), padding=8, borderwidth=0)
        style.map('TButton',
                  relief=[('pressed', 'sunken'), ('!pressed', 'raised')])

        style.configure('Connect.TButton', background='#2ecc71', foreground='white')
        style.map('Connect.TButton', background=[('active', '#27ae60')])

        style.configure('Disconnect.TButton', background='#e74c3c', foreground='white')
        style.map('Disconnect.TButton', background=[('active', '#c0392b')])

        style.configure('Pause.TButton', background='#f39c12', foreground='white')
        style.map('Pause.TButton', background=[('active', '#d35400')])

        style.configure('Action.TButton', background='#3498db', foreground='white')
        style.map('Action.TButton', background=[('active', '#2980b9')])

        style.configure('Report.TButton', background='#9b59b6', foreground='white')
        style.map('Report.TButton', background=[('active', '#8e44ad')])

        style.configure('Record.TButton', background='#2ecc71', foreground='white')
        style.map('Record.TButton', background=[('active', '#27ae60')])

        style.configure('Small.TButton', font=('Arial', 9, 'bold'), padding=(8, 4), foreground='black', background='#ecf0f1')
        style.map('Small.TButton', background=[('active', '#bdc3c7')])
        
        control_frame = ttk.LabelFrame(main_frame, text="Control de Conexión", padding="10")
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10), padx=(0, 10))
        
        ttk.Label(control_frame, text="Puerto:").grid(row=0, column=0, padx=5)
        self.port_combo = ttk.Combobox(control_frame, width=15, state='readonly', font=('Arial', 10))
        self.port_combo.grid(row=0, column=1, padx=5)
        
        ttk.Button(control_frame, text="Actualizar lista de controladores", command=self.update_ports, style='Action.TButton').grid(row=0, column=2, padx=5)
        
        self.connect_btn = ttk.Button(control_frame, text="Conectar controlador", command=self.toggle_connection, style='Connect.TButton')
        self.connect_btn.grid(row=0, column=3, padx=5)
        
        self.record_btn = ttk.Button(control_frame, text="Iniciar captura de datos", command=self.toggle_recording, state='disabled', style='Record.TButton')
        self.record_btn.grid(row=0, column=4, padx=10)

        report_frame = ttk.LabelFrame(main_frame, text="Reportes", padding="10")
        report_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        ttk.Button(report_frame, text="Guardar captura de datos en CSV", command=self.export_csv, style='Report.TButton').pack(pady=5, padx=5, fill=tk.X)
        ttk.Button(report_frame, text="Guardar captura de datos en PDF", command=self.generate_pdf_report, style='Report.TButton').pack(pady=5, padx=5, fill=tk.X)

        main_frame.columnconfigure(2, weight=0)
        
        graph_frame = ttk.Frame(main_frame)
        graph_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        graph_frame.columnconfigure(0, weight=1)
        graph_frame.columnconfigure(1, weight=1)
        graph_frame.rowconfigure(0, weight=1)
        graph_frame.rowconfigure(1, weight=1)
        graph_frame.rowconfigure(2, weight=1)
        
        self.pot_vars = {}
        self.pot_labels = {}
        self.tare_buttons = {}
        self.axes = {}
        self.lines = {}
        self.range_entries = {}
        self.canvases = {}
        self.min_max_texts = {}
        
        positions = [
            ('Pot1', 0, 0, 1),
            ('Pot2', 0, 1, 1),
            ('Pot3', 1, 0, 1),
            ('Pot4', 1, 1, 1),
            ('Pot5', 2, 0, 1)
        ]
        
        for pot_name, row, col, colspan in positions:
            pot_info = self.pot_data[pot_name]
            
            pot_container = ttk.LabelFrame(graph_frame, text="", padding="5")
            pot_container.grid(row=row, column=col, columnspan=colspan, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
            
            top_frame = ttk.Frame(pot_container)
            top_frame.pack(fill=tk.X, pady=(0, 2))
            
            var = tk.BooleanVar(value=False)
            self.pot_vars[pot_name] = var
            
            cb = ttk.Checkbutton(top_frame, text=pot_name.replace('Pot', 'Sensor '), variable=var,
                                command=lambda p=pot_name: self.toggle_pot(p))
            cb.pack(side=tk.LEFT, padx=5)
            
            label = ttk.Label(top_frame, text="---", 
                            foreground=pot_info['color'], font=('Arial', 16, 'bold'))
            label.pack(side=tk.LEFT, padx=10)
            self.pot_labels[pot_name] = label
            
            tare_btn = ttk.Button(top_frame, text="Poner a 0", style='Small.TButton',
                                  command=lambda p=pot_name: self.set_zero(p))
            tare_btn.pack(side=tk.LEFT, padx=5)
            self.tare_buttons[pot_name] = tare_btn

            ttk.Label(top_frame).pack(side=tk.LEFT, padx=(20, 2))
            range_entry = ttk.Entry(top_frame, width=8, font=('Arial', 9))
            range_entry.insert(0, "25.0")
            range_entry.pack(side=tk.LEFT, padx=2)
            self.range_entries[pot_name] = range_entry

            pot_index = int(pot_name.replace('Pot', ''))

            ttk.Button(top_frame, text="Establecer rango de transductor", style='Small.TButton',
                       command=lambda p=pot_name, i=pot_index: self.set_transducer_range(p, i)).pack(side=tk.LEFT, padx=2)


            fig = Figure(figsize=(5.5, 3.5), dpi=90)
            ax = fig.add_subplot(111)
            ax.set_xlabel('Tiempo (s)', fontsize=9)
            ax.set_ylabel('Valor', fontsize=9)
            ax.set_title(f"{pot_name.replace('Pot', 'Sensor ')}", fontsize=10, fontweight='bold', color=pot_info['color'])
            ax.grid(True, alpha=0.4, linestyle='--')
            ax.tick_params(labelsize=8)
            ax.yaxis.set_major_formatter(FormatStrFormatter('%.4f'))
            
            line, = ax.plot([], [], color=pot_info['color'], linewidth=2.5)
            
            canvas = FigureCanvasTkAgg(fig, master=pot_container)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            self.axes[pot_name] = ax
            self.lines[pot_name] = line
            self.canvases[pot_name] = canvas
            
            min_max_text = ax.text(0.02, 0.98, '', transform=ax.transAxes, fontsize=9,
                                   verticalalignment='top', bbox=dict(boxstyle='round,pad=0.3', fc='wheat', alpha=0.5))
            self.min_max_texts[pot_name] = min_max_text

        # Terminal Serial en la pantalla principal (al lado del Sensor 5)
        term_container = ttk.LabelFrame(graph_frame, text="Terminal Serial", padding="5")
        term_container.grid(row=2, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        term_frame = ttk.Frame(term_container)
        term_frame.pack(fill=tk.BOTH, expand=True)
        
        self.main_terminal_text = tk.Text(term_frame, wrap=tk.WORD, font=("Courier New", 9), bg="#2c3e50", fg="#ecf0f1", insertbackground="white", height=5)
        self.main_terminal_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        term_scroll = ttk.Scrollbar(term_frame, command=self.main_terminal_text.yview)
        term_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.main_terminal_text.config(yscrollcommand=term_scroll.set)
        
        input_frame = ttk.Frame(term_container)
        input_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.term_entry = ttk.Entry(input_frame, font=('Arial', 9))
        self.term_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.term_entry.bind('<Return>', self.send_terminal_command)
        
        ttk.Button(input_frame, text="Enviar", style='Small.TButton', command=self.send_terminal_command).pack(side=tk.RIGHT)
        ttk.Button(input_frame, text="Enter", style='Small.TButton', command=self.send_enter_main).pack(side=tk.RIGHT, padx=2)

    def send_calibration_command(self, cmd):
        if self.send_command(cmd + '\n'):
            if self.terminal_text:
                try:
                    self.terminal_text.insert(tk.END, f">>> {cmd}\n", "command_sent")
                    self.terminal_text.tag_config("command_sent", foreground="#3498db", font=("Courier New", 10, "bold"))
                    self.terminal_text.see(tk.END)
                except tk.TclError:
                    pass

    def send_terminal_command(self, event=None):
        cmd = self.term_entry.get()
        if cmd:
            if self.send_command(cmd + '\n'):
                self.main_terminal_text.insert(tk.END, f">>> {cmd}\n", "command_sent")
                self.main_terminal_text.tag_config("command_sent", foreground="#3498db", font=("Courier New", 9, "bold"))
                self.main_terminal_text.see(tk.END)
            self.term_entry.delete(0, tk.END)

    def send_enter_main(self):
        if self.send_command('\n'):
            self.main_terminal_text.insert(tk.END, ">>> [ENTER]\n", "command_sent")
            self.main_terminal_text.tag_config("command_sent", foreground="#3498db", font=("Courier New", 9, "bold"))
            self.main_terminal_text.see(tk.END)
        
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
        if self.send_command(f'R{pot_index},{new_range}\n'):
            messagebox.showinfo("Comando Enviado", f"Se envió el comando para establecer el rango a {new_range} mm.")
    
    def show_calibration_popup(self):
        popup = tk.Toplevel(self.root)
        popup.title("Panel de Calibración")
        popup.geometry("500x400")
        popup.transient(self.root)
        popup.grab_set()
        
        main_frame = ttk.Frame(popup)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        term_frame = ttk.Frame(main_frame)
        term_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.terminal_text = tk.Text(term_frame, wrap=tk.WORD, height=15, font=("Courier New", 10), bg="#2c3e50", fg="#ecf0f1", insertbackground="white")
        self.terminal_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(term_frame, command=self.terminal_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.terminal_text.config(yscrollcommand=scrollbar.set)
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=5, padx=5)

        def manual_calibration(idx):
            self.send_command(f'LBLINK{idx}\n')
            self.send_calibration_command('C')
            def finish_manual():
                self.send_calibration_command(str(idx))
                self.send_command(f'LON{idx}\n')
            popup.after(500, finish_manual)

        ttk.Label(btn_frame, text="Calibrar T:").pack(side=tk.LEFT, padx=(0, 5))
        for i in range(1, 6):
            ttk.Button(btn_frame, text=str(i), width=3, style='Small.TButton', command=lambda i=i: manual_calibration(i)).pack(side=tk.LEFT, padx=2)

        ttk.Button(btn_frame, text="Guardar (S)", style='Small.TButton', command=lambda: self.send_calibration_command('S')).pack(side=tk.LEFT, padx=(10, 2))
        ttk.Button(btn_frame, text="ENTER", style='Small.TButton', command=lambda: self.send_calibration_command('\n')).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(main_frame, text="Cerrar", style='Action.TButton', command=popup.destroy).pack(pady=10)

        selected_pots = [i for i in range(1, 6) if self.pot_data[f'Pot{i}']['enabled']]
        
        def run_calibration_step(pots_list):
            if not pots_list:
                messagebox.showinfo("Calibración", "Calibración automática completada.", parent=popup)
                return

            current_pot = pots_list[0]
            remaining_pots = pots_list[1:]
            
            self.send_command(f'LBLINK{current_pot}\n')
            self.send_calibration_command('C')
            
            def send_pot_index():
                self.send_calibration_command(str(current_pot))
                self.send_command(f'LON{current_pot}\n')
                popup.after(500, lambda: run_calibration_step(remaining_pots))
            
            popup.after(500, send_pot_index)

        if selected_pots:
            popup.after(500, lambda: run_calibration_step(selected_pots))

    def toggle_connection(self):
        if not self.is_reading:
            for pot_name in self.pot_data.keys():
                if pot_name in self.range_entries:
                    self.range_entries[pot_name].delete(0, tk.END)
                    self.range_entries[pot_name].insert(0, "...")

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
            time.sleep(2)
            self.is_reading = True
            self.connect_btn.config(text="Desconectar controlador", style='Disconnect.TButton')
            self.record_btn.config(state='normal')
            
            self.read_thread = threading.Thread(target=self.read_serial, daemon=True)
            self.read_thread.start()
            
            self.update_plot()
            for i in range(1, 6):
                if self.pot_data[f'Pot{i}']['enabled']:
                    self.send_command(f'LON{i}\n')
            
            self.show_calibration_popup()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo conectar: {str(e)}")
    
    def disconnect(self):
        self.is_reading = False
        if self.serial_conn:
            for i in range(1, 6):
                self.send_command(f'LOFF{i}\n')
            time.sleep(0.1)
            self.serial_conn.close()
            self.serial_conn = None
        self.connect_btn.config(text="Conectar controlador", style='Connect.TButton')

        self.is_recording_session = False
        self.record_btn.config(state='disabled', text="Iniciar captura de datos", style='Record.TButton')
    
    def toggle_pot(self, pot_name):
        is_enabled = self.pot_vars[pot_name].get()
        self.pot_data[pot_name]['enabled'] = is_enabled
        
        pot_index = int(pot_name.replace('Pot', ''))
        
        if is_enabled:
            self.send_command(f'E{pot_index}\n')
            self.send_command(f'LON{pot_index}\n')
        else:
            self.send_command(f'D{pot_index}\n')
            self.send_command(f'LOFF{pot_index}\n')

    def toggle_recording(self):
        self.is_recording_session = not self.is_recording_session
        if self.is_recording_session:
            self.start_time = time.time()
            
            for pot_info in self.pot_data.values():
                pot_info['values'].clear()
                pot_info['times'].clear()
                pot_info['all_values'].clear()
                pot_info['all_times'].clear()
                pot_info['min_session'] = None
                pot_info['max_session'] = None
            
            self.record_btn.config(text="Detener captura de datos", style='Disconnect.TButton')
            messagebox.showinfo("Grabación Iniciada", "Se ha iniciado la grabación. El tiempo se ha reiniciado a 0.")
        else:
            self.record_btn.config(text="Iniciar  captura de datos", style='Record.TButton')
            messagebox.showinfo("Grabación Detenida", "Se ha detenido la grabación. Los datos capturados están listos para ser exportados.")

    
    def read_serial(self):
        while self.is_reading:
            try:
                if self.serial_conn and self.serial_conn.in_waiting:
                    line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                    if not line:
                        continue

                    if line.startswith("Pot"):
                        self.process_data(line)
                    else:
                        if "Rango=" in line or "Rango T" in line:
                            try:
                                parts = line.split()
                                t_index = -1
                                r_value = ""
                                if line.startswith("T"):
                                    t_index = int(parts[0].replace('T', '').replace(':', ''))
                                    r_value = parts[-1].replace('mm', '').replace('Rango=', '')
                                elif "Rango T" in line:
                                    t_index = int(parts[2].replace('T', ''))
                                    r_value = parts[4]

                                if t_index != -1 and r_value:
                                    pot_name = f"Pot{t_index}"
                                    self.range_entries[pot_name].delete(0, tk.END)
                                    try:
                                        self.range_entries[pot_name].insert(0, f"{float(r_value):.4f}")
                                    except ValueError:
                                        self.range_entries[pot_name].insert(0, r_value)
                            except (ValueError, IndexError) as e:
                                print(f"No se pudo parsear la línea de rango: '{line}'. Error: {e}")

                        if self.terminal_text:
                            try:
                                self.terminal_text.insert(tk.END, line + '\n')
                                self.terminal_text.see(tk.END)
                            except tk.TclError:
                                pass
                        
                        if self.main_terminal_text:
                            try:
                                self.main_terminal_text.insert(tk.END, line + '\n')
                                self.main_terminal_text.see(tk.END)
                            except tk.TclError:
                                pass
            except Exception as e:
                print(f"Error leyendo serial: {e}")
            time.sleep(0.001)
    
    def process_data(self, line):
        try:
            parts = line.replace('|', ',').split(',')
            for part in parts:
                part = part.strip()
                if ':' in part:
                    split_part = part.split(':')
                    if len(split_part) != 2:
                        print(f"Skipping malformed data part: {part}")
                        continue
                    pot_name, value_str = [s.strip() for s in split_part]
                    
                    if pot_name in self.pot_data:
                        pot_info = self.pot_data[pot_name]

                        raw_value = float(value_str)

                        try:
                            # Obtener el rango máximo para invertir el valor (ej. 30 -> 0, 0 -> 30)
                            max_range = float(self.range_entries[pot_name].get())
                            processed_value = max_range - raw_value
                        except ValueError:
                            processed_value = raw_value

                        adjusted_value = processed_value - pot_info['offset']
                        current_time = time.time() - self.start_time
                        
                        pot_info['values'].append(adjusted_value)
                        pot_info['times'].append(current_time)
                        
                        if self.is_recording_session:
                            pot_info['all_values'].append(adjusted_value)
                            pot_info['all_times'].append(current_time)
                            
                            if pot_info['min_session'] is None or adjusted_value < pot_info['min_session']:
                                pot_info['min_session'] = adjusted_value
                            if pot_info['max_session'] is None or adjusted_value > pot_info['max_session']:
                                pot_info['max_session'] = adjusted_value
       
                        self.pot_labels[pot_name].config(text=f"{adjusted_value:.4f} mm")
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
                
                if x_data:
                    ax.set_xlim(0, max(10, x_data[-1] * 1.05))
                
                if y_data:
                    y_min, y_max = min(y_data), max(y_data)
                    margin = (y_max - y_min) * 0.1
                    if margin == 0: margin = 5.0
                    ax.set_ylim(y_min - margin, y_max + margin)
                
                line.set_visible(True)
                ax.set_facecolor('white')

                min_val = pot_info['min_session']
                max_val = pot_info['max_session']
                if min_val is not None and max_val is not None:
                    min_max_text.set_text(f'Min: {min_val:.4f}\nMax: {max_val:.4f}')
                else:
                    min_max_text.set_text('')
                min_max_text.set_visible(True)
            else:
                line.set_data([], [])
                line.set_visible(False)
                ax.set_facecolor('#f5f5f5')
                min_max_text.set_visible(False)
            
            canvas.draw()
        
        self.root.after(30, self.update_plot)
    
    def set_zero(self, pot_name):
        pot_info = self.pot_data[pot_name]
        btn = self.tare_buttons[pot_name]
        
        if not pot_info['is_tared']:
            if pot_info['values']:
                last_adjusted_value = list(pot_info['values'])[-1]
                pot_info['offset'] += last_adjusted_value
                pot_info['is_tared'] = True
                btn.config(text="Restaurar")
        else:
            pot_info['offset'] = 0
            pot_info['is_tared'] = False
            btn.config(text="Poner a 0")

    
    def export_csv(self):
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"datos_transductores_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        if not filename:
            return
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                headers = ['Tiempo (s)']
                enabled_pots = []
                
                for pot_name, pot_info in self.pot_data.items():
                    if pot_info['enabled']:
                        headers.append(pot_name.replace('Pot', 'Sensor '))
                        enabled_pots.append(pot_name)
                
                writer.writerow(headers)
                
                if not enabled_pots:
                    messagebox.showwarning("Advertencia", "No hay transductores habilitados para exportar.")
                    return

                first_pot_info = self.pot_data[enabled_pots[0]]
                max_len = len(first_pot_info['all_values'])

                for i in range(max_len):
                    row = [f"{first_pot_info['all_times'][i]:.4f}"]
                    for pot_name in enabled_pots:
                        pot_info = self.pot_data[pot_name]
                        if i < len(pot_info['all_values']):
                            row.append(f"{pot_info['all_values'][i]:.4f}")
                        else:
                            row.append('')
                    writer.writerow(row)
            
            messagebox.showinfo("Exportado", f"Datos exportados exitosamente:\n{filename}\n\nSe guardaron {len(enabled_pots)} transductores seleccionados.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar: {str(e)}")
    
    def generate_pdf_report(self):
        filename = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialfile=f"reporte_transductores_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        )
        
        if not filename:
            return
        
        try:
            doc = SimpleDocTemplate(filename, pagesize=letter)
            elements = []
            styles = getSampleStyleSheet()
            
            title = Paragraph("Reporte de Monitoreo de Transductores", styles['Title'])
            elements.append(title)
            elements.append(Spacer(1, 12))
            
            date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            date_p = Paragraph(f"<b>Fecha de generación:</b> {date_str}", styles['Normal'])
            elements.append(date_p)
            elements.append(Spacer(1, 8))
            
            enabled_list = [pot for pot, info in self.pot_data.items() if info['enabled']]
            enabled_text = f"<b>Transductores monitoreados:</b> {', '.join(enabled_list)}"
            elements.append(Paragraph(enabled_text, styles['Normal']))
            elements.append(Spacer(1, 20))
            
            table_data = [['Transductor', 'Valor Actual', 'Promedio', 'Mínimo', 'Máximo', 'Muestras']]
            
            for pot_name, pot_info in self.pot_data.items():
                if pot_info['enabled'] and pot_info['values']:
                    data = list(pot_info['values'])
                    avg = sum(data) / len(data)
                    min_val = min(data)
                    max_val = max(data)
                    current = data[-1]
                    
                    table_data.append([
                        f"{pot_name.replace('Pot', 'Sensor ')} (offset: {pot_info['offset']:.4f})",
                        f"{current:.4f}",
                        f"{avg:.4f}",
                        f"{min_val:.4f}",
                        f"{max_val:.4f}",
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
            
            temp_images = []
            
            elements.append(Paragraph("Gráficas Individuales", styles['Heading2']))
            elements.append(Spacer(1, 15))
            
            for pot_name, pot_info in self.pot_data.items():
                if pot_info['enabled'] and pot_info['values']:
                    fig_individual = Figure(figsize=(7, 3.5))
                    ax_individual = fig_individual.add_subplot(111)
                    
                    x_data = list(pot_info['times'])
                    y_data = list(pot_info['values'])
                    
                    ax_individual.plot(x_data, y_data, color=pot_info['color'], linewidth=2, label=pot_name.replace('Pot', 'Sensor '))
                    ax_individual.set_xlabel('Tiempo (s)', fontsize=10)
                    ax_individual.set_ylabel('Valor', fontsize=10)
                    ax_individual.set_title(f"{pot_name.replace('Pot', 'Sensor ')}", fontsize=12, fontweight='bold', color=pot_info['color'])
                    ax_individual.grid(True, alpha=0.4, linestyle='--')
                    ax_individual.yaxis.set_major_formatter(FormatStrFormatter('%.4f'))
                    
                    temp_img = f"temp_{pot_name}_{int(time.time())}.png"
                    fig_individual.savefig(temp_img, dpi=150, bbox_inches='tight')
                    temp_images.append(temp_img)
                    
                    elements.append(Image(temp_img, width=460, height=230))
                    elements.append(Spacer(1, 15))
                    
                    plt.close(fig_individual)
            
            doc.build(elements)
            
            for temp_img in temp_images:
                if os.path.exists(temp_img):
                    os.remove(temp_img)
            
            messagebox.showinfo("Reporte Generado", f"Reporte PDF generado exitosamente:\n{filename}\n\nIncluye gráficas de {len(enabled_list)} transductores seleccionados.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar el reporte: {str(e)}")

def main():
    root = tk.Tk()
    app = ArduinoMonitor(root)
    root.mainloop()

if __name__ == "__main__":
    main()