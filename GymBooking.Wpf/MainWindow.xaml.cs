using System.Text;
using System.Text.Json;
using System.Windows;
using System.Windows.Threading;
using GymBooking.Wpf.Models;
using GymBooking.Wpf.Services;
using System.IO;
using System.Windows.Input;

namespace GymBooking.Wpf;

public partial class MainWindow : Window
{
    private readonly BookingService _bookingService = new();
    private readonly DispatcherTimer _countdownTimer;
    private readonly StringBuilder _logBuilder = new();
    private CancellationTokenSource? _runCts;
    private const string ConfigPath = "booking_config.json";

    public MainWindow()
    {
        InitializeComponent();

        StateChanged += (_, _) => UpdateMaxRestoreIcon();

        _countdownTimer = new DispatcherTimer
        {
            Interval = TimeSpan.FromSeconds(1)
        };
        _countdownTimer.Tick += (_, _) => UpdateCountdownLabel();
        _countdownTimer.Start();

        LoadConfig();
        UpdateCountdownLabel();
        UpdateMaxRestoreIcon();
        SetIdle();
    }

    private async void OnStart(object sender, RoutedEventArgs e)
    {
        if (_runCts is not null)
        {
            return;
        }

        if (!TryBuildRequest(out var request))
        {
            return;
        }

        if (RememberBox.IsChecked == true)
        {
            SaveConfig(request);
        }

        _runCts = new CancellationTokenSource();
        StatusLabel.Text = "Running...";
        StartButton.IsEnabled = false;
        CancelButton.IsEnabled = true;
        ClearLog();
        Log("Starting...");

        try
        {
            await _bookingService.RunAsync(request, Log, _runCts.Token);
            StatusLabel.Text = "Done";
            Log("Done.");
        }
        catch (OperationCanceledException)
        {
            StatusLabel.Text = "Canceled";
            Log("Canceled by user.");
        }
        catch (Exception ex)
        {
            StatusLabel.Text = "Error";
            Log($"Error: {ex.Message}");
            MessageBox.Show(ex.Message, "Booking error", MessageBoxButton.OK, MessageBoxImage.Error);
        }
        finally
        {
            _runCts.Dispose();
            _runCts = null;
            StartButton.IsEnabled = true;
            CancelButton.IsEnabled = false;
        }
    }

    private void OnCancel(object sender, RoutedEventArgs e)
    {
        _runCts?.Cancel();
    }

    private void OnToggleMaxRestore(object sender, RoutedEventArgs e)
    {
        WindowState = WindowState == WindowState.Maximized ? WindowState.Normal : WindowState.Maximized;
        UpdateMaxRestoreIcon();
    }

    private void OnMinimize(object sender, RoutedEventArgs e)
    {
        WindowState = WindowState.Minimized;
    }

    private void OnClose(object sender, RoutedEventArgs e)
    {
        Close();
    }

    private void TitleBar_MouseDown(object sender, MouseButtonEventArgs e)
    {
        if (e.ChangedButton == MouseButton.Left)
        {
            if (e.ClickCount == 2)
            {
                WindowState = WindowState == WindowState.Maximized ? WindowState.Normal : WindowState.Maximized;
            }
            else
            {
                DragMove();
            }
        }
    }

    private bool TryBuildRequest(out BookingRequest request)
    {
        request = null!;
        if (string.IsNullOrWhiteSpace(UsernameBox.Text) || string.IsNullOrWhiteSpace(PasswordBox.Password))
        {
            MessageBox.Show("Username and password are required.", "Validation", MessageBoxButton.OK, MessageBoxImage.Information);
            return false;
        }

        if (!int.TryParse(DayBox.Text, out var day) || day < 1 || day > 31)
        {
            MessageBox.Show("Enter a valid day (1-31).", "Validation", MessageBoxButton.OK, MessageBoxImage.Information);
            return false;
        }

        if (!int.TryParse(MonthBox.Text, out var month) || month < 1 || month > 12)
        {
            MessageBox.Show("Enter a valid month (1-12).", "Validation", MessageBoxButton.OK, MessageBoxImage.Information);
            return false;
        }

        if (!int.TryParse(DayAttemptsBox.Text, out var attempts) || attempts < 1)
        {
            attempts = 5;
        }

        var today = DateOnly.FromDateTime(DateTime.Today);
        var target = new DateOnly(today.Year, month, day);

        request = new BookingRequest
        {
            Username = UsernameBox.Text.Trim(),
            Password = PasswordBox.Password.Trim(),
            TargetDate = target,
            DayAttempts = attempts,
            PrimarySlot = GetPrimarySlot(),
            WaitForMidnight = WaitMidnightBox.IsChecked == true,
            TryOtherSlots = TryOthersBox.IsChecked == true
        };
        return true;
    }

    private SlotSelection GetPrimarySlot()
    {
        if (Slot1.IsChecked == true) return SlotSelection.Slot1;
        if (Slot2.IsChecked == true) return SlotSelection.Slot2;
        if (Slot3.IsChecked == true) return SlotSelection.Slot3;
        return SlotSelection.Slot0;
    }

    private void Log(string message)
    {
        Dispatcher.Invoke(() =>
        {
            var line = $"[{DateTime.Now:HH:mm:ss}] {message}";
            _logBuilder.AppendLine(line);
            LogBlock.Text = _logBuilder.ToString();
        });
    }

    private void ClearLog()
    {
        _logBuilder.Clear();
        LogBlock.Text = string.Empty;
    }

    private void UpdateCountdownLabel()
    {
        var now = DateTime.Now;
        var midnight = now.Date.AddDays(1);
        var remaining = midnight - now;
        var useMidnight = WaitMidnightBox.IsChecked == true;

        CountdownTitle.Text = useMidnight ? "Countdown to midnight" : "Countdown";
        if (remaining < TimeSpan.Zero)
        {
            remaining = TimeSpan.Zero;
        }
        CountdownLabel.Text = $"{remaining:hh\\:mm\\:ss}";
    }

    private void SetIdle()
    {
        StatusLabel.Text = "Idle";
        CancelButton.IsEnabled = false;
    }

    private void UpdateMaxRestoreIcon()
    {
        if (MaxRestoreButton is null)
        {
            return;
        }

        MaxRestoreButton.Content = WindowState == WindowState.Maximized ? "\uE923" : "\uE922";
    }

    private void LoadConfig()
    {
        try
        {
            if (!File.Exists(ConfigPath))
            {
                return;
            }

            var json = File.ReadAllText(ConfigPath);
            var data = JsonSerializer.Deserialize<Dictionary<string, string>>(json);
            if (data is null)
            {
                return;
            }

            data.TryGetValue("username", out var u);
            data.TryGetValue("password", out var p);
            data.TryGetValue("day", out var d);
            data.TryGetValue("month", out var m);
            data.TryGetValue("slot_idx", out var slotIdx);
            data.TryGetValue("day_attempts", out var attempts);
            data.TryGetValue("wait_midnight", out var waitMidnight);
            data.TryGetValue("try_other_slots", out var tryOthers);

            UsernameBox.Text = u ?? string.Empty;
            PasswordBox.Password = p ?? string.Empty;
            if (!string.IsNullOrWhiteSpace(d)) DayBox.Text = d;
            if (!string.IsNullOrWhiteSpace(m)) MonthBox.Text = m;
            if (!string.IsNullOrWhiteSpace(attempts)) DayAttemptsBox.Text = attempts;
            if (waitMidnight == "True" || waitMidnight == "true") WaitMidnightBox.IsChecked = true;
            if (tryOthers == "True" || tryOthers == "true") TryOthersBox.IsChecked = true;

            Slot0.IsChecked = slotIdx != "1" && slotIdx != "2" && slotIdx != "3";
            Slot1.IsChecked = slotIdx == "1";
            Slot2.IsChecked = slotIdx == "2";
            Slot3.IsChecked = slotIdx == "3";

            RememberBox.IsChecked = true;
        }
        catch
        {
            // Swallow config load errors; keep UI clean.
        }
    }

    private void SaveConfig(BookingRequest request)
    {
        try
        {
            var payload = new Dictionary<string, string>
            {
                ["username"] = request.Username,
                ["password"] = request.Password,
                ["day"] = request.TargetDate.Day.ToString(),
                ["month"] = request.TargetDate.Month.ToString(),
                ["slot_idx"] = ((int)request.PrimarySlot).ToString(),
                ["wait_midnight"] = request.WaitForMidnight.ToString(),
                ["try_other_slots"] = request.TryOtherSlots.ToString(),
                ["day_attempts"] = request.DayAttempts.ToString()
            };
            File.WriteAllText(ConfigPath, JsonSerializer.Serialize(payload, new JsonSerializerOptions { WriteIndented = true }));
        }
        catch
        {
            // Ignore config persistence failures to avoid blocking runs.
        }
    }
}
