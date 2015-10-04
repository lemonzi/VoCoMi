import numpy

mean = 10
d = 0.95
th = -30
count = 0

def clear():
    global mean, d, th, count
    print("vad reset")
    mean = 10
    count = 0

def update(data):
    global mean, d, th, count
    count += 1
    ndata = numpy.frombuffer(data, dtype=numpy.dtype(numpy.int16)) / 32768.0
    p = 20 * numpy.log(numpy.dot(ndata, ndata)) / numpy.log(10)
    deff = d * (len(ndata) / 512)
    mean = mean * d + p * (1-d)
    print(p, mean)
    return count < 30 or mean > th

