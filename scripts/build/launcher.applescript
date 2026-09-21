on run
	set defaultPath to "/Users/imamimam/Documents/GitHub/autojurnal"
	
	-- Determine project path
	tell application "Finder"
		set appFolder to (container of (path to me)) as alias
		set appPosix to POSIX path of appFolder
	end tell
	
	set projectPath to ""
	if (do shell script "test -f " & quoted form of (appPosix & "backend/main.py") & " && echo 'yes' || echo 'no'") is "yes" then
		set projectPath to appPosix
	else if (do shell script "test -f " & quoted form of (defaultPath & "/backend/main.py") & " && echo 'yes' || echo 'no'") is "yes" then
		set projectPath to defaultPath
	else if (do shell script "test -f ~/.autojurnal/project_root.txt && test -f \"$(cat ~/.autojurnal/project_root.txt)/backend/main.py\" && echo 'yes' || echo 'no'") is "yes" then
		set projectPath to (do shell script "cat ~/.autojurnal/project_root.txt")
	else
		try
			set chosenFolder to (choose folder with prompt "Pilih folder project AutoJurnal:")
			set projectPath to POSIX path of chosenFolder
		on error
			return
		end try
	end if
	
	-- Save project path
	do shell script "mkdir -p ~/.autojurnal && echo " & quoted form of projectPath & " > ~/.autojurnal/project_root.txt"
	
	-- Helper to open in dedicated App Window
	set openAppWindowCmd to "
if [ -d '/Applications/Google Chrome.app' ]; then
    open -na 'Google Chrome' --args --app='http://localhost:8000' --user-data-dir=\"$HOME/.autojurnal/app_profile\"
elif [ -d '/Applications/Microsoft Edge.app' ]; then
    open -na 'Microsoft Edge' --args --app='http://localhost:8000' --user-data-dir=\"$HOME/.autojurnal/app_profile\"
elif [ -d '/Applications/Brave Browser.app' ]; then
    open -na 'Brave Browser' --args --app='http://localhost:8000' --user-data-dir=\"$HOME/.autojurnal/app_profile\"
else
    open 'http://localhost:8000'
fi
"
	
	-- Check if port 8000 is active
	set runningPid to (do shell script "lsof -ti :8000 2>/dev/null || true")
	if runningPid is not "" then
		set userChoice to button returned of (display dialog "AutoJurnal saat ini sedang aktif di port 8000." with title "AutoJurnal" buttons {"Batal", "Hentikan Server", "Buka Aplikasi"} default button "Buka Aplikasi" with icon note)
		if userChoice is "Buka Aplikasi" then
			do shell script openAppWindowCmd
			return
		else if userChoice is "Hentikan Server" then
			set stopCmd to "
if [ -f " & quoted form of (projectPath & "/stop.sh") & " ]; then
    bash " & quoted form of (projectPath & "/stop.sh") & "
else
    PIDS=$(lsof -ti :8000 2>/dev/null || true)
    for p in $PIDS; do kill -9 $p 2>/dev/null || true; done
    pkill -9 -f 'uvicorn.*backend.main' 2>/dev/null || true
    pkill -9 -f 'backend.main:app' 2>/dev/null || true
fi
"
			do shell script stopCmd
			display notification "Server AutoJurnal telah dihentikan." with title "AutoJurnal"
			return
		else
			return
		end if
	end if
	
	-- Start server in background
	display notification "Memulai server AutoJurnal..." with title "AutoJurnal"
	
	set launchCmd to "export PATH='/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.local/bin:$PATH'; " & ¬
		"export LC_ALL=en_US.UTF-8; export LANG=en_US.UTF-8; " & ¬
		"export MPLCONFIGDIR=/tmp/matplotlib; export MPLBACKEND=Agg; mkdir -p /tmp/matplotlib; " & ¬
		"cd " & quoted form of projectPath & " && " & ¬
		"if [ -f venv/bin/python ]; then PY=venv/bin/python; else PY=python3; fi; " & ¬
		"nohup $PY -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 > ~/.autojurnal/server.log 2>&1 &"
	
	do shell script launchCmd
	
	-- Wait for server to be responsive
	set isReady to false
	repeat 30 times
		set checkStatus to (do shell script "curl -s -m 1 http://127.0.0.1:8000 >/dev/null 2>&1 && echo 'ok' || echo 'waiting'")
		if checkStatus is "ok" then
			set isReady to true
			exit repeat
		end if
		delay 0.5
	end repeat
	
	if isReady then
		do shell script openAppWindowCmd
		display notification "AutoJurnal aktif di window aplikasi!" with title "AutoJurnal"
	else
		set lastLog to (do shell script "tail -n 8 ~/.autojurnal/server.log 2>/dev/null || echo 'No log'")
		display alert "Gagal Memulai AutoJurnal" message "Server tidak merespons:\n\n" & lastLog
	end if
end run
