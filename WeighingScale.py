#!/usr/bin/python

import paramiko
import ftplib
import cv2
import numpy as np
import commands
from datetime import datetime

#globals

filenameIN = "1.jpg"
filenameOUT = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + filenameIN[0]

#%% connect to rpi105 and take the picture
def ConnectToRpi():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('192.168.1.189', username='pi', password='raspberry')
    stdin, stdout, stderr = ssh.exec_command('cd mycode/scripts; ./camera.sh')
    stdout.readlines()
    return
    
#%% download the picture with the FTP
def DownloadImage():
    ftp = ftplib.FTP("192.168.1.189")
    ftp.login("pi", "raspberry")
    ftp.cwd("mycode/scripts")
    ftp.retrlines('LIST')     
    localfile = open(filenameIN, 'wb')
    
    try:
        ftp.retrbinary('RETR ' + '1.jpg', localfile.write, 1024)
    except:
        print "Error"
    
    ftp.quit()
    localfile.close()
    return

#%% perform image analysis
def ImageProcessing():
    camera = cv2.imread(filenameIN)
    
    height, width, depth = camera.shape
    
    #turn image into gray-scale for cornerHarris algorithm that is sensitive for 
    #the LCD corners. The corners are marked with red dots
    
    gray_camera = cv2.cvtColor(camera, cv2.COLOR_BGR2GRAY)
    ret,thresh1 = cv2.threshold(gray_camera,50,255,cv2.THRESH_BINARY)
    gray = np.float32(thresh1)
    dst = cv2.cornerHarris(gray,7,5,0.04)
    
    #result is dilated for marking the corners, not important
    dst = cv2.dilate(dst,None)
    
    # Threshold for an optimal value, it may vary depending on the image.
    camera[dst>0.8*dst.max()]=[0,0,255]
    
    #The code below searches for the 4 red dots that should appear on the edges of the LCD
    #, then it finds the x,y coordinates and sorts the arrays to get first lower points
    #and the last higher points. Then the assumtion is made that in the middle 
    #we can distinguish between these two group of points (e.g. for x position we
    #cannot distingish the firts or the last group witout sorting).  
    #xpoint1 = int(xlenght/2 - (xlenght/2)/2) from all the points we choose only
    #one thats sits in the middle and so on for rest xpoints then we append the points
    #to the array point1,  these are upper lect corner, and point2 lower right corner.
    #Next cropping is performed and we get rid of the kilograms sign (kg) and the
    #empty space in front of the first LCD number getRidOfKg = 30
    #getRofOfBeginningSpace = 100. For saving purposes we also crop the image with
    #the LCD and red dots for troubleshooting purposes.
    
    x = []
    y = []
    for i in range(0, height):
        for j in range(0, width):
            
            if camera[i][j][2] == 255:         #OpenCV loads color images in BGR, not RGB
                y.append(i)
                x.append(j)      
    
    x.sort()
    y.sort()
    
    point1 = []
    point2 = []
    
    xlenght = len(x)
    ylenght = len(y)
    xpoint1 = int(xlenght/2 - (xlenght/2)/2)
    ypoint1 = int(ylenght/2 - (ylenght/2)/2)
    xpoint2 = int(xlenght/2 + (xlenght/2)/2)
    ypoint2 = int(ylenght/2 + (ylenght/2)/2)
    
    point1.append(x[xpoint1])
    point1.append(y[ypoint1])
    point2.append(x[xpoint2])
    point2.append(y[ypoint2])

    getRidOfKg = 30
    getRofOfBeginningSpace = 100
    cropwidth = point2[0]-point1[0]-getRidOfKg-getRofOfBeginningSpace
    cropheight = point2[1]-point1[1]
    
    #increase the crop field for saving the LCD screen
    
    point1xincrease = point1[0] - 10
    point1yincrease = point1[1] - 10 
    point2xincrease = point2[0] + 10
    point2yincrease = point2[1] + 10 
    cropincreasewidht = point2xincrease - point1xincrease
    cropincreaseheight = point2yincrease - point1yincrease
    
    cropLCDFileName = filenameOUT + '-cropLCD.png'
    cropLCD = camera[point1yincrease:point1yincrease+cropincreaseheight,point1xincrease:point1xincrease+cropincreasewidht]
    cv2.imwrite(cropLCDFileName,cropLCD)
    
    crop = camera[point1[1]:point1[1]+cropheight,point1[0]+getRofOfBeginningSpace:point1[0]+getRofOfBeginningSpace+cropwidth]
    gray_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    th3 = cv2.adaptiveThreshold(gray_crop,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,\
                cv2.THRESH_BINARY,141,2)
    
    cropThresholdFileName = filenameOUT + '-cropThreshold.png'
    th3d = cv2.dilate(th3,None)
    cv2.imwrite(cropThresholdFileName,th3d)
    return cropThresholdFileName

#use Seven Segment Optical Character Recognition on thresholded LCD image
#https://www.unix-ag.uni-kl.de/~auerswal/ssocr/
def OpticalCharacterRecognition(cropThresholdFileName):
    cmd = 'ssocr -d4 -r3 ' + cropThresholdFileName
    output = commands.getoutput(cmd)
    print output
    return output

if __name__ == "__main__":
    ConnectToRpi()
    DownloadImage()
    LCDResult=OpticalCharacterRecognition(ImageProcessing())