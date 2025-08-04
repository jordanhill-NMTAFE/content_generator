"""
Utility module for converting markdown files to Jupyter notebooks using jupytext.
"""

import logging
from pathlib import Path
from typing import Optional

import logging

log = logging.getLogger(__name__)


def convert_md_to_notebook(
    md_path: Path, output_dir: Optional[Path] = None
) -> Optional[Path]:
    """
    Convert a markdown file to a Jupyter notebook using jupytext.

    Args:
        md_path: Path to the markdown file
        output_dir: Optional output directory (defaults to same directory as md_path)

    Returns:
        Path to the created notebook file, or None if conversion failed
    """
    try:
        import jupytext
        import nbformat

        if not md_path.exists():
            log.error(f"Markdown file not found: {md_path}")
            return None

        # Determine output path
        if output_dir is None:
            output_dir = md_path.parent

        output_dir.mkdir(parents=True, exist_ok=True)
        notebook_path = output_dir / f"{md_path.stem}.ipynb"

        # Convert markdown to notebook
        notebook = jupytext.read(md_path)

        # Save as .ipynb
        jupytext.write(notebook, notebook_path)

        log.info(f"✅ Successfully converted {md_path} to {notebook_path}")
        return notebook_path

    except ImportError:
        log.warning("⚠️  jupytext not available. Install with: pip install jupytext")
        log.info(
            "   You can manually convert markdown to notebook using: jupytext --to notebook <file>.md"
        )
        return None
    except Exception as e:
        log.error(f"❌ Failed to convert {md_path} to notebook: {e}")
        return None


def convert_notebook_to_md(
    notebook_path: Path, output_dir: Optional[Path] = None
) -> Optional[Path]:
    """
    Convert a Jupyter notebook to a markdown file using jupytext.

    Args:
        notebook_path: Path to the notebook file
        output_dir: Optional output directory (defaults to same directory as notebook_path)

    Returns:
        Path to the created markdown file, or None if conversion failed
    """
    try:
        import jupytext

        if not notebook_path.exists():
            log.error(f"Notebook file not found: {notebook_path}")
            return None

        # Determine output path
        if output_dir is None:
            output_dir = notebook_path.parent

        output_dir.mkdir(parents=True, exist_ok=True)
        md_path = output_dir / f"{notebook_path.stem}.md"

        # Convert notebook to markdown
        jupytext.write(notebook_path, md_path, fmt="md")

        log.info(f"✅ Successfully converted {notebook_path} to {md_path}")
        return md_path

    except ImportError:
        log.warning("⚠️  jupytext not available. Install with: pip install jupytext")
        log.info(
            "   You can manually convert notebook to markdown using: jupytext --to md <file>.ipynb"
        )
        return None
    except Exception as e:
        log.error(f"❌ Failed to convert {notebook_path} to markdown: {e}")
        return None


def batch_convert_md_to_notebook(md_dir: Path, pattern: str = "demo.md") -> list[Path]:
    """
    Convert all markdown files matching a pattern to notebooks.

    Args:
        md_dir: Directory containing markdown files
        pattern: File pattern to match (default: "demo.md")

    Returns:
        List of paths to created notebook files
    """
    created_notebooks = []

    if not md_dir.exists():
        log.error(f"Directory not found: {md_dir}")
        return created_notebooks

    for md_file in md_dir.rglob(pattern):
        notebook_path = convert_md_to_notebook(md_file)
        if notebook_path:
            created_notebooks.append(notebook_path)

    log.info(f"✅ Converted {len(created_notebooks)} markdown files to notebooks")
    return created_notebooks


def batch_convert_notebook_to_md(
    notebook_dir: Path, pattern: str = "*.ipynb"
) -> list[Path]:
    """
    Convert all notebook files matching a pattern to markdown.

    Args:
        notebook_dir: Directory containing notebook files
        pattern: File pattern to match (default: "*.ipynb")

    Returns:
        List of paths to created markdown files
    """
    created_md_files = []

    if not notebook_dir.exists():
        log.error(f"Directory not found: {notebook_dir}")
        return created_md_files

    for notebook_file in notebook_dir.rglob(pattern):
        md_path = convert_notebook_to_md(notebook_file)
        if md_path:
            created_md_files.append(md_path)

    log.info(f"✅ Converted {len(created_md_files)} notebooks to markdown files")
    return created_md_files
