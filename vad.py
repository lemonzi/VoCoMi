import numpy

mean = 10
d = 0.9
th = -30

def clear():
    global mean, d, th
    print("vad reset")
    mean = 10

def update(data):
    global mean, d, th
    ndata = numpy.frombuffer(data, dtype=numpy.dtype(numpy.int16)) / 32768.0
    p = 20 * numpy.log(numpy.dot(ndata, ndata)) / numpy.log(10)
    mean = mean * d + p * (1-d)
    print(p, mean)
    return mean > th

def silence():
    global mean, d, th
    return mean < th

