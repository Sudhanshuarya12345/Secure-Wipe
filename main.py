"""
Secure-Wipe Main Entry Point
"""
import sys

def main():
    print("Starting Secure-Wipe Modular Edition...")
    # Import the modular UI or the legacy UI depending on migration state.
    # Currently pointing to the legacy UI (with the Destroy tab removed)
    # for full backwards compatibility while the modular UI is finalized.
    try:
        import loginUI
        loginUI.main()
    except Exception as e:
        print(f"Failed to launch login UI: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
