mkdir -p ~/.claude
cat > ~/.claude/CLAUDE.md << 'EOF'
# Global AI Assistant Configuration

## About Me
I'm a ICT System engineer focused on plattforms, automation, monitoring, and reliable systems.
I prefer clear, maintainable code over clever one-liners.
I work primarily on Ubuntu Linux and Windows 11 systems.

## Coding Philosophy

while(curious) { 
question everything(); 
dig_deeper(); 
connect_dots(unexpected);

if (stuck) {
keep_thinking(); 
 } 
}

## Coding Preferences

### General Principles
- **Clarity over cleverness**: Write code that junior developers can understand
- **Explicit over implicit**: Be clear about intentions
- **Security first**: Always consider security implications
- **Test everything**: Include tests with all code
- **Document why, not what**: Comments should explain reasoning
- **Git commits**: Use conventional commits (feat:, fix:, docs:, etc.)

### Language Preferences

#### Python
- Use type hints always
- Prefer f-strings for formatting
- Use pathlib for file operations
- Follow PEP 8 strictly
- Use dataclasses for data structures
- Virtual environments for all projects

```python
# Preferred style example
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class Config:
    """Application configuration."""
    name: str
    version: str
    debug: bool = False

def process_files(directory: Path) -> List[str]:
    """Process all Python files in directory."""
    return [f.name for f in directory.glob("*.py")]