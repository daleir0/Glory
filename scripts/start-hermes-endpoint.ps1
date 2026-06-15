# Launch Hermes' HTTP endpoint (port 8083), hidden, kept alive.
$env:PATH = "C:\Users\dalei\AppData\Roaming\npm;" + $env:PATH + ";C:\Program Files\nodejs"
$py = (Get-Command python).Source
Start-Process -WindowStyle Hidden -FilePath $py `
    -ArgumentList "E:\Glory\scripts\hermes-endpoint.py" `
    -RedirectStandardOutput "E:\Glory\logs\hermes-endpoint.log" `
    -RedirectStandardError "E:\Glory\logs\hermes-endpoint.err"
