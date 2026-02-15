"""
Application Subsystem Loader.

This module acts as a "meta-loader" or registry for the specific application-related
extensions (Cogs). Its primary purpose is to group related functionality—such as
Clan, FWA, Staff, and Miscellaneous application logic—into a single loadable unit.

This pattern simplifies the main entry point by delegating the responsibility of
loading specific application sub-modules to this extension.

Dependencies:
    - interactions (Discord client library)
"""

import interactions as ipy

class ApplicationLoader(ipy.Extension):
    """
    Orchestrates the loading of sub-extensions related to the 'Applications' system.
    
    When this extension is initialized, it automatically attempts to load a predefined
    list of child extensions. This ensures that all components of the application
    system are active simultaneously.
    """

    def __init__(self, bot: ipy.Client):
        """
        Initialize the loader and trigger the sub-extension loading process.

        Args:
            bot (ipy.Client): The main bot instance.
        """
        self.bot = bot
        print("➤ Loading Application Modules...")
        
        # Registry of sub-extensions to be loaded.
        # These paths must correspond to valid python modules relative to the run directory.
        # TODO: Consider moving this list to an external config file for easier maintenance.
        self.app_extensions = [
            "extensions.apps.clan",
            "extensions.apps.fwa",
            "extensions.apps.staff",
            "extensions.apps.misc"
        ]
        
        # Iterate through the registry and attempt to load each module.
        # We use a try-except block here to ensure that a failure in one module
        # does not prevent the others from loading.
        for ext in self.app_extensions:
            try:
                self.bot.load_extension(ext)
                print(f"  ✓ Loaded {ext}")
            except Exception as e:
                # Log the specific error to console for debugging.
                # In a production environment, this should ideally use the logging module.
                print(f"  ✕ Failed to load {ext}: {e}")

def setup(bot: ipy.Client):
    """
    Entry point for the extension.
    
    Initializes the ApplicationLoader which triggers the loading of sub-modules.
    
    Args:
        bot (ipy.Client): The main bot instance.
    """
    ApplicationLoader(bot)