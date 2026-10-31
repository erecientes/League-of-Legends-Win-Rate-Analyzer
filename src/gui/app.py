"""
Main desktop application window for match filtering and analytics.

Usage:
    from app import App
    app = App()
    app.mainloop()
"""

import customtkinter as ctk


class App(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        self.title("LoL Match Analytics")
        self.geometry("1100x700")
        ctk.set_appearance_mode("dark")

        # Layout: Column 0 (Left sidebar), Column 1 (Right content area)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left panel: Match & champion filters
        self.left_frame = ctk.CTkFrame(self, width=280)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # Right panel: Analytics view (item cards, stats)
        self.right_frame = ctk.CTkScrollableFrame(self)
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

