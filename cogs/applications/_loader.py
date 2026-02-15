import interactions as ipy

class ApplicationLoader(ipy.Extension):
    def __init__(self, bot):
        self.bot = bot
        print("➤ Loading Application Modules...")
        
        # List of your specific application files
        self.app_extensions = [
            "extensions.apps.clan",
            "extensions.apps.fwa",
            "extensions.apps.staff",
            "extensions.apps.misc"
        ]
        
        for ext in self.app_extensions:
            try:
                self.bot.load_extension(ext)
                print(f"  ✓ Loaded {ext}")
            except Exception as e:
                print(f"  ✕ Failed to load {ext}: {e}")

def setup(bot):
    ApplicationLoader(bot)