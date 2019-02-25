import time

def wait_for(condition_function, timeout):
  start_time = time.time()
  while time.time() < start_time + timeout:
    if condition_function():
      return True
    else:
      time.sleep(0.1)
  raise Exception('Timeout waiting for' + condition_function.__name__)