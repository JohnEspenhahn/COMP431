import sys
import re
from socket import *

RE_250 = re.compile("^250")
RE_354 = re.compile("^354")
RE_220 = re.compile("^220")

def send(mss):
	# print "Sending " + mss;
	client.sendall(mss)

def recv():
	res = client.recv(1024).decode()
	# print "Received " + res
	return res
	
def procBody(from_mailbox, to_mailboxes, subject, body_arr):
	# Send data command
	send("DATA")
	
	res = recv()
	if RE_354.match(res) == None: raise Exception("Expected 354, got %s" % res)

	# Send content (header and body)
	send("From: " + from_mailbox)
	send("To: " + ",".join(to_mailboxes) + "\r\n")
	send("Subject: " + subject + "\r\n")
	send("\r\n")
	for line in body_arr: send(line + "\r\n")
	send(".")
	
	res = recv()
	if RE_250.match(res) == None: raise Exception("Expected 250, got %s" % res)
		
def procFrom(from_mailbox):
	send("MAIL FROM: <" + from_mailbox + ">")
	
	res = recv()
	if RE_250.match(res) == None: raise Exception("Expected 250, got %s" % res)
	
def procTo(to_mailboxes):
	for mailbox in to_mailboxes:
		send("RCPT TO: <" + mailbox + ">")
	
		res = recv()
		if RE_250.match(res) == None: raise Exception("Expected 250, got %s" % res)
	
def procHello(res):
	if RE_220.match(res) == None: raise Exception("Expected 220, got %s" % res)

	send("HELO cs.unc.edu")

	res = recv()
	if RE_250.match(res) == None: raise Exception("Expected 250, got %s" % res)

# Parse a mailbox. If found returns original string with mailbox removed and the domain of the mailbox
re_mailbox = re.compile("^(.+?)@(.+?)$")
re_local_part_ascii = re.compile(r"^[\x00-\x7F]+$")
re_local_part_char = re.compile(r"^[^ \t<>()\[\]\\\.,;:@\"]+$")
re_domain_elem = re.compile("^[a-zA-Z][a-zA-Z0-9]+$")
def match_mailbox(mailbox):
	match = re.match(re_mailbox, mailbox)
	if match == None: return False

	domain = match.group(2)
	domain_elems = domain.split(".")

	# Check is ascii, then check not illegal char
	match = re.match(re_local_part_ascii, match.group(1))
	if match == None: return False
	match = re.match(re_local_part_char, match.group(0))
	if match == None: return False

	# Check all domain elements
	for de in domain_elems:
		match = re.match(re_domain_elem, de)
		if match == None: return False

	return True

	
HOST = sys.argv[1]
PORT = int(sys.argv[2])
client = socket(AF_INET, SOCK_STREAM)
 
def main():
	# Get valid from mailbox
	while True:
		from_mailbox = raw_input("From: ")
		if match_mailbox(from_mailbox):
			break
		else:
			print("Invalid from address '" + from_mailbox + "'")

	# Get valid to mailboxes
	while True:
		to_mailboxes = raw_input("To: ").split(",")
		invalid = False
		for mailbox in to_mailboxes:
			if not match_mailbox(mailbox):
				print("Invalid to address '" + mailbox + "'")
				invalid = True

		if not invalid: break	
	
	subject = raw_input("Subject: ")

	# Read body
	print "Message:"
	body_arr = []
	while True:
		line = raw_input()
		if line == ".": break
		body_arr.append(line)

	# Connect to server
	try:
		client.connect((HOST, PORT))
	except: 
		print("Failed to connect to server")
		return	
	
	try:
		# Wait for server to talk first
		procHello(recv())
		procFrom(from_mailbox)
		procTo(to_mailboxes)
		procBody(from_mailbox, to_mailboxes, subject, body_arr)	
	except Exception as e:
		print(e)
	
	send("QUIT")

main()
client.close()
