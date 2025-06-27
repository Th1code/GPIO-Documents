import serial
import time
import struct
from collections import deque

# Configurações da porta serial (ajuste conforme necessário)
PORT = 'COM3'          # Substitua pela sua porta
BAUDRATE = 500000      # Deve corresponder à configuração do ESP32
SAMPLE_SIZE = 4        # Tamanho de cada amostra em bytes (4 para int32)
TIMEOUT = 0.1          # Timeout para leitura serial

def main():
    ser = None
    try:
        # Configuração otimizada da porta serial
        ser = serial.Serial(
            port=PORT,
            baudrate=BAUDRATE,
            timeout=TIMEOUT,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE
        )
        ser.reset_input_buffer()
        
        print(f"Monitorando taxa de amostragem na porta {PORT}...")
        print("Configuração: {}-{}-{}-{}".format(
            ser.bytesize, ser.parity, ser.stopbits, ser.baudrate))
        print("Pressione Ctrl+C para encerrar\n")
        
        # Variáveis para cálculo da taxa
        sample_count = 0
        window_size = 1000
        time_window = deque(maxlen=window_size)
        start_time = time.time()
        last_print = start_time
        buffer = bytearray()

        while True:
            # Lê todos os dados disponíveis
            data = ser.read(ser.in_waiting or 1)
            if data:
                buffer.extend(data)
                
                # Processa amostras completas
                while len(buffer) >= SAMPLE_SIZE:
                    # Extrai uma amostra (4 bytes)
                    sample = buffer[:SAMPLE_SIZE]
                    buffer = buffer[SAMPLE_SIZE:]
                    
                    # Converte de little-endian para inteiro
                    try:
                        value = struct.unpack('<i', sample)[0]
                    except struct.error as e:
                        print(f"\nErro ao decodificar: {e}")
                        continue
                    
                    sample_count += 1
                    current_time = time.time()
                    time_window.append(current_time)
                    
                    # Exibe a taxa periodicamente
                    if current_time - last_print >= 1.0:  # Atualiza a cada 1 segundo
                        if len(time_window) > 1:
                            elapsed = time_window[-1] - time_window[0]
                            rate = (len(time_window) - 1) / elapsed if elapsed > 0 else 0
                            print(f"Taxa: {rate:.2f} Hz | Total: {sample_count} | Último valor: {value}", 
                                  end='\r')
                        last_print = current_time
            
            # Pequena pausa para evitar uso excessivo da CPU
            time.sleep(0.001)

    except KeyboardInterrupt:
        print("\nEncerrando monitoramento...")
    except Exception as e:
        print(f"\nErro: {str(e)}")
    finally:
        if ser and ser.is_open:
            ser.close()
        print("\nPorta serial fechada.")

if __name__ == '__main__':
    main()