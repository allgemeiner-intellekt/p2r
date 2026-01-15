# p2r

A command-line tool that converts PDF papers to Markdown using MinerU cloud API.

## Features

- Convert PDF files to Markdown format
- Automatic OCR for scanned PDFs
- Extract images and tables
- Support for academic papers with complex layouts
- Progress tracking during conversion

## Installation

### For Development

1. Clone the repository:
```bash
git clone <repository-url>
cd p2r
```

2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux
# venv\Scripts\activate    # On Windows
```

3. Install in editable mode:
```bash
pip install -e .
```

### For Users

Install using pipx (recommended):
```bash
pipx install /path/to/p2r
```

Or using pip with a virtual environment:
```bash
pip install /path/to/p2r
```

## Configuration

Before using p2r, you need to configure your MinerU API token.

### Get API Token

1. Visit [MinerU website](https://mineru.net) and sign up for an account
2. Generate an API token from your account dashboard

### Set API Token

You can set the token in two ways:

**Option 1: Using the CLI command**
```bash
p2r config-token YOUR_API_TOKEN_HERE
```

**Option 2: Environment variable**
```bash
export P2R_MINERU_TOKEN=YOUR_API_TOKEN_HERE
```

### View Configuration

```bash
p2r show-config
```

## Usage

### Basic Conversion

Convert a PDF file to Markdown:
```bash
p2r convert paper.pdf
```

The output will be saved to a temporary directory by default.

### Specify Output Directory

```bash
p2r convert paper.pdf -o ./output
```

### Choose Model Version

MinerU offers two models:
- `pipeline` (default): Fast and efficient
- `vlm`: Vision-Language Model for better accuracy

```bash
p2r convert paper.pdf --model vlm
```

### Complete Example

```bash
# Configure token (first time only)
p2r config-token your-token-here

# Convert a paper
p2r convert research-paper.pdf -o ./converted

# Check the output
ls ./converted
```

## Project Status

This is **Phase 1** implementation. Currently supported:
- ✅ PDF to Markdown conversion
- ✅ Progress tracking
- ✅ Configuration management
- ✅ Basic CLI interface

Not yet implemented (planned for future phases):
- ⏳ File renaming based on paper title
- ⏳ Automatic moving to Obsidian vault
- ⏳ Image upload to image hosting
- ⏳ Metadata extraction
- ⏳ Frontmatter generation

## Requirements

- Python 3.8+
- MinerU API token
- Internet connection

## Development

### Project Structure

```
p2r/
├── src/p2r/
│   ├── __init__.py
│   ├── cli.py          # Command-line interface
│   ├── config.py       # Configuration management
│   └── mineru.py       # MinerU API client
├── tests/              # Test suite
├── doc/                # Documentation
├── pyproject.toml      # Project configuration
└── README.md
```

### Running Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black src/
ruff check src/
```

## License

MIT License - see LICENSE file for details

## Documentation

- [Product Requirements Document (PRD)](doc/PRD.md)
- [Phase 1 Plan](doc/phase1_plan.md)
- [MinerU API Reference](doc/mineru_api_reference.md)
