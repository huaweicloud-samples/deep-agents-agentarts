from app.browser.tool import browser_use


def get_weather(location: str) -> str:
    """Get weather forecast for a given location."""
    return f"The weather in {location} is sunny, 22°C with light breeze."


AVAILABLE_TOOLS = [get_weather, browser_use]
