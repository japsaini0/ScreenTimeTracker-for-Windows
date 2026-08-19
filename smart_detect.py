"""
Smart Detection module for Screen Time Tracker.
Detects actual content being used (e.g., Netflix on Edge → "Netflix").
"""
import re
import os

# Browser process names
BROWSERS = {
    "msedge.exe", "chrome.exe", "firefox.exe", "brave.exe",
    "opera.exe", "vivaldi.exe", "arc.exe", "safari.exe",
    "iexplore.exe", "chromium.exe",
}

# Known website patterns → display names with categories
# Format: (regex_pattern_for_title, display_name, category)
_WEBSITE_RULES_RAW = [
    # Streaming
    (r"netflix", "Netflix", "Entertainment"),
    (r"disney\+|disneyplus", "Disney+", "Entertainment"),
    (r"prime video|primevideo", "Prime Video", "Entertainment"),
    (r"hotstar", "Hotstar", "Entertainment"),
    (r"hulu", "Hulu", "Entertainment"),
    (r"hbo max|hbomax", "HBO Max", "Entertainment"),
    (r"crunchyroll", "Crunchyroll", "Entertainment"),
    (r"jio ?cinema", "JioCinema", "Entertainment"),
    (r"sonyliv", "SonyLIV", "Entertainment"),
    (r"zee5", "ZEE5", "Entertainment"),
    (r"mxplayer|mx player", "MX Player", "Entertainment"),
    (r"apple ?tv", "Apple TV+", "Entertainment"),
    (r"twitch\.tv|twitch", "Twitch", "Entertainment"),

    # Video
    (r"youtube\.com|youtube", "YouTube", "Entertainment"),
    (r"vimeo", "Vimeo", "Entertainment"),
    (r"dailymotion", "Dailymotion", "Entertainment"),

    # Music
    (r"spotify", "Spotify", "Music"),
    (r"soundcloud", "SoundCloud", "Music"),
    (r"apple music", "Apple Music", "Music"),
    (r"jiosaavn|saavn", "JioSaavn", "Music"),
    (r"gaana", "Gaana", "Music"),
    (r"wynk", "Wynk Music", "Music"),

    # Social Media
    (r"facebook|fb\.com", "Facebook", "Social"),
    (r"instagram", "Instagram", "Social"),
    (r"twitter|x\.com", "Twitter/X", "Social"),
    (r"reddit", "Reddit", "Social"),
    (r"linkedin", "LinkedIn", "Social"),
    (r"snapchat", "Snapchat", "Social"),
    (r"pinterest", "Pinterest", "Social"),
    (r"tumblr", "Tumblr", "Social"),
    (r"threads", "Threads", "Social"),
    (r"quora", "Quora", "Social"),

    # Communication
    (r"whatsapp", "WhatsApp", "Communication"),
    (r"telegram", "Telegram", "Communication"),
    (r"discord", "Discord", "Communication"),
    (r"slack", "Slack", "Communication"),
    (r"microsoft teams|teams", "Microsoft Teams", "Communication"),
    (r"zoom", "Zoom", "Communication"),
    (r"google meet|meet\.google", "Google Meet", "Communication"),
    (r"skype", "Skype", "Communication"),

    # Email
    (r"gmail", "Gmail", "Email"),
    (r"outlook\.(com|live|office)", "Outlook", "Email"),
    (r"yahoo ?mail", "Yahoo Mail", "Email"),
    (r"proton ?mail", "ProtonMail", "Email"),

    # Productivity
    (r"google docs|docs\.google", "Google Docs", "Productivity"),
    (r"google sheets|sheets\.google", "Google Sheets", "Productivity"),
    (r"google slides|slides\.google", "Google Slides", "Productivity"),
    (r"google drive|drive\.google", "Google Drive", "Productivity"),
    (r"notion", "Notion", "Productivity"),
    (r"trello", "Trello", "Productivity"),
    (r"asana", "Asana", "Productivity"),
    (r"jira", "Jira", "Productivity"),
    (r"figma", "Figma", "Productivity"),
    (r"canva", "Canva", "Productivity"),
    (r"overleaf", "Overleaf", "Productivity"),

    # Development
    (r"github", "GitHub", "Development"),
    (r"gitlab", "GitLab", "Development"),
    (r"stackoverflow|stack overflow", "Stack Overflow", "Development"),
    (r"codepen", "CodePen", "Development"),
    (r"replit", "Replit", "Development"),
    (r"leetcode", "LeetCode", "Development"),
    (r"hackerrank", "HackerRank", "Development"),
    (r"codeforces", "Codeforces", "Development"),
    (r"geeksforgeeks|gfg", "GeeksforGeeks", "Development"),

    # Shopping
    (r"amazon\.(com|in|co)", "Amazon", "Shopping"),
    (r"flipkart", "Flipkart", "Shopping"),
    (r"myntra", "Myntra", "Shopping"),
    (r"ebay", "eBay", "Shopping"),
    (r"aliexpress", "AliExpress", "Shopping"),

    # Education
    (r"coursera", "Coursera", "Education"),
    (r"udemy", "Udemy", "Education"),
    (r"khan ?academy", "Khan Academy", "Education"),
    (r"edx\.org|edx", "edX", "Education"),
    (r"unacademy", "Unacademy", "Education"),
    (r"byju", "BYJU'S", "Education"),

    # Search / General
    (r"google\.(com|co)", "Google Search", "Browsing"),
    (r"bing\.com", "Bing Search", "Browsing"),
    (r"duckduckgo", "DuckDuckGo", "Browsing"),
    (r"wikipedia", "Wikipedia", "Browsing"),

    # AI
    (r"chatgpt|chat\.openai", "ChatGPT", "AI"),
    (r"claude\.ai|anthropic", "Claude", "AI"),
    (r"gemini\.google|bard", "Gemini", "AI"),
    (r"copilot\.microsoft|copilot", "Copilot", "AI"),
    (r"perplexity", "Perplexity", "AI"),

    # News
    (r"bbc\.com|bbc news", "BBC News", "News"),
    (r"cnn\.com", "CNN", "News"),
    (r"ndtv", "NDTV", "News"),
    (r"times ?of ?india|timesofindia", "Times of India", "News"),
    (r"hindustan ?times", "Hindustan Times", "News"),

    # Gaming
    (r"steam", "Steam", "Gaming"),
    (r"epic ?games", "Epic Games", "Gaming"),
    (r"roblox", "Roblox", "Gaming"),
]

# Pre-compile all regex patterns at module load time (eliminates repeated
# recompilation every 3-second poll cycle — saves ~27 compilations/second)
WEBSITE_RULES = [
    (re.compile(pattern, re.IGNORECASE), name, category)
    for pattern, name, category in _WEBSITE_RULES_RAW
]

# Pre-compile the browser suffix pattern once
_BROWSER_SUFFIX_RE = re.compile(
    r"\s*[-–—]\s*(?:google chrome|chrome|microsoft edge|edge|firefox|"
    r"mozilla firefox|brave|opera|vivaldi|arc).*$",
    re.IGNORECASE,
)

# Known desktop app process → display name mapping
APP_NAMES = {
    "code.exe": ("VS Code", "Development"),
    "devenv.exe": ("Visual Studio", "Development"),
    "idea64.exe": ("IntelliJ IDEA", "Development"),
    "pycharm64.exe": ("PyCharm", "Development"),
    "webstorm64.exe": ("WebStorm", "Development"),
    "sublime_text.exe": ("Sublime Text", "Development"),
    "notepad++.exe": ("Notepad++", "Development"),
    "notepad.exe": ("Notepad", "Utilities"),
    "windowsterminal.exe": ("Windows Terminal", "Development"),
    "cmd.exe": ("Command Prompt", "Development"),
    "powershell.exe": ("PowerShell", "Development"),
    "pwsh.exe": ("PowerShell", "Development"),
    "wt.exe": ("Windows Terminal", "Development"),
    "antigravity.exe": ("Antigravity IDE", "Development"),

    "explorer.exe": ("File Explorer", "System"),
    "taskmgr.exe": ("Task Manager", "System"),
    "mmc.exe": ("System Console", "System"),
    "systemsettings.exe": ("Settings", "System"),
    "control.exe": ("Control Panel", "System"),

    "winword.exe": ("Microsoft Word", "Productivity"),
    "excel.exe": ("Microsoft Excel", "Productivity"),
    "powerpnt.exe": ("Microsoft PowerPoint", "Productivity"),
    "onenote.exe": ("OneNote", "Productivity"),
    "outlook.exe": ("Outlook", "Email"),

    "spotify.exe": ("Spotify", "Music"),
    "discord.exe": ("Discord", "Communication"),
    "slack.exe": ("Slack", "Communication"),
    "teams.exe": ("Microsoft Teams", "Communication"),
    "ms-teams.exe": ("Microsoft Teams", "Communication"),
    "telegram.exe": ("Telegram", "Communication"),
    "whatsapp.exe": ("WhatsApp", "Communication"),
    "zoom.exe": ("Zoom", "Communication"),
    "skype.exe": ("Skype", "Communication"),

    "vlc.exe": ("VLC Media Player", "Entertainment"),
    "wmplayer.exe": ("Windows Media Player", "Entertainment"),
    "mpc-hc64.exe": ("Media Player Classic", "Entertainment"),
    "mpc-hc.exe": ("Media Player Classic", "Entertainment"),
    "mpv.exe": ("mpv", "Entertainment"),

    "photoshop.exe": ("Photoshop", "Creative"),
    "illustrator.exe": ("Illustrator", "Creative"),
    "premierepro.exe": ("Premiere Pro", "Creative"),
    "afterfx.exe": ("After Effects", "Creative"),
    "lightroom.exe": ("Lightroom", "Creative"),
    "gimp-2.10.exe": ("GIMP", "Creative"),
    "blender.exe": ("Blender", "Creative"),

    "steam.exe": ("Steam", "Gaming"),
    "epicgameslauncher.exe": ("Epic Games", "Gaming"),
    "riotclientservices.exe": ("Riot Games", "Gaming"),
    "javaw.exe": ("Minecraft", "Gaming"),

    "acrobat.exe": ("Adobe Acrobat", "Productivity"),
    "acrord32.exe": ("Adobe Reader", "Productivity"),
    "foxitreader.exe": ("Foxit Reader", "Productivity"),
    "sumatrapdf.exe": ("SumatraPDF", "Productivity"),

    "calc.exe": ("Calculator", "Utilities"),
    "snippingtool.exe": ("Snipping Tool", "Utilities"),
    "mspaint.exe": ("Paint", "Utilities"),
    "wordpad.exe": ("WordPad", "Utilities"),
}

# Category colors for UI
CATEGORY_COLORS = {
    "Entertainment": "#E74C3C",
    "Music": "#9B59B6",
    "Social": "#E91E63",
    "Communication": "#3498DB",
    "Email": "#1ABC9C",
    "Productivity": "#2ECC71",
    "Development": "#F39C12",
    "Browsing": "#95A5A6",
    "Shopping": "#FF9800",
    "Education": "#00BCD4",
    "AI": "#7C4DFF",
    "News": "#607D8B",
    "Gaming": "#FF5722",
    "Creative": "#E040FB",
    "System": "#78909C",
    "Utilities": "#90A4AE",
    "Other": "#546E7A",
}

# Browser display name lookup
_BROWSER_NAMES = {
    "msedge.exe": "Microsoft Edge",
    "chrome.exe": "Google Chrome",
    "firefox.exe": "Firefox",
    "brave.exe": "Brave Browser",
    "opera.exe": "Opera",
    "vivaldi.exe": "Vivaldi",
    "arc.exe": "Arc Browser",
}


def detect_app(process_name, window_title):
    """
    Detect the actual application/website being used.

    Args:
        process_name: The executable name (e.g., "msedge.exe")
        window_title: The window title text

    Returns:
        tuple: (display_name, category)
    """
    proc_lower = process_name.lower() if process_name else ""
    title_lower = window_title.lower() if window_title else ""

    # Check if it's a browser
    if proc_lower in BROWSERS:
        # Try to match website from title (uses pre-compiled patterns)
        for compiled_re, name, category in WEBSITE_RULES:
            if compiled_re.search(title_lower):
                return name, category

        # Extract website name from browser title
        cleaned_title = window_title or ""
        cleaned_title = _BROWSER_SUFFIX_RE.sub("", cleaned_title).strip()

        if cleaned_title and len(cleaned_title) > 2:
            if cleaned_title != window_title:
                return cleaned_title[:50], "Browsing"

        # Fallback to browser name
        return _BROWSER_NAMES.get(proc_lower, "Browser"), "Browsing"

    # Check known desktop apps
    if proc_lower in APP_NAMES:
        return APP_NAMES[proc_lower]

    # Fallback: Clean up process name
    name = process_name or "Unknown"
    name = name.replace(".exe", "").replace(".EXE", "")
    name = name.replace("_", " ").replace("-", " ").title()
    return name, "Other"


def get_category_color(category):
    """Get the color associated with a category."""
    return CATEGORY_COLORS.get(category, CATEGORY_COLORS["Other"])
