import re
import html

def sanitize_text(value: str) -> str:
    if not isinstance(value, str):
        return value
    
    # Strip HTML tags
    value = re.sub(r'<[^>]*>', '', value)
    
    # Strip JS pseudo-protocols
    value = re.sub(r'(?i)javascript:', '', value)
    value = re.sub(r'(?i)vbscript:', '', value)
    value = re.sub(r'(?i)data:', '', value)
    
    # HTML escape
    value = html.escape(value)
    
    return value
