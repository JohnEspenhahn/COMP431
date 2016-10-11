import sys
import re
from socket import *

# Possible states of the state machine
class States:MAIL_FROM, RCPT_TO_FIRST, RCPT_TO, DATA, EOF = range(5)

# Class to manage state of the machine
class SMTPState:
	def __init__(self):
		self.reset()	

	def reset(self):
		self.state = States.MAIL_FROM
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
			with open("forward/" + to_mailbox, "a") as f:
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

# Check for the pattern, if found remove it. Otherwise throw parse exception
def match(name, pattern, token):
	match = re.match(pattern, token)
	if match == None: raise ParseException(name)
	else: return re.sub(pattern, "", token)

# Check for the <path> object. If found remove, otherwise throw parse exception
re_path = re.compile("^<(.+?)>")
re_mailbox = re.compile("^(.+?)@(.+?)$")
re_local_part_ascii = re.compile(r"^[\x00-\x7F]+$")
re_local_part_char = re.compile(r"^[^ \t<>()\[\]\\\.,;:@\"]+$")
re_domain_elem = re.compile("^[a-zA-Z][a-zA-Z0-9]+$")
def match_path(token):
	# Check <path> token
	match = re.match(re_path, token)
	if match == None: raise ParseException("path")
	
	# Store mailbox to return if parse matched 
	mailbox = match.group(1)

	# Check <mailbox> token	
	match = re.match(re_mailbox, match.group(1))
	if match == None: raise ParseException("mailbox")

	# Arbitrary number of "domain elements" seperated by "."
	domain_elems = match.group(2).split(".")

	# Check is ascii, then check not illegal char
	match = re.match(re_local_part_ascii, match.group(1))
	if match == None: raise ParseException("local-part")
	match = re.match(re_local_part_char, match.group(0))
	if match == None: raise ParseException("local-part")

	# Check all domain elements
	for de in domain_elems:
		match = re.match(re_domain_elem, de)
		if match == None: raise ParseException("domain")

	# Return passed in token with matched path removed, and matched mailbox
	return re.sub(re_path, "", token), mailbox

# Main loop
while smtp.state != States.EOF:
	try:
		line = raw_input()
		print(line)
		if smtp.state == States.DATA:
			readdata(line)
		elif re.match(re_data_1, line):
			data(line)
		elif re.match(re_rcpt_to_1, line):
			rcptto(line)
		elif re.match(re_mail_from_1, line):
			mailfrom(line)
		else:
			print("500 Syntax error: command unrecognized")
	except EOFError:
		smtp.state = States.EOF
	except ParseException as e:
		# print(str(e))
		print("501 Syntax error in parameters or arguments")
	except OutOfOrderException:
		print("503 Bad sequence of commands")
		smtp.reset()
