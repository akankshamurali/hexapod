import time
import dynamixel_sdk as dxl 
import numpy as np
# import keyboard as kb
import pyzed.sl as sl
from multiprocessing import Process, Manager

# min_dist = -1.0
# dist_flag = False

# V8 is Multiprocessing with concurrent camera recording and bot autnomous motion with obstacle avoidance
# V9 experimental code to check feet contact alongside obstacle detection for turning

class HexapodController:
    def __init__(self, device_name, baudrate, edge_gaits, vertex_gaits, dist_flag, min_dist, lock):
        self.device_name = device_name
        self.baudrate = baudrate
        self.edge_gaits = edge_gaits  # (initial, continuous, final)
        self.vertex_gaits = vertex_gaits  # (initial, continuous, final)
        self.port = dxl.PortHandler(self.device_name)
        self.packet = dxl.PacketHandler(2.0)
        self.group_sync_write = None
        self.gait_angles = None
        self.setup_motors()
        self.action=None
        self.cam_pos = 2048 # +-90 == +-1024
        self.start = 1
        self.min_dist = None
        self.dist_shared = min_dist
        self.dist_flag = dist_flag
        self.lock = lock

        # seq_N = (6, 12, 18, 1, 7, 13, 2, 8, 14, 3, 9, 15, 4, 10, 16, 5, 11, 17) #2048
        # seq_S = (3, 9, 15, 4, 10, 16, 5, 11, 17, 6, 12, 18, 1, 7, 13, 2, 8, 14) #0
        # seq_W = (3, 9,15, 4, 10, 16, 5, 11, 17, 6, 12, 18,1, 7, 13, 2, 8, 14) #3072
        # seq_E = (6, 12, 18, 1, 7, 13, 2, 8, 14, 3, 9, 15, 4, 10, 16, 5, 11, 17) #1024
        # self.dir_dict = {2048:seq_N, 0:seq_S, 3072:seq_W, 1024:seq_E}
        # self.edge = True

    def setup_motors(self):
        if not self.port.openPort():
            raise Exception("Failed to open port")
        if not self.port.setBaudRate(self.baudrate):
            raise Exception("Failed to set baudrate")
        try:
            self.packet.write1ByteTxOnly(self.port, 254, 65, 0)
            self.packet.write1ByteTxOnly(self.port, 254, 64, 1)
            time.sleep(0.1)
            self.packet.write2ByteTxOnly(self.port, 254, 84, 800)  # P gain
            self.packet.write2ByteTxOnly(self.port, 254, 82, 0)    # I gain
            self.packet.write2ByteTxOnly(self.port, 254, 80, 64)   # D gain
            time.sleep(0.1)
            self.packet.write2ByteTxOnly(self.port, 19, 82, 100)    # I gain
            self.packet.write2ByteTxOnly(self.port, 19, 80, 50)   # D gain
            time.sleep(0.1)
            self.packet.write4ByteTxOnly(self.port, 19, 112, 30) #Set Cam motor velocity
            time.sleep(0.1)
            self.group_sync_write = dxl.GroupSyncWrite(self.port, self.packet, 116, 4) #Initialize Motor Group Write
            time.sleep(0.1)
            self.packet.write4ByteTxOnly(self.port, 254, 116, 2048) #Send all motors to home position
            time.sleep(0.1)
        except Exception as e:
            print(f"Error configuring motor parameters: {e}")



    def load_gait_file(self, file):
        try:
            self.gait_angles = np.load(file, allow_pickle=True)
            print(f"Loaded gait file with {self.gait_angles.shape[0]} frames")
        except Exception as e:
            print(f"Error loading gait file: {e}")

    def cam_motion_complete(self):
        count = 0
        stat = self.packet.read1ByteTxRx(self.port,19,122)
        while count < 5:
            time.sleep(0.02)
            stat = self.packet.read1ByteTxRx(self.port,19,122)
            if stat[0] == 0:
                count+=1
            else:
                count = 0
        return 1
    
    def feet_contact(self):
        contact = 0
        i_low = 20
        i_high = 1500
        if self.cam_pos > 2040 and self.cam_pos < 2060:
            # self.move_north()
            i1 = self.packet.read2ByteTxRx(self.port,7,126)[0]
            time.sleep(0.005)
            i2 = self.packet.read2ByteTxRx(self.port,12,126)[0]
            time.sleep(0.005)
            if i1 > i_low and i1 < i_high and i2 > i_low and i2 < i_high:
                contact = 1
        elif self.cam_pos > 4090 or self.cam_pos < 10:
            # self.move_south()
            i1 = self.packet.read2ByteTxRx(self.port,9,126)[0]
            time.sleep(0.005)
            i2 = self.packet.read2ByteTxRx(self.port,10,126)[0]
            time.sleep(0.005)
            if i1 > i_low and i1 < i_high and i2 > i_low and i2 < i_high:
                contact = 1
        elif self.cam_pos > 1010 and self.cam_pos < 1040:
            # self.move_east()
            i1 = self.packet.read2ByteTxRx(self.port,11,126)[0]
            time.sleep(0.005)
            if i1 > i_low and i1 < i_high:
                contact = 1
        elif self.cam_pos > 3060 and self.cam_pos < 3090:
            # self.move_west()
            i1 = self.packet.read2ByteTxRx(self.port,8,126)[0]
            time.sleep(0.005)
            if i1 > i_low and i1 < i_high:
                contact = 1
        if contact == 0:
            print("Front foot not in contact or is stuck")
        return contact
        # time.sleep(0.01)        

    def walk(self, seq, gaits, delay=0.01):
        self.cam_motion_complete()
        try:
            self.min_dist = get_dist(self.dist_flag, self.dist_shared, self.lock)
            if self.min_dist > 350 and self.feet_contact():
                # Initial gait
                self.load_gait_file(gaits[0])
                for frame in range(self.gait_angles.shape[0]):
                    self.execute_frame(seq, frame, delay)

                # Continuous gait loop
                self.load_gait_file(gaits[1])
                
                # Change this to distance condition
                self.min_dist = get_dist(self.dist_flag, self.dist_shared, self.lock)
                while self.min_dist > 350 and self.feet_contact():  
                    for frame in range(self.gait_angles.shape[0]):
                        self.execute_frame(seq, frame, delay)
                    self.min_dist = get_dist(self.dist_flag, self.dist_shared, self.lock)
                    print(self.min_dist)

                # Final gait
                self.load_gait_file(gaits[2])
                for frame in range(self.gait_angles.shape[0]):
                    # print(self.gait_angles[frame, :])
                    self.execute_frame(seq, frame, delay)
            else:
                print("Obstacle Min dist = " + str(self.min_dist))

        except Exception as e:
            print(f"Error during walking: {e}")

    def scan(self):
        self.cam_pos += 1024
        if self.cam_pos > 4095:
            self.cam_pos -= 4095
        # self.cam_pos = max(0, min(4095, self.cam_pos+1024)) #Camera turn Left
        self.packet.write4ByteTxOnly(self.port, 19, 116, self.cam_pos)
        self.cam_motion_complete()
        l_min = get_dist(self.dist_flag, self.dist_shared, self.lock)
        self.cam_pos -= 2048
        if self.cam_pos < 0:
            self.cam_pos += 4095
        # self.cam_pos = max(0, min(4095, self.cam_pos-2048)) #Camera turn Right
        self.packet.write4ByteTxOnly(self.port, 19, 116, self.cam_pos)
        self.cam_motion_complete()
        r_min = get_dist(self.dist_flag, self.dist_shared, self.lock)

        print("Left dist = " + str(l_min) + " Right dist = "+ str(r_min))
        if r_min <= l_min:
            self.cam_pos -= 2048
            if self.cam_pos < 0:
                self.cam_pos += 4095            
            # self.cam_pos = max(0, min(4095, self.cam_pos+2048)) #Camera turn left
            self.packet.write4ByteTxOnly(self.port, 19, 116, self.cam_pos)
            self.cam_motion_complete()
        # print("Self Cam Pos = " + str(self.cam_pos))
        return self.cam_pos
        
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
        print(f'Moving North')
        seq = (6, 12, 18, 1, 7, 13, 2, 8, 14, 3, 9, 15, 4, 10, 16, 5, 11, 17)
        # seq = (4, 10, 16, 5, 11, 17, 6, 12, 18, 1, 7, 13, 2, 8, 14, 3, 9, 15)
        # self.packet.write4ByteTxOnly(self.port, 19, 116, 2048)
        # time.sleep(0.5)
        self.walk(seq, self.edge_gaits)

    def move_south(self):
        # seq = (1, 7, 13, 2, 8, 14, 3, 9, 15, 4, 10, 16, 5, 11, 17, 6, 12, 18)
        seq = (3, 9, 15, 4, 10, 16, 5, 11, 17, 6, 12, 18, 1, 7, 13, 2, 8, 14)
        # self.packet.write4ByteTxOnly(self.port, 19, 116, 0)
        # time.sleep(0.5)
        self.walk(seq, self.edge_gaits)

    def move_west(self):
        seq = (3, 9,15, 4, 10, 16, 5, 11, 17, 6, 12, 18,1, 7, 13, 2, 8, 14)
        # self.packet.write4ByteTxOnly(self.port, 19, 116, 3072)
        # time.sleep(0.5)
        self.walk(seq, self.vertex_gaits)

    def move_east(self):
        seq = (6, 12, 18, 1, 7, 13, 2, 8, 14, 3, 9, 15, 4, 10, 16, 5, 11, 17)
        # self.packet.write4ByteTxOnly(self.port, 19, 116, 1024)
        # time.sleep(0.5)
        self.walk(seq, self.vertex_gaits)

    def move_north_east(self):
        # seq = (3, 9, 15, 4, 10, 16, 5, 11, 17, 6, 12, 18, 1, 7, 13, 2, 8, 14)
        seq = (5, 11, 17, 6, 12, 18, 1, 7, 13, 2, 8, 14, 3, 9, 15, 4, 10, 16)
        # self.packet.write4ByteTxOnly(self.port, 19, 116, 1365)
        # time.sleep(0.5)
        self.walk(seq, self.edge_gaits)

    def move_south_east(self):
        # seq = (2, 8, 14, 3, 9, 15, 4, 10, 16, 5, 11, 17, 6, 12, 18, 1, 7, 13)
        seq = (4, 10, 16, 5, 11, 17, 6, 12, 18, 1, 7, 13, 2, 8, 14, 3, 9, 15)
        # self.packet.write4ByteTxOnly(self.port, 19, 116, 682)
        # time.sleep(0.5)
        self.walk(seq, self.edge_gaits)

    def move_north_west(self):
        # seq = (5, 11, 17, 6, 12, 18, 1, 7, 13, 2, 8, 14, 3, 9, 15, 4, 10, 16)
        seq = (1, 7, 13, 2, 8, 14, 3, 9, 15, 4, 10, 16, 5, 11, 17, 6, 12, 18)
        # self.packet.write4ByteTxOnly(self.port, 19, 116, 2730)
        # time.sleep(0.5)
        self.walk(seq, self.edge_gaits)

    def move_south_west(self):
        # seq = (6, 12, 18, 1, 7, 13, 2, 8, 14, 3, 9, 15, 4, 10, 16, 5, 11, 17)
        seq = (2, 8, 14, 3, 9, 15, 4, 10, 16, 5, 11, 17, 6, 12, 18, 1, 7, 13)
        # self.packet.write4ByteTxOnly(self.port, 19, 116, 3383)
        # time.sleep(0.5)
        self.walk(seq, self.edge_gaits)

    def controller(self):
        # try:
        print(f'motor control started')
        while True:
            if self.start:
                self.start = 0
                self.move_north()
                time.sleep(0.01)
            cam_pos = self.scan()
            # print("Cam Position = " +str(cam_pos))
            if cam_pos > 2040 and cam_pos < 2060:
                self.move_north()
            elif cam_pos > 4090 or cam_pos < 10:
                self.move_south()
            elif cam_pos > 1010 and cam_pos < 1040:
                self.move_east()
            elif cam_pos > 3060 and cam_pos < 3090:
                self.move_west()
            time.sleep(0.01)

        # except KeyboardInterrupt:
        #     print("\nProgram stopped")
        #     stop_event.set()
        #     self.packet.write4ByteTxOnly(self.port, 254, 116, 2048)
                
            
        # except Exception as e:
        #     print(f"An error occurred: {e}")
            
        # finally:
        #     if self.port.is_open:
        #         self.port.closePort()
        #         print("Port closed")


def get_dist(dist_flag, min_dist, lock):
    with lock:
        min_dist.value = -1.0
        dist_flag.value = True
        tmp = min_dist.value
    time.sleep(0.01)
    while tmp == -1.0:
        with lock:
            tmp = min_dist.value
        # print(f'While loop dist Flag = {dist_flag}')
        time.sleep(0.02)
#            print(f'Distance is {min_dist}')
    # self.min_dist = min_dist
    # print(f"Exited while loop Min Dist {tmp}")
    return tmp

def cam_recording(dist_flag, min_dist, lock):

    cam = sl.Camera()
    init_params = sl.InitParameters()
    init_params.camera_resolution = sl.RESOLUTION.HD720
    init_params.camera_fps = 60
    init_params.depth_mode = sl.DEPTH_MODE.PERFORMANCE
    init_params.coordinate_units = sl.UNIT.MILLIMETER
    init_params.depth_minimum_distance = 230
    err = cam.open(init_params)
    if err != sl.ERROR_CODE.SUCCESS:
        print("Error Opening Camera")
        exit(-1)
    img_l = sl.Mat()
    img_depth = sl.Mat()
    # self.img_depth_dis = sl.Mat()
    runtime_params = sl.RuntimeParameters()
    recordingParameters = sl.RecordingParameters()

    recordingParameters.compression_mode = sl.SVO_COMPRESSION_MODE.H264
    recordingParameters.video_filename = "record.svo2"
    err = cam.enable_recording(recordingParameters)
    if err != sl.ERROR_CODE.SUCCESS:
        print("Error Enabling Recording")
        exit(-1)
    img_roi = None

    while True:
        if cam.grab(runtime_params) == sl.ERROR_CODE.SUCCESS:
            with lock:
                if dist_flag.value == True:
                    # cam.retrieve_image(img_l, sl.VIEW.LEFT)
                    cam.retrieve_measure(img_depth, sl.MEASURE.DEPTH)
                    # cam.retrieve_image(img_depth_dis, sl.VIEW.DEPTH)
                    img_roi = img_depth.get_data()[200:500,280:1170] 
                    img_roi[np.isnan(img_roi)] = np.inf
                    img_roi[img_roi<0] = np.inf
                    min_dist.value = np.min(img_roi)
                    # print(f'Distance is {min_dist.value}')
                    dist_flag.value = False

def main():
    DEVICE_NAME = '/dev/ttyUSB0' #'COM9'  
    BAUDRATE = 57600   
    f_path = "./gait_angles_DIR_all_v6/Processed/"
    EDGE_GAITS = (f"{f_path}N_STR.npy",f"{f_path}N_MID.npy",f"{f_path}N_END.npy")
    VERTEX_GAITS = (f"{f_path}W_STR.npy",f"{f_path}W_MID.npy",f"{f_path}W_END.npy")


    mngr = Manager()
    dist_flag = mngr.Value('b', False)
    min_dist = mngr.Value('f', -1.0)
    lock = mngr.Lock()
    cam = Process(target = cam_recording, args=(dist_flag,min_dist, lock))
    time.sleep(0.1)

    hexapod = HexapodController(DEVICE_NAME, BAUDRATE, EDGE_GAITS, VERTEX_GAITS, dist_flag, min_dist, lock)
    try:
        cam.start()
#        print(f'Trying motor control')
        hexapod.controller()
        time.sleep(2)
        cam.join()
    except KeyboardInterrupt:
        print("\nProgram stopped")
        # stop_event.set()
        hexapod.packet.write4ByteTxOnly(hexapod.port, 254, 116, 2048)
    except Exception as e:
        print(f"An error occurred: {e}")
        
    finally:
        if hexapod.port.is_open:
            hexapod.port.closePort()
            print("Port closed")

if __name__ == "__main__":
    # mp.set_start_method('spawn')  # Optional but more explicit on Windows
    main()
