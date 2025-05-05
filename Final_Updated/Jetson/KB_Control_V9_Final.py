import os, sys, ctypes, time
import dynamixel_sdk as dxl 
import numpy as np
import keyboard as kb



# Final code for Research Exhibit with motor soft reboot and dance command included


class HexapodController:
    def __init__(self, device_name, baudrate, edge_gaits, vertex_gaits, dance_gaits):
        self.device_name = device_name
        self.baudrate = baudrate
        self.edge_gaits = edge_gaits  # (initial, continuous, final)
        self.vertex_gaits = vertex_gaits  # (initial, continuous, final)
        self.dance_gaits = dance_gaits
        self.port = dxl.PortHandler(self.device_name)
        self.packet = dxl.PacketHandler(2.0)
        self.group_sync_write = None
        self.gait_angles = None
        self.setup_motors()
        self.action=None

    def setup_motors(self):
        if not self.port.openPort():
            raise Exception("Failed to open port")
        if not self.port.setBaudRate(self.baudrate):
            raise Exception("Failed to set baudrate")
        self.init_motors()

    def init_motors(self):
        try:
            self.packet.write1ByteTxOnly(self.port, 254, 65, 0)
            self.packet.write1ByteTxOnly(self.port, 254, 64, 1)
            time.sleep(0.02)
            self.packet.write2ByteTxOnly(self.port, 254, 84, 800)  # P gain
            self.packet.write2ByteTxOnly(self.port, 254, 82, 0)    # I gain
            self.packet.write2ByteTxOnly(self.port, 254, 80, 64)   # D gain
            time.sleep(0.02)
            self.packet.write2ByteTxOnly(self.port, 19, 82, 100)    # I gain
            self.packet.write2ByteTxOnly(self.port, 19, 80, 50)   # D gain
            time.sleep(0.02)
            self.packet.write4ByteTxOnly(self.port, 19, 112, 30) #Set Cam motor velocity
            time.sleep(0.02)
            self.group_sync_write = dxl.GroupSyncWrite(self.port, self.packet, 116, 4)
            time.sleep(0.02)
            self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
            time.sleep(0.02)
        except Exception as e:
            print(f"Error configuring motor parameters: {e}")

    def reboot(self):
        self.packet.reboot(self.port, 254)
        time.sleep(0.5)
        self.init_motors()
        print("Reboot Complete")

    # def get_current(self):
    #     # m_id = input("Which Motor to read current on?\n\b")
    #     while (kb.is_pressed('i')):
    #         time.sleep(0.1)
    #         print(self.packet.read2ByteTxRx(self.port,12,126))


    def load_gait_file(self, file):
        try:
            self.gait_angles = np.load(file, allow_pickle=True)
            print(f"Loaded gait file with {self.gait_angles.shape[0]} frames")
        except Exception as e:
            print(f"Error loading gait file: {e}")

    def walk(self, seq, gaits, keys, delay=0.005):
        count = 0
        stat = self.packet.read1ByteTxRx(self.port,19,122)
        while count < 8:
            time.sleep(0.03)
            stat = self.packet.read1ByteTxRx(self.port,19,122)
            if stat[0] == 0:
                count+=1
            else:
                count = 0
        try:
            # Ensure `keys` is either a string (single key) or tuple (multiple keys)
            if not isinstance(keys, (str, tuple)):
                raise ValueError("Keys must be a string or a tuple of key names.")

            # Normalize keys to a tuple for uniform handling
            if isinstance(keys, str):
                keys = (keys,)  # Convert single key to a tuple

            # Initial gait
            self.load_gait_file(gaits[0])
            for frame in range(self.gait_angles.shape[0]):
                self.execute_frame(seq, frame, delay)

            # Continuous gait loop
            self.load_gait_file(gaits[1])
            while all(kb.is_pressed(key) for key in keys):  # Check all keys are pressed
                for frame in range(self.gait_angles.shape[0]):
                    self.execute_frame(seq, frame, delay)

            # Final gait
            self.load_gait_file(gaits[2])
            for frame in range(self.gait_angles.shape[0]):
                # print(self.gait_angles[frame, :])
                self.execute_frame(seq, frame, delay)

        except Exception as e:
            print(f"Error during walking: {e}")


    def execute_frame(self, seq, frame, delay):
        self.group_sync_write.clearParam()
        for motor_id in range(18):
            angle = int(self.gait_angles[frame, motor_id])
            angle = max(0, min(4095, angle))
            param = [
                dxl.DXL_LOBYTE(dxl.DXL_LOWORD(angle)),
                dxl.DXL_HIBYTE(dxl.DXL_LOWORD(angle)),
                dxl.DXL_LOBYTE(dxl.DXL_HIWORD(angle)),
                dxl.DXL_HIBYTE(dxl.DXL_HIWORD(angle))
            ]
            self.group_sync_write.addParam(seq[motor_id], param)
        self.group_sync_write.txPacket()
        time.sleep(delay)

    def move_north(self):
        seq = (6, 12, 18, 1, 7, 13, 2, 8, 14, 3, 9, 15, 4, 10, 16, 5, 11, 17)
        # seq = (4, 10, 16, 5, 11, 17, 6, 12, 18, 1, 7, 13, 2, 8, 14, 3, 9, 15)
        self.packet.write4ByteTxOnly(self.port, 19, 116, 2048)
        # time.sleep(0.5)
        self.walk(seq, self.edge_gaits, 'w')

    def move_dance_action(self):
        seq = (6, 12, 18, 1, 7, 13, 2, 8, 14, 3, 9, 15, 4, 10, 16, 5, 11, 17)
        # seq = (4, 10, 16, 5, 11, 17, 6, 12, 18, 1, 7, 13, 2, 8, 14, 3, 9, 15)
        self.packet.write4ByteTxOnly(self.port, 19, 116, 2048)
        # time.sleep(0.5)
        self.walk(seq, self.dance_gaits, 'g')

    def move_south(self):
        # seq = (1, 7, 13, 2, 8, 14, 3, 9, 15, 4, 10, 16, 5, 11, 17, 6, 12, 18)
        seq = (3, 9, 15, 4, 10, 16, 5, 11, 17, 6, 12, 18, 1, 7, 13, 2, 8, 14)
        self.packet.write4ByteTxOnly(self.port, 19, 116, 0)
        # time.sleep(0.5)
        self.walk(seq, self.edge_gaits, 'x')

    def move_west(self):
        seq = (3, 9,15, 4, 10, 16, 5, 11, 17, 6, 12, 18,1, 7, 13, 2, 8, 14)
        self.packet.write4ByteTxOnly(self.port, 19, 116, 3072)
        # time.sleep(0.5)
        self.walk(seq, self.vertex_gaits, 'a')

    def move_east(self):
        seq = (6, 12, 18, 1, 7, 13, 2, 8, 14, 3, 9, 15, 4, 10, 16, 5, 11, 17)
        self.packet.write4ByteTxOnly(self.port, 19, 116, 1024)
        # time.sleep(0.5)
        self.walk(seq, self.vertex_gaits, 'd')

    def move_north_east(self):
        # seq = (3, 9, 15, 4, 10, 16, 5, 11, 17, 6, 12, 18, 1, 7, 13, 2, 8, 14)
        seq = (5, 11, 17, 6, 12, 18, 1, 7, 13, 2, 8, 14, 3, 9, 15, 4, 10, 16)
        self.packet.write4ByteTxOnly(self.port, 19, 116, 1365)
        # time.sleep(0.5)
        self.walk(seq, self.edge_gaits, 'e')

    def move_south_east(self):
        # seq = (2, 8, 14, 3, 9, 15, 4, 10, 16, 5, 11, 17, 6, 12, 18, 1, 7, 13)
        seq = (4, 10, 16, 5, 11, 17, 6, 12, 18, 1, 7, 13, 2, 8, 14, 3, 9, 15)
        self.packet.write4ByteTxOnly(self.port, 19, 116, 682)
        # time.sleep(0.5)
        self.walk(seq, self.edge_gaits, 'c')

    def move_north_west(self):
        # seq = (5, 11, 17, 6, 12, 18, 1, 7, 13, 2, 8, 14, 3, 9, 15, 4, 10, 16)
        seq = (1, 7, 13, 2, 8, 14, 3, 9, 15, 4, 10, 16, 5, 11, 17, 6, 12, 18)
        self.packet.write4ByteTxOnly(self.port, 19, 116, 2730)
        # time.sleep(0.5)
        self.walk(seq, self.edge_gaits, 'q')

    def move_south_west(self):
        # seq = (6, 12, 18, 1, 7, 13, 2, 8, 14, 3, 9, 15, 4, 10, 16, 5, 11, 17)
        seq = (2, 8, 14, 3, 9, 15, 4, 10, 16, 5, 11, 17, 6, 12, 18, 1, 7, 13)
        self.packet.write4ByteTxOnly(self.port, 19, 116, 3383)
        # time.sleep(0.5)
        self.walk(seq, self.edge_gaits, 'z')

    def rotate_left(self):
        p1 = (7, 9, 11)
        p2 = (8, 10, 12)
        d = 0.02
        d2 = 0.5
        if self.action != 5:
            self.action = 5
            time.sleep(0.2)
        try:
            while kb.is_pressed('l'):
                for i in p1:
                    if not kb.is_pressed('l'):
                        print("Key released, stopping turn left action")
                        self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
                        return
                    self.packet.write4ByteTxOnly(self.port, i, 116, 1800)
                    time.sleep(d)
                    self.packet.write4ByteTxOnly(self.port, i + 6, 116, 1800)
                    time.sleep(d)
                time.sleep(0.5)
                for i in p2:
                    if not kb.is_pressed('l'):
                        print("Key released, stopping turn left action")
                        self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
                        return
                    self.packet.write4ByteTxOnly(self.port, i - 6, 116, 1850)
                    time.sleep(d)
                time.sleep(d2)
                for i in p1:
                    if not kb.is_pressed('l'):
                        print("Key released, stopping turn left action")
                        self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
                        return
                    self.packet.write4ByteTxOnly(self.port, i, 116, 2048)
                    time.sleep(d)
                    self.packet.write4ByteTxOnly(self.port, i + 6, 116, 2048)
                    time.sleep(d)
                time.sleep(0.5)
                time.sleep(d2)
                for i in p2:
                    if not kb.is_pressed('l'):
                        print("Key released, stopping turn left action")
                        self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
                        return
                    self.packet.write4ByteTxOnly(self.port, i, 116, 1800)
                    time.sleep(d)
                    self.packet.write4ByteTxOnly(self.port, i + 6, 116, 1800)
                    time.sleep(d)
                time.sleep(0.5)
                for i in p2:
                    if not kb.is_pressed('l'):
                        print("Key released, stopping turn left action")
                        self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
                        return
                    self.packet.write4ByteTxOnly(self.port, i - 6, 116, 2048)
                    time.sleep(d)
                time.sleep(d2)
                self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
                time.sleep(d2)
        except KeyboardInterrupt:
            print("Turn left action interrupted")
        except Exception as e:
            print(f"Error during turn left action: {e}")

    def rotate_right(self):
        p1 = (7, 9, 11)
        p2 = (8, 10, 12)
        d = 0.02
        d2 = 0.5
        if self.action != 6:
            self.action = 6
            time.sleep(0.2)
        try:
            while kb.is_pressed('r'):
                for i in p1:
                    if not kb.is_pressed('r'):
                        print("Key released, stopping turn right action")
                        self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
                        return
                    self.packet.write4ByteTxOnly(self.port, i, 116, 1800)
                    time.sleep(d)
                    self.packet.write4ByteTxOnly(self.port, i + 6, 116, 1800)
                    time.sleep(d)
                time.sleep(0.5)
                for i in p2:
                    if not kb.is_pressed('r'):
                        print("Key released, stopping turn right action")
                        self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
                        return
                    self.packet.write4ByteTxOnly(self.port, i - 6, 116, 2300)
                    time.sleep(d)
                time.sleep(d2)
                for i in p1:
                    if not kb.is_pressed('r'):
                        print("Key released, stopping turn right action")
                        self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
                        return
                    self.packet.write4ByteTxOnly(self.port, i, 116, 2048)
                    time.sleep(d)
                    self.packet.write4ByteTxOnly(self.port, i + 6, 116, 2048)
                    time.sleep(d)
                time.sleep(0.5)
                time.sleep(d2)
                for i in p2:
                    if not kb.is_pressed('r'):
                        print("Key released, stopping turn right action")
                        self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
                        return
                    self.packet.write4ByteTxOnly(self.port, i, 116, 1800)
                    time.sleep(d)
                    self.packet.write4ByteTxOnly(self.port, i + 6, 116, 1800)
                    time.sleep(d)
                time.sleep(0.5)
                for i in p2:
                    if not kb.is_pressed('r'):
                        print("Key released, stopping turn right action")
                        self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
                        return
                    self.packet.write4ByteTxOnly(self.port, i - 6, 116, 2048)
                    time.sleep(d)
                time.sleep(d2)
                self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
                time.sleep(d2)
        except KeyboardInterrupt:
            print("Turn right action interrupted")
        except Exception as e:
            print(f"Error during turn right action: {e}")

    def perform_pushup_action(self):
        p2 = (7, 9, 11, 8, 10, 12)
        d = 0.01
        if self.action != 2:

            self.packet.write2ByteTxOnly(self.port, 254, 84, 800)  # P gain
            self.packet.write2ByteTxOnly(self.port, 254, 82, 0)    # I gain
            self.packet.write2ByteTxOnly(self.port, 254, 80, 15)   # D gain
            self.action = 2
            time.sleep(0.2)
        try:
            while kb.is_pressed('p'):
                for i in p2:
                    if not kb.is_pressed('p'):
                        print("Key released, stopping pushup action")
                        self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
                        return
                    self.packet.write4ByteTxOnly(self.port, i, 116, 2800)
                    time.sleep(d)
                    self.packet.write4ByteTxOnly(self.port, i + 6, 116, 1200)
                    time.sleep(d)
                time.sleep(2)
                for i in p2:
                    if not kb.is_pressed('p'):
                        print("Key released, stopping pushup action")
                        self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
                        return
                    self.packet.write4ByteTxOnly(self.port, i, 116, 2048)
                    time.sleep(d)
                    self.packet.write4ByteTxOnly(self.port, i + 6, 116, 2048)
                    time.sleep(d)
                time.sleep(2)
        except KeyboardInterrupt:
            print("Pushup action interrupted")
        except Exception as e:
            print(f"Error during pushup action: {e}")

    def perform_wave_action(self):
        # p2 = (16, 17)
        # p1 = (13, 14)
        # d = 0.005
        if self.action != 3:
            self.packet.write2ByteTxOnly(self.port, 254, 84, 600)  # P gain
            self.packet.write2ByteTxOnly(self.port, 254, 82, 0)    # I gain
            self.packet.write2ByteTxOnly(self.port, 254, 80, 15)   # D gain
            self.action = 3
            time.sleep(0.2)
            # time.sleep(0.01)
            self.packet.write4ByteTxOnly(self.port, 18, 112, 140)
            time.sleep(0.01)
            self.packet.write4ByteTxOnly(self.port,6,116,2370)
            time.sleep(0.01)
            self.packet.write4ByteTxOnly(self.port,12,116,1676)
            time.sleep(0.01)
        try:
            while kb.is_pressed('h'):
                self.packet.write4ByteTxOnly(self.port,18,116,1500)
                time.sleep(0.4)
                self.packet.write4ByteTxOnly(self.port,18,116,900)
                time.sleep(0.4)
            self.packet.write4ByteTxOnly(self.port, 18, 112, 0)
                # time.sleep(0.01)
            time.sleep(0.2)
            self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
        except KeyboardInterrupt:
            print("Wave action interrupted")
        except Exception as e:
            print(f"Error during wave action: {e}")

    def perform_dance_action(self):
        p1 = (7, 9, 11)
        p2 = (8, 10, 12)
        d = 0.02
        d2 = 0.5
        if self.action != 4:
            self.packet.write2ByteTxOnly(self.port, 254, 84, 600)  # P gain
            self.packet.write2ByteTxOnly(self.port, 254, 82, 0)    # I gain
            self.packet.write2ByteTxOnly(self.port, 254, 80, 15)   # D gain
            self.action = 4
            time.sleep(0.2)
        try:
            while kb.is_pressed('g'):
                for i in p1:
                    if not kb.is_pressed('g'):
                        print("Key released, stopping dance action")
                        self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
                        return
                    self.packet.write4ByteTxOnly(self.port, i, 116, 1500)
                    time.sleep(d)
                    self.packet.write4ByteTxOnly(self.port, i + 6, 116, 1100)
                    time.sleep(d)
                time.sleep(0.5)
                for i in p2:
                    if not kb.is_pressed('g'):
                        print("Key released, stopping dance action")
                        self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
                        return
                    self.packet.write4ByteTxOnly(self.port, i - 6, 116, 1550)
                    time.sleep(d)
                time.sleep(0.5)
                for i in p2:
                    if not kb.is_pressed('g'):
                        print("Key released, stopping dance action")
                        self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
                        return
                    self.packet.write4ByteTxOnly(self.port, i - 6, 116, 2048)
                    time.sleep(d)
                time.sleep(d2)
                self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
                time.sleep(d2)
                for i in p2:
                    if not kb.is_pressed('g'):
                        print("Key released, stopping dance action")
                        self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
                        return
                    self.packet.write4ByteTxOnly(self.port, i, 116, 1500)
                    time.sleep(d)
                    self.packet.write4ByteTxOnly(self.port, i + 6, 116, 1100)
                    time.sleep(d)
                time.sleep(0.5)
                for i in p1:
                    if not kb.is_pressed('g'):
                        print("Key released, stopping dance action")
                        self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
                        return
                    self.packet.write4ByteTxOnly(self.port, i - 6, 116, 2600)
                    time.sleep(d)
                time.sleep(d2)
                for i in p1:
                    if not kb.is_pressed('g'):
                        print("Key released, stopping dance action")
                        self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
                        return
                    self.packet.write4ByteTxOnly(self.port, i - 6, 116, 2048)
                    time.sleep(d)
                time.sleep(d2)
                self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
                time.sleep(d2)
        except KeyboardInterrupt:
            print("Dance action interrupted")
        except Exception as e:
            print(f"Error during dance action: {e}")

    def perform_alt_action(self):
        p1 = (7, 9, 11)
        p2 = (8, 10, 12)
        d = 0.02
        d2 = 0.5

        # Set PID values
        self.packet.write2ByteTxOnly(self.port, 254, 84, 600)  # P gain
        self.packet.write2ByteTxOnly(self.port, 254, 82, 0)    # I gain
        self.packet.write2ByteTxOnly(self.port, 254, 80, 15)   # D gain
        time.sleep(0.1)

        try:
            while kb.is_pressed('t'):
                # if kb.is_pressed('t'):
                for i in p1:
                    if not kb.is_pressed('t'):
                        print("Key released, stopping pushup action")
                        self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
                        return
                    self.packet.write4ByteTxOnly(self.port, i, 116, 1500)
                    time.sleep(d)
                    self.packet.write4ByteTxOnly(self.port, i + 6, 116, 1100)
                    time.sleep(d)

                time.sleep(0.5)

                self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
                time.sleep(d2)

                for i in p2:
                    if not kb.is_pressed('t'):
                        print("Key released, stopping pushup action")
                        self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
                        return
                    self.packet.write4ByteTxOnly(self.port, i, 116, 1500)
                    time.sleep(d)
                    self.packet.write4ByteTxOnly(self.port, i + 6, 116, 1100)
                    time.sleep(d)

                time.sleep(0.5)
                self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
                time.sleep(d2)
                # else:
                #     time.sleep(0.1)
        except KeyboardInterrupt:
            print("Action interrupted")
        except Exception as e:
            print(f"Error during action: {e}")



def main():
    DEVICE_NAME = '/dev/ttyUSB0' #'COM9'  
    BAUDRATE = 57600   
    f_path = "./gait_angles_DIR_all_v6/Processed/"
    EDGE_GAITS = (f"{f_path}N_STR.npy",f"{f_path}N_MID.npy",f"{f_path}N_END.npy")
    VERTEX_GAITS = (f"{f_path}W_STR.npy",f"{f_path}W_MID.npy",f"{f_path}W_END.npy")
    DANCE_GAITS = (f"{f_path}Dance_W_STR.npy",f"{f_path}Dance_W_MID.npy",f"{f_path}Dance_W_END.npy")
 

    hexapod = HexapodController(DEVICE_NAME, BAUDRATE, EDGE_GAITS, VERTEX_GAITS, DANCE_GAITS)
    
    try:
        if hexapod.port.openPort():
            print(f"Succeeded to open port {DEVICE_NAME}")
        else:
            print("Failed to open port")
            return      
        if hexapod.port.setBaudRate(BAUDRATE):
            print(f"Succeeded to set baudrate to {BAUDRATE}")
        else:
            print("Failed to change baudrate")
            return
        # hexapod.packet.write4ByteTxOnly(hexapod.port, 254, 116, 2048)
        # time.sleep(1)
        # hexapod.packet.write4ByteTxOnly(hexapod.port, 19, 112, 30)
        # time.sleep(1)


        while True:
            if kb.is_pressed('q'):
                hexapod.move_north_west()
            elif kb.is_pressed('z'):
                hexapod.move_south_west()
            elif kb.is_pressed('e'):
                hexapod.move_north_east()
            elif kb.is_pressed('c'):
                hexapod.move_south_east()
            elif kb.is_pressed('w'):
                hexapod.move_north()
            elif kb.is_pressed('x'):
                hexapod.move_south()
            elif kb.is_pressed('a'):
                hexapod.move_west()
            elif kb.is_pressed('d'):
                hexapod.move_east()
            elif kb.is_pressed('p'):
                hexapod.perform_pushup_action()
            elif kb.is_pressed('h'):
                hexapod.perform_wave_action()
            elif kb.is_pressed('g'):
                hexapod.move_dance_action()
            elif kb.is_pressed('t'):
                hexapod.perform_alt_action()
            elif kb.is_pressed('r'):
                hexapod.reboot()
            # elif kb.is_pressed('i'):
            #     hexapod.get_current()
            time.sleep(0.1)

    except KeyboardInterrupt:
        hexapod.port.closePort()
        print("\nProgram stopped")
        
    except Exception as e:
        print(f"An error occurred: {e}")
        
    finally:
        if hexapod.port.is_open:
            hexapod.port.closePort()
            print("Port closed")

if __name__ == "__main__":
    main()