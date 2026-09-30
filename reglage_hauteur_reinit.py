from serial import Serial
import time 


dev = Serial('/dev/ttyACM0', baudrate=115200)

dev.write(b'G28 Z0\r\n')
dev.write(b'G0 X0 Y0 Z120\r\n')

dev.close()

