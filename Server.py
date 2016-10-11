import sys
import re
from socket import *

# Possible states of the state machine
class States:HELLO, MAIL_FROM, RCPT_TO_FIRST, RCPT_TO, DATA, EOF = range(6)

# Class to manage state of the machine
class SMTPState:
	def __init__(self):
		self.conn = None
		self.reset()	

	def reset(self):
		if self.conn != None: self.conn.close()
		self.conn = None
		self.state = States.HELLO
		self.from_mailbox = ""
		self.to_mailboxes = []
		self.data = []

	def writeToFile(self):
		if self.state != States.DATA:
			raise OutOfOrderException()

		# Create string to write to file
		data_str = "From: <" + self.from_mailbox + ">\n"
		for to_mailbox in self.to_mailboxes:
			data_str += "To: <" + to_mailbox + ">\n"
		data_str += str.join("\n", self.data) + "\n"

		# WRite to files	
		for to_mailbox in self.to_mailboxes: 
			_, domain = match_mailbox(to_mailbox)
			with open(domain, "a") as f:
				f.write(data_str)

# Custom exception thrown when a parse function fails
class ParseException(Exception):pass
class OutOfOrderException(Exception):pass

smtp = SMTPState()

# The common "<nullspace> <CRLF>" ending
re_null_crlf = re.compile("^[ \t]*[\r]?$")

# Parse data while in state = DATA
def readdata(line):
	if smtp.state != States.DATA: raise OutOfOrderException()

	if line == ".":
		smtp.writeToFile()
		smtp.reset()
		print("250 OK")
	else:
		smtp.data.append(line)	

# Parse DATA
re_data_1 = re.compile("^DATA")
def data(line):
	if smtp.state != States.RCPT_TO: raise OutOfOrderException()

	line = match("data-cmd", re_data_1, line)
	line = match("data-cmd", re_null_crlf, line)
	
	smtp.state = States.DATA
	print("354 Start mail input; end with <CRLF>.<CRLF>")

# Parse RCPT TO
re_rcpt_to_1 = re.compile("^RCPT[ \t]+TO:[ \t]*")
def rcptto(line):
	if smtp.state != States.RCPT_TO_FIRST and smtp.state != States.RCPT_TO: 
		raise OutOfOrderException()

	line = match("rcpt-to-cmd", re_rcpt_to_1, line)
	line, mailbox = match_path(line)
	line = match("rcpt-to-cmd", re_null_crlf, line)
	
	# Has gotten at least first RCPT_TO
	smtp.to_mailboxes.append(mailbox)
	smtp.state = States.RCPT_TO
	print("250 OK")	 

# Regular expressions used to parse mail from
re_mail_from_1 = re.compile("^MAIL[ \t]+FROM:[ \t]*")
def mailfrom(line):
	if smtp.state != States.MAIL_FROM: raise OutOfOrderException()	

	line = match("mail-from-cmd", re_mail_from_1, line)
	line, mailbox = match_path(line)
	line = match("mail-from-cmd", re_null_crlf, line)	
	
	smtp.from_mailbox = mailbox
	smtp.state = States.RCPT_TO_FIRST
	print("250 OK")

# Inital handshake "hello" command
re_hello = re.compile("^HELO")
def hello(line):
	if smtp.state != States.HELLO: raise OutOfOrderException()
	line = match("helo", re_hello, line)
	smtp.state = States.MAIL_FROM
	print("250 " + line.strip() + ", pleased to meet you")

# Check for the pattern, if found remove it. Otherwise throw parse exception
def match(name, pattern, token):
	match = re.match(pattern, token)
	if match == None: raise ParseException(name)
	else: return re.sub(pattern, "", token)

# Check for the <path> object. If found remove from original string and return that and mailbox, otherwise throw parse exception
re_path = re.compile("^<(.+?)>")
re_mailbox = re.compile("^(.+?)@(.+?)$")
re_local_part_ascii = re.compile(r"^[\x00-\x7F]+$")
re_local_part_char = re.compile(r"^[^ \t<>()\[\]\\\.,;:@\"]+$")
re_domain_elem = re.compile("^[a-zA-Z][a-zA-Z0-9]+$")
def match_path(token):
	match = re.match(re_path, token)
	if match == None: raise ParseException("path")
	
	mailbox = match.group(1)
	line, domain = match_mailbox(mailbox)
	return line, mailbox

# Parse a mailbox. If found returns original string with mailbox removed and the domain of the mailbox
def match_mailbox(mailbox):
	match = re.match(re_mailbox, mailbox)
	if match == None: raise ParseException("mailbox")

	domain = match.group(2)
	domain_elems = domain.split(".")

	# Check is ascii, then check not illegal char
	match = re.match(re_local_part_ascii, match.group(1))
	if match == None: raise ParseException("local-part")
	match = re.match(re_local_part_char, match.group(0))
	if match == None: raise ParseException("local-part")

	# Check all domain elements
	for de in domain_elems:
		match = re.match(re_domain_elem, de)
		if match == None: raise ParseException("domain")

	return re.sub(re_path, "", token), domain

# Main loop
def main():
	PORT = int(sys.argv[1])
	socket = socket(AF_INET,SOCKET_STREAM)
	
	# Try starting the server
	try:
		socket.bind(('', PORT))
		socket.listen(1)
	except: return
	
	while True:
		smtp.conn = socket.accept()
		runSMTP()

# Run SMTP protocol for connection
def runSMTP():
	if (smtp.conn == None) return

	smtp.conn.send("220 " + socket.getfqdn())
	while True:
		try:
			line = smtp.conn.recv(1024).decode()
			print(line)
			if smtp.state == States.DATA:
				readdata(line)
			elif re.match(re_hello, line):
				hello(line)
			elif re.match(re_data_1, line):
				data(line)
			elif re.match(re_rcpt_to_1, line):
				rcptto(line)
			elif re.match(re_mail_from_1, line):
				mailfrom(line)
			elif line == "QUIT":
				break
			else:
				smtp.conn.send("500 Syntax error: command unrecognized")
				
		except ParseException as e:
			smtp.conn.send("501 Syntax error in parameters or arguments")
		except OutOfOrderException:
			smtp.conn.send("503 Bad sequence of commands")
			print("503 Bad sequence of commands")
			break
	smtp.reset()

# Start
main()
