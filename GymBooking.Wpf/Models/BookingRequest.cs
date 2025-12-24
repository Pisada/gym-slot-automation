namespace GymBooking.Wpf.Models;

public sealed class BookingRequest
{
    public required string Username { get; init; }
    public required string Password { get; init; }
    public required DateOnly TargetDate { get; init; }
    public required SlotSelection PrimarySlot { get; init; }
    public bool WaitForMidnight { get; init; }
    public bool TryOtherSlots { get; init; }
    public int DayAttempts { get; init; } = 5;
    public int StartEarlySeconds { get; init; } = 30;
}

public enum SlotSelection
{
    Slot0,
    Slot1,
    Slot2,
    Slot3
}
