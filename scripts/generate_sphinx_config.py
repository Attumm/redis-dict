# scripts/generate_sphinx_config.py

import tomli
import os
from pathlib import Path


def generate_configs():
    """Generate Sphinx configuration files from pyproject.toml."""
    print("Current working directory:", os.getcwd())

    # Get absolute paths
    root_dir = Path(os.getcwd())
    src_dir = root_dir / 'src'
    docs_dir = root_dir / 'docs'

    print(f"Source directory: {src_dir}")
    print(f"Docs directory: {docs_dir}")

    # Read project configuration
    with open('pyproject.toml', 'rb') as f:
        config = tomli.load(f)

    project_info = config['project']

    # Ensure docs directory exists
    docs_path = Path('docs')
    docs_path.mkdir(exist_ok=True)
    source_path = docs_path / 'source'
    source_path.mkdir(exist_ok=True)

    # Generate Sphinx configuration
    conf_content = f"""
import os
import sys

# Add absolute path to the source directory
src_path = os.path.abspath('{src_dir}')
print(f"Adding to path: {{src_path}}")
sys.path.insert(0, src_path)

project = "{project_info['name']}"
copyright = "2024, {project_info['authors'][0]['name']}"
author = "{project_info['authors'][0]['name']}"
version = "{project_info['version']}"

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx_autodoc_typehints'
]

# Show the path being used
def setup(app):
    print(f"Python path: {{sys.path}}")

html_theme = 'sphinx_rtd_theme'
"""

    # Generate main documentation file with proper RST formatting
    index_content = """
Redis Dict Documentation
=====================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   modules

Indices and Tables
================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
"""

    # Generate Makefile
    makefile_content = """
# Minimal makefile for Sphinx documentation
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = source
BUILDDIR      = build

help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile

%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
"""

    # Write files
    with open(source_path / 'conf.py', 'w') as f:
        f.write(conf_content)

    with open(source_path / 'index.rst', 'w') as f:
        f.write(index_content)

    with open(docs_path / 'Makefile', 'w') as f:
        f.write(makefile_content)


if __name__ == '__main__':
    generate_configs()