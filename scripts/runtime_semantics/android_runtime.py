#!/usr/bin/env python3
"""Stable orchestration entry point for the Android production runtime adapter."""
if __package__:
    from .android_runner import main
else:
    from android_runner import main

if __name__ == "__main__":
    main()
