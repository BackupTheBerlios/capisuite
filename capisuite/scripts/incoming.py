#              incoming.py - standard incoming script for capisuite
#              ----------------------------------------------------
#    copyright            : (C) 2002 by Gernot Hillier
#    email                : gernot@hillier.de
#    version              : $Revision: 1.18 $
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#

# general imports
import time,os,re,string,pwd
# CapiSuite imports
import capisuite,cs_helpers

# @brief main function called by CapiSuite when an incoming call is received
#
# It will decide if this call should be accepted, with which service and for
# which user. The real call handling is done in faxIncoming and voiceIncoming.
#
# @param call reference to the call. Needed by all capisuite functions
# @param service one of SERVICE_FAXG3, SERVICE_VOICE, SERVICE_OTHER
# @param call_from string containing the number of the calling party
# @param call_to string containing the number of the called party
def callIncoming(call,service,call_from,call_to):
	# read config file and search for call_to in the user sections
	try:
		config=cs_helpers.readConfig()
		userlist=config.sections()
		userlist.remove('GLOBAL')
		curr_user=""

		for u in userlist:
			if config.has_option(u,'voice_numbers'):
				numbers=config.get(u,'voice_numbers')
				if (call_to in numbers.split(',') or numbers=="*"):
					if (service==capisuite.SERVICE_VOICE):
						curr_user=u
						curr_service=capisuite.SERVICE_VOICE
						break
					if (service==capisuite.SERVICE_FAXG3):
						curr_user=u
						curr_service=capisuite.SERVICE_FAXG3
						break

			if config.has_option(u,'fax_numbers'):
				numbers=config.get(u,'fax_numbers')
				if (call_to in numbers.split(',') or numbers=="*"):
				 	if (service in (capisuite.SERVICE_FAXG3,capisuite.SERVICE_VOICE)):
						curr_user=u
						curr_service=capisuite.SERVICE_FAXG3
						break

	except IOError,e:
		capisuite.error("Error occured during config file reading: %s Disconnecting..." % e)
		capisuite.reject(call,0x34A9)
		return
        # answer the call with the right service
	if (curr_user==""):
		capisuite.log("call from %s to %s ignoring" % (call_from,call_to),1,call)
		capisuite.reject(call,1)
		return
	try:
		if (curr_service==capisuite.SERVICE_VOICE):
			delay=cs_helpers.getOption(config,curr_user,"voice_delay")
			if (delay==None):
				capisuite.error("voice_delay not found for user %s! -> rejecting call" % curr_user)
				capisuite.reject(call,0x34A9)
				return
			capisuite.log("call from %s to %s for %s connecting with voice" % (call_from,call_to,curr_user),1,call)
			capisuite.connect_voice(call,int(delay))
			voiceIncoming(call,call_from,call_to,curr_user,config)
		elif (curr_service==capisuite.SERVICE_FAXG3):
			faxIncoming(call,call_from,call_to,curr_user,config,0)
	except capisuite.CallGoneError: # catch exceptions from connect_*
		(cause,causeB3)=capisuite.disconnect(call)
		capisuite.log("connection lost with cause 0x%x,0x%x" % (cause,causeB3),1,call)

# @brief called by callIncoming when an incoming fax call is received
#  
# @param call reference to the call. Needed by all capisuite functions
# @param call_from string containing the number of the calling party
# @param call_to string containing the number of the called party
# @param curr_user name of the user who is responsible for this
# @param config ConfigParser instance holding the config data
# @param already_connected 1 if we're already connected (that means we must switch to fax mode)
def faxIncoming(call,call_from,call_to,curr_user,config,already_connected):
	try:
		udir=cs_helpers.getOption(config,"","fax_user_dir")
		if (udir==None):
			capisuite.error("global option fax_user_dir not found! -> rejecting call")
			capisuite.reject(call,0x34A9)
			return
		udir=os.path.join(udir,curr_user)
		if (not os.path.exists(udir)):
			userdata=pwd.getpwnam(curr_user)
			os.mkdir(udir,0700)
			os.chown(udir,userdata[2],userdata[3])
		if (not os.path.exists(os.path.join(udir,"received"))):
			userdata=pwd.getpwnam(curr_user)
			os.mkdir(os.path.join(udir,"received"),0700)
			os.chown(os.path.join(udir,"received"),userdata[2],userdata[3])
	except KeyError:
		capisuite.error("user %s is not a valid system user. Disconnecting" % curr_user,call)
		capisuite.reject(call,0x34A9)
		return
	filename="" # assure the variable is defined...
	faxInfo=None
	try:
		stationID=cs_helpers.getOption(config,curr_user,"fax_stationID")
		if (stationID==None):
			capisuite.error("Warning: fax_stationID not found for user %s -> using empty string" % curr_user)
			stationID=""
		headline=cs_helpers.getOption(config,curr_user,"fax_headline","") # empty string is no problem here
		capisuite.log("call from %s to %s for %s connecting with fax" % (call_from,call_to,curr_user),1,call)
		if (already_connected):
			faxInfo=capisuite.switch_to_faxG3(call,stationID,headline)
		else:
			faxInfo=capisuite.connect_faxG3(call,stationID,headline,0)
		if (faxInfo!=None and faxInfo[3]==1):
			faxFormat="cff" # color fax
		else:
			faxFormat="sff" # normal b&w fax
		filename=cs_helpers.uniqueName(os.path.join(udir,"received"),"fax",faxFormat)
		faxInfo=capisuite.fax_receive(call,filename)
		(cause,causeB3)=capisuite.disconnect(call)
		capisuite.log("connection finished with cause 0x%x,0x%x" % (cause,causeB3),1,call)

	except capisuite.CallGoneError: # catch this here to get the cause info in the mail
		(cause,causeB3)=capisuite.disconnect(call)
		capisuite.log("connection lost with cause 0x%x,0x%x" % (cause,causeB3),1,call)

	if (os.access(filename,os.R_OK)):
		cs_helpers.writeDescription(filename,
		  "call_from=\"%s\"\ncall_to=\"%s\"\ntime=\"%s\"\n" \
		  "cause=\"0x%x/0x%x\"\n" % (call_from,call_to,time.ctime(),cause,causeB3))
		userdata=pwd.getpwnam(curr_user)
		os.chmod(filename,0600)
		os.chown(filename,userdata[2],userdata[3])
		os.chmod("%stxt" % filename[:-3],0600)
		os.chown("%stxt" % filename[:-3],userdata[2],userdata[3])

		fromaddress=cs_helpers.getOption(config,curr_user,"fax_email_from","")
		if (fromaddress==""):
			fromaddress=curr_user
		mailaddress=cs_helpers.getOption(config,curr_user,"fax_email","")
		if (mailaddress==""):
			mailaddress=curr_user
                action=cs_helpers.getOption(config,curr_user,"fax_action","").lower()
		if (action not in ("mailandsave","saveonly")):
			capisuite.error("Warning: No valid fax_action definition found for user %s -> assuming SaveOnly" % curr_user)
			action="saveonly"
		if (action=="mailandsave"):
			mailText="You got a fax from %s to %s\nDate: %s" % (call_from,call_to,time.ctime())
			if (faxInfo!=None and len(faxInfo)>=5):
				mailText="%sStation ID: %s\nTransmission Details: bit rate %i " \
				  "%s %s\nPages: %i\n\nSee attached file.\n" \
				  "The original file was saved to file://%s " \
				  "on host \"%s\"." % (mailText,faxInfo[0], \
				  faxInfo[1],(faxInfo[2] and "hiRes" or "loRes"), \
				  (faxInfo[3] and "color" or ""),faxInfo[4], \
				  fileName,os.uname()[1])
			cs_helpers.sendMIMEMail(fromaddress, mailaddress, "Fax received from %s to %s" % (call_from,call_to),
			  faxFormat, mailText, filename)

# @brief called by callIncoming when an incoming voice call is received
#
# @param call reference to the call. Needed by all capisuite functions
# @param call_from string containing the number of the calling party
# @param call_to string containing the number of the called party
# @param curr_user name of the user who is responsible for this
# @param config ConfigParser instance holding the config data
def voiceIncoming(call,call_from,call_to,curr_user,config):
	try:
		udir=cs_helpers.getOption(config,"","voice_user_dir")
		if (udir==None):
			capisuite.error("global option voice_user_dir not found! -> rejecting call")
			capisuite.reject(call,0x34A9)
			return
		udir=os.path.join(udir,curr_user)
		if (not os.path.exists(udir)):
			userdata=pwd.getpwnam(curr_user)
			os.mkdir(udir,0700)
			os.chown(udir,userdata[2],userdata[3])
		if (not os.path.exists(os.path.join(udir,"received"))):
			userdata=pwd.getpwnam(curr_user)
			os.mkdir(os.path.join(udir,"received"),0700)
			os.chown(os.path.join(udir,"received"),userdata[2],userdata[3])
	except KeyError:
		capisuite.error("user %s is not a valid system user. Disconnecting" % curr_user,call)
		capisuite.reject(call,0x34A9)
		return
	filename=cs_helpers.uniqueName(os.path.join(udir,"received"),"voice","la")
	action=cs_helpers.getOption(config,curr_user,"voice_action","").lower()
	if (action not in ("mailandsave","saveonly","none")):
		capisuite.error("Warning: No valid voice_action definition found for user %s -> assuming SaveOnly" % curr_user)
		action="saveonly"
	try:
		capisuite.enable_DTMF(call)
		userannouncement=os.path.join(udir,cs_helpers.getOption(config,curr_user,"announcement","announcement.la"))
		pin=cs_helpers.getOption(config,curr_user,"pin","")
		if (os.access(userannouncement,os.R_OK)):
			capisuite.audio_send(call,userannouncement,1)
		else:
			if (call_to!="-"):
				capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"anrufbeantworter-von.la"),1)
				cs_helpers.sayNumber(call,call_to,curr_user,config)
			capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"bitte-nachricht.la"),1)

		if (action!="none"):
			capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"beep.la"),1)
			length=cs_helpers.getOption(config,curr_user,"record_length","60")
			silence_timeout=cs_helpers.getOption(config,curr_user,"record_silence_timeout","5")
			msg_length=capisuite.audio_receive(call,filename,int(length), int(silence_timeout),1)

		dtmf_list=capisuite.read_DTMF(call,0)
		if (dtmf_list=="X"):
			if (os.access(filename,os.R_OK)):
				os.unlink(filename)
			faxIncoming(call,call_from,call_to,curr_user,config,1)
		elif (dtmf_list!="" and pin!=""):
			dtmf_list="%s%s" % (dtmf_list,capisuite.read_DTMF(call,3)) # wait 5 seconds for input
			count=1
			while (count<3 and pin!=dtmf_list):  # try again if input was wrong
				capisuite.log("wrong PIN entered...",1,call)
				capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"beep.la"))
				dtmf_list=capisuite.read_DTMF(call,3)
				count+=1
			if (pin==dtmf_list):
				if (os.access(filename,os.R_OK)):
					os.unlink(filename)
				capisuite.log("Starting remote inquiry...",1,call)
				remoteInquiry(call,udir,curr_user,config)

		(cause,causeB3)=capisuite.disconnect(call)
		capisuite.log("connection finished with cause 0x%x,0x%x" % (cause,causeB3),1,call)

	except capisuite.CallGoneError: # catch this here to get the cause info in the mail
		(cause,causeB3)=capisuite.disconnect(call)
		capisuite.log("connection lost with cause 0x%x,0x%x" % (cause,causeB3),1,call)

	if (os.access(filename,os.R_OK)):
		cs_helpers.writeDescription(filename,
		  "call_from=\"%s\"\ncall_to=\"%s\"\ntime=\"%s\"\n" \
		  "cause=\"0x%x/0x%x\"\n" % (call_from,call_to,time.ctime(),cause,causeB3))
		userdata=pwd.getpwnam(curr_user)
		os.chmod(filename,0600)
		os.chown(filename,userdata[2],userdata[3])
		os.chmod("%stxt" % filename[:-2],0600)
		os.chown("%stxt" % filename[:-2],userdata[2],userdata[3])

		fromaddress=cs_helpers.getOption(config,curr_user,"voice_email_from","")
		if (fromaddress==""):
			fromaddress=curr_user
		mailaddress=cs_helpers.getOption(config,curr_user,"voice_email","")
		if (mailaddress==""):
			mailaddress=curr_user
		if (action=="mailandsave"):
			mailText="You got a voice call from %s to %s\n" \
			  "Date: %s\nLength: %i s\n\nSee attached file.\n" \
			  "The original file was saved to file://%s on" \
			  "host \"%s\".\n\n" % (call_from,call_to,time.ctime(), \
			  msg_length,filename,os.uname()[1])
			subject="Voice call received from %s to %s" % (call_from,call_to)
			cs_helpers.sendMIMEMail(fromaddress,mailaddress,subject,"la",mailText,filename)

# @brief remote inquiry function (uses german wave snippets!)
#
# commands for remote inquiry
# delete message - 1
# next message - 4
# last message - 5
# repeat current message - 6
#
# @param call reference to the call. Needed by all capisuite functions
# @param userdir spool_dir of the current_user
# @param curr_user name of the user who is responsible for this
# @param config ConfigParser instance holding the config data
def remoteInquiry(call,userdir,curr_user,config):
	import time,fcntl,errno,os
	# acquire lock
	lockfile=open(os.path.join(userdir,"received/inquiry_lock"),"w")
	try:
		fcntl.lockf(lockfile,fcntl.LOCK_EX | fcntl.LOCK_NB) # only one inquiry at a time!

	except IOError,err: # can't get the lock
		if (err.errno in (errno.EACCES,errno.EAGAIN)):
			capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"fernabfrage-aktiv.la"))
			lockfile.close()
			return

	try:
		# read directory contents
		messages=os.listdir(os.path.join(userdir,"received"))
		messages=filter (lambda s: re.match("voice-.*\.la",s),messages)  # only use voice-* files
		messages=map(lambda s: int(re.match("voice-([0-9]+)\.la",s).group(1)),messages) # filter out numbers
		messages.sort()

		# read the number of the message heard last at the last inquiry
		lastinquiry=-1
		if (os.access(os.path.join(userdir,"received/last_inquiry"),os.W_OK)):
			lastfile=open(os.path.join(userdir,"received/last_inquiry"),"r")
			lastinquiry=int(lastfile.readline())
			lastfile.close()

		# sort out old messages
		oldmessages=[]
		i=0
		while (i<len(messages)):
			if (messages[i]<=lastinquiry):
				oldmessages.append(messages[i])
				del messages[i]
			else:
				i+=1

		cs_helpers.sayNumber(call,str(len(messages)),curr_user,config,"f")
		if (len(messages)==1):
			capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"neue-nachricht.la"),1)
		else:
			capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"neue-nachrichten.la"),1)

		# menu for record new announcement
		cmd=""
		while (cmd not in ("1","9")):
			if (len(messages)+len(oldmessages)):
				capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"zum-abhoeren-1.la"),1)
			capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"fuer-neue-ansage-9.la"),1)
			cmd=capisuite.read_DTMF(call,0,1)
		if (cmd=="9"):
			newAnnouncement(call,userdir,curr_user,config)
			return

		# start inquiry
		for curr_msgs in (messages,oldmessages):
			cs_helpers.sayNumber(call,str(len(curr_msgs)),curr_user,config,"f")
			if (curr_msgs==messages):
				if (len(curr_msgs)==1):
					capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"neue-nachricht.la"),1)
				else:
					capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"neue-nachrichten.la"),1)
			else:
				if (len(curr_msgs)==1):
					capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"nachricht.la"),1)
				else:
					capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"nachrichten.la"),1)

			i=0
			while (i<len(curr_msgs)):
				filename=os.path.join(userdir,"received/voice-%i.la" % curr_msgs[i])
				descr=cs_helpers.readConfig("%stxt" % filename[:-2])
				capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"nachricht.la"),1)
				cs_helpers.sayNumber(call,str(i+1),curr_user,config)
				capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"von.la"),1)
				cs_helpers.sayNumber(call,descr.get('GLOBAL','call_from'),curr_user,config)
				capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"fuer.la"),1)
				cs_helpers.sayNumber(call,descr.get('GLOBAL','call_to'),curr_user,config)
				capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"am.la"),1)
				calltime=time.strptime(descr.get('GLOBAL','time'))
				cs_helpers.sayNumber(call,str(calltime[2]),curr_user,config)
				capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"..la"),1)
				cs_helpers.sayNumber(call,str(calltime[1]),curr_user,config)
				capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"..la"),1)
				capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"um.la"),1)
				cs_helpers.sayNumber(call,str(calltime[3]),curr_user,config,"n")
				capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"uhr.la"),1)
				cs_helpers.sayNumber(call,str(calltime[4]),curr_user,config)
				capisuite.audio_send(call,filename,1)
				cmd=""
				while (cmd not in ("1","4","5","6")):
					capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"erklaerung.la"),1)
					cmd=capisuite.read_DTMF(call,0,1)
				if (cmd=="1"):
					os.remove(filename)
					os.remove("%stxt" % filename[:-2])
					del curr_msgs[i]
					capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"nachricht-geloescht.la"))
				elif (cmd=="4"):
					if (curr_msgs[i]>lastinquiry):
						lastinquiry=curr_msgs[i]
						lastfile=open(os.path.join(userdir,"received/last_inquiry"),"w")
						lastfile.write("%i\n" % curr_msgs[i])
						lastfile.close()
					i+=1
				elif (cmd=="5"):
					i-=1
		capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"keine-weiteren-nachrichten.la"))

	finally:
		# unlock
		fcntl.lockf(lockfile,fcntl.LOCK_UN)
		lockfile.close()
		os.unlink(os.path.join(userdir,"received/inquiry_lock"))

# @brief remote inquiry: record new announcement (uses german wave snippets!)
#
# @param call reference to the call. Needed by all capisuite functions
# @param userdir spool_dir of the current_user
# @param curr_user name of the user who is responsible for this
# @param config ConfigParser instance holding the config data
def newAnnouncement(call,userdir,curr_user,config):
	capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"bitte-neue-ansage-komplett.la"))
	capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"beep.la"))
	cmd=""
	while (cmd!="1"):
		capisuite.audio_receive(call,os.path.join(userdir,"announcement-tmp.la"),60,3)
		capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"neue-ansage-lautet.la"))
		capisuite.audio_send(call,os.path.join(userdir,"announcement-tmp.la"))
		capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"wenn-einverstanden-1.la"))
		cmd=capisuite.read_DTMF(call,0,1)
		if (cmd!="1"):
			capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"bitte-neue-ansage-kurz.la"))
			capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"beep.la"))
	userannouncement=os.path.join(userdir,cs_helpers.getOption(config,curr_user,"announcement","announcement.la"))
	os.rename(os.path.join(userdir,"announcement-tmp.la"),userannouncement)
	userdata=pwd.getpwnam(curr_user)
	os.chown(userannouncement,userdata[2],userdata[3])

	capisuite.audio_send(call,cs_helpers.getAudio(config,curr_user,"ansage-gespeichert.la"))

#
# History:
#
# Old Log (for new changes see ChangeLog):
# Revision 1.13  2003/12/01 20:53:05  gernot
# - confused "hiRes" and "loRes". Thx to Ingo Goeppert <Ingo.Goeppert@gmx.de>
#   for the report!
#
# Revision 1.12  2003/10/03 13:42:09  gernot
# - added new options "fax_email_from" and "voice_email_from"
#
# Revision 1.11  2003/08/24 12:47:50  gernot
# - faxIncoming tried to reconnect when it was called after a switch from
#   voice to fax mode, which lead to a call abort. Thx to Harald Jansen &
#   Andreas Scholz for reporting!
#
# Revision 1.10  2003/07/20 10:30:37  gernot
# - started implementing faxInfo output in sent mails, not working currently
#
# Revision 1.9  2003/06/27 07:51:09  gernot
# - replaced german umlaut in filename "nachricht-gelscht.la", can cause
#   problems on Redhat, thx to Herbert H�bner for reporting
#
# Revision 1.8  2003/06/16 10:21:05  gernot
# - define filename in any case (thx to Axel Schneck for reporting and
#   analyzing...)
#
# Revision 1.7  2003/05/25 13:38:30  gernot
# - support reception of color fax documents
#
# Revision 1.6  2003/04/10 21:29:51  gernot
# - support empty destination number for incoming calls correctly (austrian
#   telecom does this (sic))
# - core now returns "-" instead of "??" for "no number available" (much nicer
#   in my eyes)
# - new wave file used in remote inquiry for "unknown number"
#
# Revision 1.5  2003/03/20 09:12:42  gernot
# - error checking for reading of configuration improved, many options got
#   optional, others produce senseful error messages now if not found,
#   fixes bug# 531, thx to Dieter Pelzel for reporting
#
# Revision 1.4  2003/03/13 11:08:06  gernot
# - fix remote inquiry locking (should fix bug #534, but doesn't - anyway,
#   this fix is definitely necessary)
# - stricter permissions of saved files and created dirs, fixes #544
# - add "file://" prefix to the path shown in the mails to the user
#
# Revision 1.3  2003/02/21 13:13:34  gernot
# - removed some debug output (oops...)
#
# Revision 1.2  2003/02/21 11:02:17  gernot
# - removed os.setuid() from incoming script
#   -> fixes Bug #527
#
# Revision 1.1.1.1  2003/02/19 08:19:54  gernot
# initial checkin of 0.4
#
# Revision 1.11  2003/02/17 11:13:43  ghillie
# - remoteinquiry supports new and old messages now
#
# Revision 1.10  2003/02/03 14:50:08  ghillie
# - fixed small typo
#
# Revision 1.9  2003/01/31 16:32:41  ghillie
# - support "*" for "all numbers"
# - automatic switch voice->fax when SI says fax
#
# Revision 1.8  2003/01/31 11:24:41  ghillie
# - wrong user handling for more than one users fixed
# - creates user_dir/user and user_dir/user/received now separately as
#   idle.py can also create user_dir/user now
#
# Revision 1.7  2003/01/27 21:57:54  ghillie
# - fax_numbers and voice_numbers may not exist (no fatal error any more)
# - accept missing email option
# - fixed typo
#
# Revision 1.6  2003/01/27 19:24:29  ghillie
# - updated to use new configuration files for fax & answering machine
#
# Revision 1.5  2003/01/19 12:03:27  ghillie
# - use capisuite log functions instead of stdout/stderr
#
# Revision 1.4  2003/01/17 15:09:49  ghillie
# - cs_helpers.sendMail was renamed to sendMIMEMail
#
# Revision 1.3  2003/01/16 12:58:34  ghillie
# - changed DTMF timeout for pin to 3 seconds
# - delete recorded wave if fax or remote inquiry is recognized
# - updates in remoteInquiry: added menu for recording own announcement
# - fixed some typos
# - remoteInquiry: delete description file together with call if requested
# - new function: newAnnouncement
#
# Revision 1.2  2003/01/15 15:55:12  ghillie
# - added exception handler in callIncoming
# - faxIncoming: small typo corrected
# - voiceIncoming & remoteInquiry: updated to new config file system
#
# Revision 1.1  2003/01/13 16:12:58  ghillie
# - renamed from incoming.pyin to incoming.py as all previously processed
#   variables are moved to config and cs_helpers.pyin
#
# Revision 1.4  2002/12/18 14:34:56  ghillie
# - added some informational prints
# - accept voice calls to fax nr
#
# Revision 1.3  2002/12/16 15:04:51  ghillie
# - added missing path prefix to delete routing in remote inquiry
#
# Revision 1.2  2002/12/16 13:09:25  ghillie
# - added some comments about the conf_* vars
# - added conf_wavedir
# - added support for B3 cause now returned by disconnect()
# - corrected some dir entries to work in installed system
#
# Revision 1.1  2002/12/14 13:53:18  ghillie
# - idle.py and incoming.py are now auto-created from *.pyin
#
# Revision 1.4  2002/12/11 12:58:05  ghillie
# - read return value from disconnect()
# - added disconnect() to exception handler
#
# Revision 1.3  2002/12/09 15:18:35  ghillie
# - added disconnect() in exception handler
#
# Revision 1.2  2002/12/02 21:30:42  ghillie
# fixed some minor typos
#
# Revision 1.1  2002/12/02 21:15:55  ghillie
# - moved scripts to own directory
# - added remote-connect script to repository
#
# Revision 1.20  2002/12/02 20:59:44  ghillie
# another typo :-|
#
# Revision 1.19  2002/12/02 20:54:07  ghillie
# fixed small typo
#
# Revision 1.18  2002/12/02 16:51:32  ghillie
# nearly complete new script, supports answering machine, fax receiving and remote inquiry now
#
# Revision 1.17  2002/11/29 16:28:43  ghillie
# - updated syntax (connect_telephony -> connect_voice)
#
# Revision 1.16  2002/11/29 11:09:04  ghillie
# renamed CapiCom to CapiSuite (name conflict with MS crypto API :-( )
#
# Revision 1.15  2002/11/25 11:43:43  ghillie
# updated to new syntax
#
# Revision 1.14  2002/11/23 16:16:17  ghillie
# moved switch2fax after audio_receive()
#
# Revision 1.13  2002/11/22 15:48:58  ghillie
# renamed pcallcontrol module to capicom
#
# Revision 1.12  2002/11/22 15:02:39  ghillie
# - added automatic switch between speech and fax
# - some comments added
#
# Revision 1.11  2002/11/19 15:57:18  ghillie
# - Added missing throw() declarations
# - phew. Added error handling. All exceptions are caught now.
#
# Revision 1.10  2002/11/18 12:32:36  ghillie
# - callIncoming lives now in __main__, not necessarily in pcallcontrol any more
# - added some comments and header
#
