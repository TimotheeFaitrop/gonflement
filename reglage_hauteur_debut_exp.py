from serial import Serial
import time 


def send_code(dev, cmd):
	dev.write((cmd + '\r\n').encode())

	while True:
		line = dev.readline().decode(errors='ignore').strip()
		if line :
			print(">>", line)
		if line.lower().startswith('ok'):
			break

dev = Serial('/dev/ttyACM0', baudrate=115200)
running = True




send_code(dev, 'G28 Z0')
send_code(dev, 'G0 X0 Y0 Z70')
dev.close()





