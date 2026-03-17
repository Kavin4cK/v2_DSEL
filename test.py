import serial, time
s = serial.Serial('/dev/ttyUSB0', 9600, timeout=5)
time.sleep(2)
s.reset_input_buffer()
print('Listening...')
for i in range(20):
    line = s.readline().decode('utf-8', errors='ignore').strip()
    print(repr(line))
s.close()
