# Gym Slot Automation (WPF)

Windows desktop app to automate gym slot booking with a clean UI, countdown-to-midnight helper, and live log view. Uses Playwright under the hood.

## Prerequisites
- Windows 10/11
- .NET 8 SDK
- PowerShell

## Build and package
From the repo root (`C:\Users\alika\Desktop\gym`):

```powershell
# Restore and build
dotnet build GymBooking.Wpf/GymBooking.Wpf.csproj -c Release

# Install Playwright browser (places files under bin/Release/net8.0-windows/ms-playwright)
powershell -ExecutionPolicy Bypass -File ".\GymBooking.Wpf\bin\Release\net8.0-windows\playwright.ps1" install chromium

# Publish self-contained single file
dotnet publish GymBooking.Wpf/GymBooking.Wpf.csproj `
  -c Release -r win-x64 --self-contained true `
  -p:PublishSingleFile=true -p:IncludeAllContentForSelfExtract=true -p:PublishTrimmed=false

# Copy Playwright payload into the publish folder
Copy-Item -Recurse -Force `
  ".\GymBooking.Wpf\bin\Release\net8.0-windows\ms-playwright" `
  ".\GymBooking.Wpf\bin\Release\net8.0-windows\win-x64\publish\"
```

Share `GymBooking.Wpf\bin\Release\net8.0-windows\win-x64\publish\` as a zip. Users can run `GymBooking.Wpf.exe` directly.

## Usage
- Fill credentials, target date, preferred slot, and options.
- Click **Start booking**; **Cancel** stops the run.
- Enable **Remember** to persist inputs to `booking_config.json` locally.
- Logs stream in the right-hand panel; a screenshot (`booking_result.png`) is saved beside the app after each run.

## Repo contents
- `GymBooking.Wpf/` – WPF app UI and automation client.
- `booking_backend.py`, `gui.py` – supporting Python scripts (not required for the WPF build).
- `booking_config.json` – local-only saved inputs (ignored by git).
