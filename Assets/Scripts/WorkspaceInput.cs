using UnityEngine;
using UnityEngine.InputSystem;

// Single boundary for runtime device input. Missing/unfocused devices are safe.
public struct WorkspaceInput
{
    public Vector2 Position, Delta;
    public float Scroll;
    public bool Pressed, Held;
    public static WorkspaceInput Read()
    {
        var mouse = Mouse.current;
        if (mouse == null || !Application.isFocused) return default;
        return new WorkspaceInput {
            Position = mouse.position.ReadValue(), Delta = mouse.delta.ReadValue(),
            Scroll = mouse.scroll.ReadValue().y / 120f,
            Pressed = mouse.leftButton.wasPressedThisFrame, Held = mouse.leftButton.isPressed
        };
    }
}
