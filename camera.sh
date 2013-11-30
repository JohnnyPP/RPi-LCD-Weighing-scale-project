#!/bin/bash
echo "Bash version ${BASH_VERSION}..."
echo "Prepare yourself, you have 15 seconds"
for i in {15..0..1}		#counts from 15 to 0 with step 1
  do
	if test "$i" -eq "0" 
	then
		echo "Taking picture"
		sleep 1
		echo "Filename : 1.jpg"
		raspistill -t 5000 -ISO 200 -o 1.jpg
	else
     		echo "$i"
		sleep 1
	fi
 done
