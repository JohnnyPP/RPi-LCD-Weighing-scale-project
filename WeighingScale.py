#!/usr/bin/python

import paramiko
import ftplib
import cv2
import numpy as np
import commands
import httplib, urllib          #thingspeak
import sqlite3
from datetime import datetime


#globals
filenameIN = "1.jpg"

#%% connect to rpi105 and take the picture
def ConnectToRpi():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('192.168.1.189', username='pi', password='raspberry')
    stdin, stdout, stderr = ssh.exec_command('cd mycode/scripts; ./camera.sh')
    stdout.readlines()
    return None
    
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
        print "FTP Error"
    
    ftp.quit()
    localfile.close()
    return None

#%% perform image analysis
def ImageProcessing():
    camera = cv2.imread(filenameIN)
    height, width, depth = camera.shape
    DateAndTime = datetime.now().strftime("%Y%m%d-%H%M%S")
    LCDRectangleThreshold = 40

    #turn image into gray-scale for cornerHarris algorithm that is sensitive for 
    #the LCD corners. The corners are marked with red dots
    
    gray_camera = cv2.cvtColor(camera, cv2.COLOR_BGR2GRAY)
    #cv2.imwrite('gray_camera.png',gray_camera)
    ret,thresh1 = cv2.threshold(gray_camera,LCDRectangleThreshold,255,cv2.THRESH_BINARY)
    #cv2.imwrite('thresh.png',thresh1)
    gray = np.float32(thresh1)
    #cv2.imwrite('gray.png',gray)
    dst = cv2.cornerHarris(gray,7,5,0.04)
    
    #result is dilated for marking the corners, not important
    dst = cv2.dilate(dst,None)
    
    # Threshold for an optimal value, it may vary depending on the image.
    camera[dst>0.8*dst.max()]=[0,0,255]
    #cv2.imwrite('cropped.png',camera)
    
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
    
    cropLCDFileName = DateAndTime + '-cropLCD.png'
    cropLCD = camera[point1yincrease:point1yincrease+cropincreaseheight,point1xincrease:point1xincrease+cropincreasewidht]
    cv2.imwrite(cropLCDFileName,cropLCD)
    
    crop = camera[point1[1]:point1[1]+cropheight,point1[0]+getRofOfBeginningSpace:point1[0]+getRofOfBeginningSpace+cropwidth]
    gray_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    th3 = cv2.adaptiveThreshold(gray_crop,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,\
                cv2.THRESH_BINARY,141,2)
    
    cropThresholdFileName = DateAndTime + '-cropLCDThreshold.png'
    th3d = cv2.dilate(th3,None)
    cv2.imwrite(cropThresholdFileName,th3d)
    return cropThresholdFileName

#use Seven Segment Optical Character Recognition on thresholded LCD image
#https://www.unix-ag.uni-kl.de/~auerswal/ssocr/
def OpticalCharacterRecognition(cropThresholdFileName):
    cmd = 'ssocr -d4 -r3 ' + cropThresholdFileName
    output = commands.getoutput(cmd)
    print output
    #when OCS fails to return good results it writes the response of the form:
    #output = "found only 3 of 4 digits". In this case this function returns -1
    #Succesful OCR returns output of the form 74.1 (SSOCR claims there are 4 digits) 
    if output.find("found") == 0:
        return -1
    else:
        return output

#sending data to thingspeak
def SendDataToThingspeak(LCDResult):
    params = urllib.urlencode({'key': 'MB0Q9HXOHIXVL6AN','field1': LCDResult})
    headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain"}
    conn = httplib.HTTPConnection("api.thingspeak.com")
    conn.request("POST", "/update", params, headers)
    response = conn.getresponse()
    print response.status, response.reason
    ServerResponse = response.status, response.reason
    conn.close()
    return ServerResponse

#add data to sqlite3 database
def AddDataToDatabase(DateTimeNow, LCDResult, person):
    #run this is only once 
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    # Create table run this only once
    #c.execute('''CREATE TABLE data(date text, weight real, person real)''')
    # Insert a row of data
    c.execute("INSERT INTO data VALUES (?, ?, ?)", (DateTimeNow, LCDResult, person))
    # Save (commit) the changes
    conn.commit()
    # We can also close the connection if we are done with it.
    # Just be sure any changes have been committed or they will be lost.
    conn.close()
    print "Data written to database file"

#add data to txt file
def AddDataToFile(DateTimeNow, LCDResult, person):
    # Open/append file
    f = open("data.txt", "a")
    try:
        f.write(DateTimeNow + "\t" + str(LCDResult) + "\t" + str(person) + "\n");
    except:
        print "File error"
    # Close opend file
    f.close()
    print "Data written to text file"
    
if __name__ == "__main__":
    DateTimeNow = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    person = 1
    
    ConnectToRpi()
    DownloadImage()
    LCDResult=OpticalCharacterRecognition(ImageProcessing())
    if LCDResult != -1:
        ThingspeakResponse = SendDataToThingspeak(LCDResult)
        AddDataToDatabase(DateTimeNow, LCDResult, person)
        AddDataToFile(DateTimeNow, LCDResult, person)