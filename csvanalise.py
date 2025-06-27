import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button
import os
import glob
from datetime import datetime
import tkinter as tk
from tkinter import filedialog

class CSVDataAnalyzer:
    def __init__(self):
        self.data = None
        self.current_file = None
        self.fig = None
        self.ax = None
        self.time_window = 1000  # Janela de tempo inicial para visualização
        
        # Configurar interface gráfica para seleção de arquivo
        root = tk.Tk()
        root.withdraw()
        
        # Pedir para selecionar um arquivo CSV
        file_path = filedialog.askopenfilename(
            initialdir="dados_hx711",
            title="Selecione um arquivo CSV para análise",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*"))
        )
        
        if not file_path:
            print("Nenhum arquivo selecionado. Encerrando.")
            exit()
            
        self.current_file = file_path
        self.load_data(file_path)
        self.setup_plot()
        self.show_stats()
        plt.show()

    def load_data(self, file_path):
        """Carrega os dados do arquivo CSV"""
        try:
            self.data = pd.read_csv(file_path, parse_dates=['timestamp'])
            print(f"Dados carregados: {len(self.data)} amostras")
            
            # Calcular diferença de tempo entre amostras
            self.data['time_diff'] = self.data['timestamp'].diff().dt.total_seconds()
            self.data['elapsed_time'] = self.data['time_diff'].cumsum().fillna(0)
            
            # Calcular variações (derivada numérica)
            self.data['variation'] = self.data['value'].diff()
            
        except Exception as e:
            print(f"Erro ao carregar arquivo: {e}")
            exit()

    def setup_plot(self):
        """Configura o gráfico interativo de variações temporais"""
        self.fig, self.ax = plt.subplots(figsize=(12, 6))
        plt.subplots_adjust(bottom=0.25)
        
        # Gráfico principal (variações ao longo do tempo)
        self.line, = self.ax.plot(
            self.data['elapsed_time'][:self.time_window], 
            self.data['variation'][:self.time_window],
            'b-', linewidth=1
        )
        self.ax.set_title(f"Variações dos Dados HX711 - {os.path.basename(self.current_file)}")
        self.ax.set_xlabel('Tempo (s)')
        self.ax.set_ylabel('Variação (diferença entre amostras)')
        self.ax.grid(True)
        
        # Adicionar controles deslizantes
        ax_slider = plt.axes([0.2, 0.1, 0.6, 0.03])
        self.slider = Slider(
            ax_slider, 
            'Janela (amostras)', 
            100, 
            len(self.data), 
            valinit=self.time_window
        )
        self.slider.on_changed(self.update_plot)
        
        # Adicionar botões
        ax_prev = plt.axes([0.7, 0.05, 0.1, 0.04])
        ax_next = plt.axes([0.81, 0.05, 0.1, 0.04])
        ax_stats = plt.axes([0.1, 0.05, 0.15, 0.04])
        
        self.prev_button = Button(ax_prev, 'Anterior')
        self.prev_button.on_clicked(self.prev_file)
        
        self.next_button = Button(ax_next, 'Próximo')
        self.next_button.on_clicked(self.next_file)
        
        self.stats_button = Button(ax_stats, 'Estatísticas')
        self.stats_button.on_clicked(lambda event: self.show_stats(show_window=True))

    def update_plot(self, val):
        """Atualiza o gráfico com base no valor do slider"""
        self.time_window = int(val)
        self.line.set_data(
            self.data['elapsed_time'][:self.time_window], 
            self.data['variation'][:self.time_window]
        )
        self.ax.relim()
        self.ax.autoscale_view()
        self.fig.canvas.draw_idle()

    def show_stats(self, show_window=False):
        """Calcula e exibe estatísticas das variações"""
        if self.data is None:
            return
            
        stats = {
            "Arquivo": os.path.basename(self.current_file),
            "Total de amostras": len(self.data),
            "Duração (s)": self.data['elapsed_time'].iloc[-1],
            "Taxa média (Hz)": len(self.data) / self.data['elapsed_time'].iloc[-1],
            "Média das variações": np.mean(self.data['variation'].dropna()),
            "Desvio padrão das variações": np.std(self.data['variation'].dropna()),
            "Variação mínima": np.min(self.data['variation'].dropna()),
            "Variação máxima": np.max(self.data['variation'].dropna()),
            "Primeiro timestamp": self.data['timestamp'].iloc[0],
            "Último timestamp": self.data['timestamp'].iloc[-1]
        }
        
        if show_window:
            stats_text = "\n".join([f"{k}: {v}" for k, v in stats.items()])
            plt.figure(figsize=(8, 4))
            plt.axis('off')
            plt.text(0.1, 0.5, stats_text, fontfamily='monospace', fontsize=10)
            plt.title("Estatísticas das Variações")
            plt.show()
        else:
            print("\nEstatísticas das variações:")
            for k, v in stats.items():
                print(f"{k}: {v}")

    def find_adjacent_files(self):
        """Encontra arquivos adjacentes na mesma pasta"""
        dir_path = os.path.dirname(self.current_file)
        csv_files = sorted(glob.glob(os.path.join(dir_path, '*.csv')))
        
        if not csv_files:
            return None, None
            
        current_index = csv_files.index(self.current_file)
        prev_file = csv_files[current_index - 1] if current_index > 0 else None
        next_file = csv_files[current_index + 1] if current_index < len(csv_files) - 1 else None
        
        return prev_file, next_file

    def prev_file(self, event):
        """Carrega o arquivo anterior"""
        prev_file, _ = self.find_adjacent_files()
        if prev_file:
            self.current_file = prev_file
            self.reload_data()

    def next_file(self, event):
        """Carrega o próximo arquivo"""
        _, next_file = self.find_adjacent_files()
        if next_file:
            self.current_file = next_file
            self.reload_data()

    def reload_data(self):
        """Recarrega os dados e atualiza o gráfico"""
        self.load_data(self.current_file)
        
        # Atualizar gráfico de variações
        self.line.set_data(
            self.data['elapsed_time'][:self.time_window], 
            self.data['variation'][:self.time_window]
        )
        self.ax.relim()
        self.ax.autoscale_view()
        self.ax.set_title(f"Variações dos Dados HX711 - {os.path.basename(self.current_file)}")
        
        # Atualizar slider
        self.slider.valmax = len(self.data)
        self.slider.ax.set_xlim(self.slider.valmin, self.slider.valmax)
        
        self.fig.canvas.draw_idle()
        self.show_stats()

if __name__ == "__main__":
    analyzer = CSVDataAnalyzer()