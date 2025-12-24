using GymBooking.Wpf.Models;
using Microsoft.Playwright;

namespace GymBooking.Wpf.Services;

public sealed class BookingService
{
    private const string SelUsername = "#UC_Login_TXTUser";
    private const string SelPassword = "#UC_Login_TXTPwd";
    private const string SelLoginBtn = "#UC_Login_BTNLogin1";
    private const string SelNavPrenotazioni = "#BoxHeader_HyperLink3";
    private const string SelFreeFitness = "#UC_ElencoPrenotazioni_HLFreeFitness";
    private const string SelCalendar = "#UC_FreeFitness_Calendar1";
    private const string SelSlot0 = "#UC_FreeFitness_GVPeriodi_CBScelta_0";
    private const string SelSlot1 = "#UC_FreeFitness_GVPeriodi_CBScelta_1";
    private const string SelSlot2 = "#UC_FreeFitness_GVPeriodi_CBScelta_2";
    private const string SelSlot3 = "#UC_FreeFitness_GVPeriodi_CBScelta_3";
    private const string SelConfirm = "#UC_FreeFitness_LBConferma";

    private const string UrlLogin = "https://servizi.custorino.it/loginareariservata.aspx";

    private static readonly string[] MonthIt =
    [
        "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
        "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"
    ];

    public async Task RunAsync(BookingRequest request, Action<string> log, CancellationToken token)
    {
        token.ThrowIfCancellationRequested();
        using var playwright = await Playwright.CreateAsync();
        await using var browser = await playwright.Chromium.LaunchAsync(new BrowserTypeLaunchOptions
        {
            Headless = false
        });
        var page = await browser.NewPageAsync();

        await page.GotoAsync(UrlLogin, new PageGotoOptions { WaitUntil = WaitUntilState.DOMContentLoaded });
        log("Loaded login page.");

        await page.FillAsync(SelUsername, request.Username);
        await page.FillAsync(SelPassword, request.Password);
        await page.ClickAsync(SelLoginBtn);
        await page.WaitForTimeoutAsync(1500);

        if (await page.IsVisibleAsync(SelNavPrenotazioni))
        {
            log("Login confirmed.");
        }
        else
        {
            log("Login not confirmed; retrying after reload...");
            await page.ReloadAsync(new PageReloadOptions { WaitUntil = WaitUntilState.DOMContentLoaded });
            await page.FillAsync(SelUsername, request.Username);
            await page.FillAsync(SelPassword, request.Password);
            await page.ClickAsync(SelLoginBtn);
            await page.WaitForTimeoutAsync(1500);
            if (!await page.IsVisibleAsync(SelNavPrenotazioni))
            {
                throw new InvalidOperationException("Login failed; verify credentials or check for popups.");
            }
        }

        await page.ClickAsync(SelNavPrenotazioni);
        await page.WaitForLoadStateAsync(LoadState.DOMContentLoaded);
        log("Opened Prenotazioni.");

        var popupTask = page.WaitForPopupAsync();
        await page.ClickAsync(SelFreeFitness);
        var freePage = await popupTask;
        await freePage.WaitForLoadStateAsync(LoadState.DOMContentLoaded);
        log("Opened Free Fitness page.");

        if (request.WaitForMidnight)
        {
            var waitSeconds = SecondsUntilMidnight();
            if (waitSeconds > request.StartEarlySeconds)
            {
                var sleep = TimeSpan.FromSeconds(waitSeconds - request.StartEarlySeconds);
                log($"Waiting {sleep.TotalSeconds:F0}s (start {request.StartEarlySeconds}s before midnight)...");
                await Task.Delay(sleep, token);
            }
            await freePage.ReloadAsync(new PageReloadOptions { WaitUntil = WaitUntilState.DOMContentLoaded });
        }

        log($"Target date: {request.TargetDate}");
        await ClickDayWithRetryAsync(freePage, request.TargetDate.Day, request.TargetDate.Month, request.DayAttempts, log, token);

        var slotOrder = BuildSlots(request.PrimarySlot, request.TryOtherSlots);
        Exception? lastError = null;

        foreach (var slotSelector in slotOrder)
        {
            token.ThrowIfCancellationRequested();
            try
            {
                if (!await freePage.IsEnabledAsync(slotSelector))
                {
                    log($"{slotSelector} disabled/full; skipping.");
                    continue;
                }

                await freePage.CheckAsync(slotSelector, new PageCheckOptions { Force = true });
                log($"Slot selected ({slotSelector}); submitting.");

                await freePage.ClickAsync(SelConfirm);
                log("Confirm clicked; waiting for server response.");
                await freePage.WaitForTimeoutAsync(2000);
                await freePage.ScreenshotAsync(new PageScreenshotOptions
                {
                    Path = "booking_result.png",
                    FullPage = true
                });
                log("Attempted booking; see booking_result.png");
                log("Booking flow completed.");
                await browser.CloseAsync();
                return;
            }
            catch (Exception ex)
            {
                lastError = ex;
                log($"Slot attempt failed ({slotSelector}): {ex.Message}");
            }
        }

        await browser.CloseAsync();
        throw new InvalidOperationException(lastError?.Message ?? "All slots disabled or failed.");
    }

    private static IReadOnlyList<string> BuildSlots(SlotSelection primary, bool tryOthers)
    {
        var order = new List<string> { SelectorFor(primary) };
        if (tryOthers)
        {
            var all = new[] { SelSlot0, SelSlot1, SelSlot2, SelSlot3 };
            foreach (var slot in all)
            {
                if (!order.Contains(slot))
                {
                    order.Add(slot);
                }
            }
        }

        return order;
    }

    private static string SelectorFor(SlotSelection slot) => slot switch
    {
        SlotSelection.Slot0 => SelSlot0,
        SlotSelection.Slot1 => SelSlot1,
        SlotSelection.Slot2 => SelSlot2,
        SlotSelection.Slot3 => SelSlot3,
        _ => SelSlot0
    };

    private static async Task ClickDayWithRetryAsync(
        IPage page,
        int day,
        int month,
        int attempts,
        Action<string> log,
        CancellationToken token)
    {
        var monthName = MonthIt[month - 1];
        for (var i = 1; i <= attempts; i++)
        {
            token.ThrowIfCancellationRequested();
            try
            {
                var calendar = page.Locator(SelCalendar);
                var titleSel = $"a[title=\"{day} {monthName}\"]";
                var anchor = calendar.Locator(titleSel);
                var fallback = calendar.Locator($"a:has-text(\"{day}\")");
                var hasAnchor = await anchor.CountAsync() > 0 || await fallback.CountAsync() > 0;

                if (hasAnchor)
                {
                    await ClickDayAsync(page, day, month);
                    log($"Clicked day {day} on attempt {i}.");
                    return;
                }

                log($"Attempt {i}: day {day} anchor not found; reloading...");
                await page.ReloadAsync(new PageReloadOptions { WaitUntil = WaitUntilState.DOMContentLoaded });
            }
            catch (Exception ex)
            {
                log($"Attempt {i} failed to click day {day}; retrying... ({ex.Message})");
                await page.ReloadAsync(new PageReloadOptions { WaitUntil = WaitUntilState.DOMContentLoaded });
            }

            await page.WaitForTimeoutAsync(60);
        }

        throw new InvalidOperationException($"Could not click day {day} after {attempts} attempts");
    }

    private static async Task ClickDayAsync(IPage page, int day, int month)
    {
        var monthName = MonthIt[month - 1];
        var calendar = page.Locator(SelCalendar);
        var titleSel = $"a[title=\"{day} {monthName}\"]";
        var anchor = calendar.Locator(titleSel);
        if (await anchor.CountAsync() > 0)
        {
            await anchor.First.ScrollIntoViewIfNeededAsync();
            await anchor.First.WaitForAsync(new LocatorWaitForOptions { State = WaitForSelectorState.Visible, Timeout = 5000 });
            await anchor.First.ClickAsync();
            return;
        }

        var fallback = calendar.Locator($"a:has-text(\"{day}\")");
        if (await fallback.CountAsync() > 0)
        {
            await fallback.First.ScrollIntoViewIfNeededAsync();
            await fallback.First.WaitForAsync(new LocatorWaitForOptions { State = WaitForSelectorState.Visible, Timeout = 5000 });
            await fallback.First.ClickAsync();
            return;
        }

        var cell = calendar.Locator($"td:has-text(\"{day}\")");
        await cell.First.ScrollIntoViewIfNeededAsync();
        await cell.First.WaitForAsync(new LocatorWaitForOptions { State = WaitForSelectorState.Visible, Timeout = 5000 });
        await cell.First.ClickAsync();
    }

    private static double SecondsUntilMidnight()
    {
        var now = DateTime.Now;
        var midnight = now.Date.AddDays(1);
        return Math.Max(0, (midnight - now).TotalSeconds);
    }
}
