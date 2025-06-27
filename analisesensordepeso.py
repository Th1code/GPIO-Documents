import sys
import serial
import numpy as np
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                            QWidget, QMessageBox)
from PyQt6.QtCore import QTimer
import pyqtgraph as pg
import struct
from collections import deque
from datetime import datetime, timedelta
import os
import csv
import time

class RealTimePlot(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Configurações de inicialização
        self.start_time = time.time()  # Tempo de início do programa
        self.initial_delay = 3  # Delay inicial de 3 segundos
        self.ignore_initial_data = True  # Flag para filtrar dados iniciais
        
        # Configuração da janela principal
        self.setWindowTitle("Sistema de Aquisição de Dados - HX711 (Com Filtro Inicial)")
        self.resize(1200, 800)
        
        # Configuração do sistema de arquivos
        self.setup_file_system()
        
        try:
            # Widget central e layout
            self.setup_ui()
            
            # Configuração dos dados
            self.buffer_size = 2000
            self.data = deque(maxlen=self.buffer_size)
            self.time_values = deque(maxlen=self.buffer_size)
            
            # Configuração serial
            self.setup_serial()
            
            # Configuração dos timers
            self.setup_timers()
            
            # Barra de status
            self.update_status("Inicializando... Aguardando estabilização inicial (3s)")
            
        except Exception as e:
            self.show_error(f"Erro na inicialização: {e}")
            self.close()

    def setup_file_system(self):
        """Configura o sistema de arquivos e CSV"""
        self.data_dir = "dados_hx711"
        os.makedirs(self.data_dir, exist_ok=True)
        self.csv_file = None
        self.csv_writer = None
        self.file_start_time = None
        self.file_duration = timedelta(minutes=30)  # Novo arquivo a cada 30 minutos
        self.init_csv_file()

    def setup_ui(self):
        """Configura a interface do usuário"""
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)
        
        # 1. Gráfico principal
        self.setup_main_plot()
    

    def setup_main_plot(self):
        """Configura o gráfico principal"""
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_curve = self.plot_widget.plot(
            pen=pg.mkPen(color='b', width=2),
            name="Valores HX711"
        )
        self.plot_widget.setLabel('left', 'Valor Bruto', units='counts')
        self.plot_widget.setLabel('bottom', 'Amostras')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.addLegend()
        self.layout.addWidget(self.plot_widget)

    def setup_histogram(self):
        """Configura o gráfico de histograma"""
        self.hist_widget = pg.PlotWidget()
        self.hist_widget.setBackground('w')
        self.hist_plot = self.hist_widget.plot(
            stepMode=True,
            fillLevel=0,
            brush=(0, 0, 255, 150),
            name="Distribuição"
        )
        self.hist_widget.setLabel('left', 'Frequência')
        self.hist_widget.setLabel('bottom', 'Valor')
        self.layout.addWidget(self.hist_widget)

    def setup_serial(self):
        """Configura a comunicação serial"""
        try:
            self.ser = serial.Serial('COM7', 500000, timeout=0.01)
            self.ser.reset_input_buffer()
            self.update_status("Porta serial conectada - Aguardando estabilização inicial")
        except serial.SerialException as e:
            self.show_error(f"Erro Serial: {str(e)}")
            raise

    def setup_timers(self):
        """Configura os timers de atualização"""
        # Timer para atualização do gráfico
        self.plot_timer = QTimer()
        self.plot_timer.timeout.connect(self.update_plot)
        self.plot_timer.start(30)  # ~33 FPS
        
        # Timer para estatísticas e histograma
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.start(500)  # Atualiza a cada 500ms
        
        # Timer para verificar rotação de arquivo
        self.file_timer = QTimer()
        self.file_timer.timeout.connect(self.check_file_rotation)
        self.file_timer.start(60000)  # Verifica a cada minuto

    def init_csv_file(self):
        """Inicializa um novo arquivo CSV com timestamp"""
        try:
            if self.csv_file:
                self.csv_file.close()
                
            filename = os.path.join(
                self.data_dir,
                f"dados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
            self.csv_file = open(filename, 'w', newline='')
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow(["timestamp", "value"])  # Cabeçalho
            self.file_start_time = datetime.now()
            self.update_status(f"Novo arquivo criado: {filename}")
        except Exception as e:
            self.show_error(f"Erro ao criar arquivo CSV: {str(e)}")

    def update_plot(self):
        """Atualiza o gráfico principal com novos dados"""
        try:
            # Verifica se já passaram os 3 segundos iniciais
            if self.ignore_initial_data:
                elapsed = time.time() - self.start_time
                if elapsed >= self.initial_delay:
                    self.ignore_initial_data = False
                    self.update_status("Filtro inicial removido - Coletando dados...")
                else:
                    # Descarta quaisquer dados recebidos durante o período de filtro
                    if self.ser.in_waiting >= 4:
                        self.ser.read(self.ser.in_waiting)
                    return
            
            # Processa os dados apenas se o filtro estiver desativado
            if not self.ignore_initial_data and self.ser.in_waiting >= 4:
                raw_data = self.ser.read(self.ser.in_waiting)
                
                for i in range(0, len(raw_data), 4):
                    if i + 4 > len(raw_data):
                        break
                    sample = struct.unpack('<i', raw_data[i:i+4])[0]
                    self.data.append(sample)
                    self.time_values.append(len(self.data))
                    self.save_to_csv(sample)
                
                self.plot_curve.setData(
                    x=list(self.time_values),
                    y=list(self.data)
                )
                
        except Exception as e:
            self.update_status(f"Erro na atualização do gráfico: {str(e)}")

    def save_to_csv(self, sample):
        """Salva uma amostra no arquivo CSV"""
        try:
            if self.csv_writer:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
                self.csv_writer.writerow([timestamp, sample])
        except Exception as e:
            self.show_error(f"Erro ao salvar dados: {str(e)}")
            try:
                self.init_csv_file()  # Tenta recuperar
            except:
                self.csv_writer = None  # Desativa salvamento

    def check_file_rotation(self):
        """Verifica se precisa rotacionar o arquivo baseado no tempo decorrido"""
        if self.ignore_initial_data:
            return
            
        try:
            if self.file_start_time and (datetime.now() - self.file_start_time) >= self.file_duration:
                self.init_csv_file()
        except Exception as e:
            print(f"Erro na rotação de arquivo: {e}")

    def update_stats(self):
        """Atualiza estatísticas e histograma"""
        if self.ignore_initial_data:
            elapsed = time.time() - self.start_time
            remaining = max(0, self.initial_delay - elapsed)
            self.update_status(f"Aguardando estabilização: {remaining:.1f}s restantes")
            return
            
        if len(self.data) > 10:
            try:
                data_array = np.array(self.data)
                y, x = np.histogram(data_array, bins=50)
                self.hist_plot.setData(x, y)
                
                time_elapsed = datetime.now() - self.file_start_time if self.file_start_time else timedelta(0)
                stats_text = (
                    f"Média: {np.mean(data_array):.1f} | "
                    f"Std: {np.std(data_array):.1f} | "
                    f"Min: {np.min(data_array)} | "
                    f"Max: {np.max(data_array)} | "
                    f"Amostras: {len(self.data)} | "
                    f"Tempo no arquivo: {str(time_elapsed).split('.')[0]}"
                )
                self.update_status(stats_text)
                
            except Exception as e:
                print(f"Erro no cálculo de estatísticas: {e}")

    def update_status(self, message):
        """Atualiza a barra de status"""
        self.statusBar().showMessage(message)

    def show_error(self, message):
        """Mostra mensagem de erro"""
        QMessageBox.critical(self, "Erro", message)
        self.update_status(message)

    def closeEvent(self, event):
        """Garante o fechamento seguro"""
        try:
            self.plot_timer.stop()
            self.stats_timer.stop()
            self.file_timer.stop()
            if hasattr(self, 'ser') and self.ser.is_open:
                self.ser.close()
            if self.csv_file:
                self.csv_file.close()
        except Exception as e:
            print(f"Erro ao fechar: {e}")
        finally:
            event.accept()

if __name__ == '__main__':
    try:
        app = QApplication(sys.argv)
        app.setStyle('Fusion')
        
        window = RealTimePlot()
        window.show()
        
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"Erro fatal: {e}")
        sys.exit(1)