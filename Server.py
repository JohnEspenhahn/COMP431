import sys
import re
import socket

# Possible states of the state machine
class States:HELLO, MAIL_FROM, RCPT_TO_FIRST, RCPT_TO, DATA, EOF = range(6)

# Class to manage state of the machine
class SMTPState:
	def __init__(self):
		self._conn = None
		self.reset()	

	def reset(self):
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
		alreadySent = set()
		for to_mailbox in self.to_mailboxes: 
			domain = match_mailbox(to_mailbox)
			if domain in alreadySent: continue			
			else: alreadySent.add(domain)

			with open(domain, "a") as f:
				f.write(data_str)

	def send(self, mss):
		if self._conn == None:
			print "Tried to send without connection"

		# print "Sending " + mss
		self._conn.sendall(mss)

# Custom exception thrown when a parse function fails
class ParseException(Exception):pass
class OutOfOrderException(Exception):pass

smtp = SMTPState()

# The common "<nullspace> <CRLF>" ending
re_null_crlf = re.compile("^[ \t]*[\r]?$")

# Parse data while in state = DATA
def readdata(line):
	if smtp.state != States.DATA: raise OutOfOrderException()

	# print "Reading '" + line + "'"
	if line == ".":
		smtp.writeToFile()
		smtp.send("250 OK")
		smtp.reset()
	else:
		smtp.data.append(line)	

# Parse DATA
re_data_1 = re.compile("^DATA")
def data(line):
	if smtp.state != States.RCPT_TO: raise OutOfOrderException()

	line = match("data-cmd", re_data_1, line)
	line = match("data-cmd", re_null_crlf, line)
	
	smtp.state = States.DATA
	smtp.send("354 Start mail input; end with <CRLF>.<CRLF>")

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
	smtp.send("250 OK")	 

# Regular expressions used to parse mail from
re_mail_from_1 = re.compile("^MAIL[ \t]+FROM:[ \t]*")
def mailfrom(line):
	if smtp.state != States.MAIL_FROM: raise OutOfOrderException()	

	line = match("mail-from-cmd", re_mail_from_1, line)
	line, mailbox = match_path(line)
	line = match("mail-from-cmd", re_null_crlf, line)	
	
	smtp.from_mailbox = mailbox
	smtp.state = States.RCPT_TO_FIRST
	smtp.send("250 OK")

# Inital handshake "hello" command
re_hello = re.compile("^HELO")
def hello(line):
	if smtp.state != States.HELLO: raise OutOfOrderException()
	line = match("helo", re_hello, line)
	smtp.state = States.MAIL_FROM
	smtp.send("250 " + line.strip() + ", pleased to meet you")

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
	match_mailbox(mailbox)
	return re.sub(re_path, "", token), mailbox

# Parse a mailbox. If found returns the domain of the mailbox, otherwise throw exception
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

	return domain

# Main loop
def main():
	try: 
		if len(sys.argv) < 1:
			print "No port provided"
			return None
		else:
			PORT = int(sys.argv[1])
	except: 
		print "Invalid port provided " + sys.argv[1]
		return None

	listener = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
	
	# Try starting the server
	try:
		listener.bind(('', PORT))
		listener.listen(1)
	except: 
		print "Failed to bind to port"
		return None
	
	while True:
		smtp._conn, _ = listener.accept()
		runSMTP()

# Run SMTP protocol for connection
def runSMTP():
	if smtp._conn == None:
		print "Tried to run SMTP without an open connection"
		return None

	smtp.send("220 " + socket.gethostname())
	while True:
		try:
			res = smtp._conn.recv(1024).decode()
			if len(res) == 0: break

			for line in res.split("\r\n"):
				# print(line)
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
					smtp.send("500 Syntax error: command unrecognized")
				
		except ParseException as e:
			smtp.send("501 Syntax error in parameters or arguments")
		except OutOfOrderException:
			smtp.send("503 Bad sequence of commands")
			break
	smtp.reset()
	smtp._conn.close()
	smtp._conn = None

# Start
main()
