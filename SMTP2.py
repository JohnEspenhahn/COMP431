import sys
import re

class States:PROC_FROM, PROC_TO, PROC_BODY = range(3)

state = States.PROC_FROM
		
RE_250 = re.compile("^250")
RE_354 = re.compile("^354")

def procStartOfNew(line):
	print(".")
	res = raw_input()
	sys.stderr.write(res + "\n")
	if RE_250.match(res) == None: raise Exception("Expected 250")
		
	return procFrom(line)

	
RE_FROM = re.compile("^From: <(.+?)>")
def procFrom(line):
	match = RE_FROM.match(line)
	if match == None: raise Exception("Invalid from")
	
	print("MAIL FROM: <" + match.group(1) + ">");
	
	res = raw_input()
	sys.stderr.write(res + "\n")
	if RE_250.match(res) == None: raise Exception("Expected 250")
	
	return States.PROC_TO
	
	
RE_TO = re.compile("^To: <(.+?)>")
def procTo(line):
	# Send to command
	match = RE_TO.match(line)
	if match == None: raise Exception("Invalid to")
	
	print("RCPT TO: <" + match.group(1) + ">")
	
	res = raw_input()
	sys.stderr.write(res + "\n")
	if RE_250.match(res) == None: raise Exception("Expected 250")
	
	# Send data command (assuming only one to)
	print("DATA")
	
	res = raw_input()
	sys.stderr.write(res + "\n")
	if RE_354.match(res) == None: raise Exception("Expected 354")
	
	return States.PROC_BODY
	
mailbox_name = sys.argv[1]
with open(mailbox_name, "r") as mailbox_file:
	line = mailbox_file.readline()
	try:
		while line != "":
			if state == States.PROC_FROM: 
				state = procFrom(line)
			elif state == States.PROC_TO: 
				state = procTo(line)	
			elif state == States.PROC_BODY:
				if line.startswith("From:"):
					state = procStartOfNew(line)
				else:
					print(line)
		
			line = mailbox_file.readline()
	except Exception as e:
		print(e)
		print("QUIT")