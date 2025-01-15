#!/usr/bin/env python
#coding:utf-8
"""
	Documentation
		Allows to send notifications to the user. Ie using pop-ups or notification tray.
		Can be run as main.
		use the function `notify`.
	Params
		title: string with the title
		message: string with the message
		icon: string with the path to an icon
		val: int progress value
		nag: bool should the user be nagged? message will be printed
"""

__version__ = "0.1a"

__author__ = "Jeronimo Barraco Marmol"

import sys, subprocess, os
import libs.os_utils.v0_1 as os_utils

# values used for the popup. No need to change
KEY = "string:x-canonical-private-synchronous:"

tkroot = None
def showNag(title, msg):
	try:
		import Tkinter
		import tkMessageBox
		global tkroot
		if not tkroot:
			tkroot = Tkinter.Tk()
			tkroot.withdraw()
		tkMessageBox.showerror(title, msg)
	except Exception, e:
		print ("Error showing tkinter notification, please check if it's installed")
		print (e)

def _notifyLin(title, msg, icon="", val=0, nag=False):
	command = "notify-send"
	subprocess.call([command, title, "--icon=" + icon, "-h", KEY, "-h", "int:value:" + str(val), msg])
	if nag:
		showNag(title, msg)

def _notifyMac(title, msg, icon="", val=0, nag=False):
	# this method doesn't work, as there's some weird quotation modification happening
	# command = "/usr/bin/osascript"
	# param = """'display notification "%s" with title "%s"'""" % (title, msg)
	# subprocess.call([command, '-e', param])
	# It is not possible to change the icon of a notification via osascript
	command = """osascript -e 'display notification "{}" with title "{}"' """
	os.system(command.format(msg, title))
	if nag:
		showNag(title, msg)
		pass

def _notifyWin(title, msg, icon="", val=0, nag=False):
	if nag:
		showNag(title, msg)
	else:
		print("%s\n\t%s\n" % (title, msg))

	command = "powershell"
	param = """
[void] [System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms")
$notification = New-Object System.Windows.Forms.NotifyIcon;
$notification.Icon = [System.Drawing.SystemIcons]::Information;
$notification.BalloonTipTitle = "{}";
$notification.BalloonTipIcon = "Info";
$notification.BalloonTipText = "{}";
$notification.Visible = $True;
$notification.ShowBalloonTip(600);
""".format(title, msg) 
	# this works but is super annoying
	# subprocess.call([command, param])

def notify(title, msg, icon="", val=0, nag=False):
	"""This is the main function, that will call the corresponding one depending on the platform"""
	if os_utils.PLAT == os_utils. P_LIN:
		_notifyLin(title, msg, icon, val, nag)
	elif os_utils.PLAT == os_utils.P_MAC:
		_notifyMac(title, msg, icon, val)
	else:
		_notifyWin(title, msg, icon, val, nag)

	if nag:
		print("%s\n\t%s\n" % (title, msg))

if __name__ == "__main__":
	args = sys.argv[1:]

	title = args.pop(0) if args else ""
	msg = args.pop(0) if args else ""
	icon = args.pop(0) if args else ""
	val = int(args.pop(0)) if args else 0
	nag = bool(args.pop(0)) if args else False

	notify(title, msg, icon, val, nag)
