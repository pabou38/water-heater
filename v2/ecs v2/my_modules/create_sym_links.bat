: v2.0

: : is not displayed. rem is displayed

rem for micropython

rem WARNING !!!! search for COMMAND PROMPT (not powershell) and run as admin
rem WARNING. edit cd to micropython project dir

: to run cut and paste below AFTER updating cd above
: c:\Users\pboud\micropython\"MY MODULES"\create_sym_links.bat

: structure on windows:
: HOME/micropython
: HOME/Blynk


: sym link generic modules located in ../my modules (ie HOME/micropython/my modules) and ../../Blynk (ie HOME/Blynk)
: those are Windows directory
: HOME/Blynk also used for windows / python app - add to sys.path
: Home/Blynk also used on linux/raspberry


: WHY symlink for micropython ? 
: file needs to be in vscode project folder for pymakr upload (can be in any dir if this dir is included in sys.path of micropython script)
: edits when developping application will ACCUMULATE in a single (cross application) version. single version of "last version".
: WARNING: other application may need to be modified to adapt to the lastest version. necessary pain I guess

:creates sym link to ôoint to generic micropython modules
:both my modules and Blynk
:delete before creating


cd c:\users\pboud\micropython


rem please cd to project directory
: === >WARNING cd to project directory
:eg cd "modbus PZEM"

cd "ecs v2"


rem deleting old symlink
rmdir my_modules
rmdir Blynk


mklink /D my_modules ..\"MY MODULES"\

: if linking entiere Blynk, pymakr sync project will copy blynk server data, START etc ..
: Blynk\Blynk _client is the code to be imported, rest of Blynk is server
: from micropython/<app> to Blynk/Blynk_client
mklink /D Blynk ..\..\Blynk\Blynk_client


: Blynk and my_modules are windows dir, to be uploaded to ESP under /

:make sure my_modules and Blynk are in micropython sys.path

:failed to upload c:\Users\pboud\micropython\watering to / 
:Reason: Error: ENOENT: no such file or directory, stat 'c:\Users\pboud\micropython\watering/Blynk/my_blynk_new.py'