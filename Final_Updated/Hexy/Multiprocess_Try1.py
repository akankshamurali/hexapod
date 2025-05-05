from multiprocessing import Process, Manager
from time import sleep

def func1(a,b,lock):
	with lock:
		a.value = -1.0
		b.value = True
		c = a.value
	while c == -1.0:
		print('Value of C from while ' + str(c))
		with lock:
			c = a.value
		sleep(0.01)
	print("While from func1 done C updated = " +str(c))
def func2(a,b,lock):
	while True:
		with lock:
			if b.value == True:
				a.value = 10
			if a.value == 10:
				exit()
		# print("Printing from Func2 a value = " +str(a.value))
def main():
	with Manager() as mngr:
		a = mngr.Value('f', -1.0)
		b = mngr.Value('b', False)
		lock = mngr.Lock()
		p1 = Process(target = func1, args=(a,b,lock))
		p2 = Process(target = func2, args=(a,b,lock))
		p1.start()
		sleep(5)
		print("Func2 started")
		p2.start()
		sleep(1)
		p1.join()
		p2.join()

if __name__ == "__main__":
	main()