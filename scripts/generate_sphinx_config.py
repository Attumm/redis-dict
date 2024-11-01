import tomli
import os
from pathlib import Path


def generate_configs():
    """Generate Sphinx configuration files from pyproject.toml."""
    print("Current working directory:", os.getcwd())

    root_dir = Path(os.getcwd())
    package_dir = root_dir / 'src' / 'redis_dict'
    docs_dir = root_dir / 'docs'

    print(f"Package directory: {package_dir}")
    print(f"Docs directory: {docs_dir}")

    with open('pyproject.toml', 'rb') as f:
        config = tomli.load(f)

    project_info = config['project']

    docs_path = Path('docs')
    docs_path.mkdir(exist_ok=True)
    source_path = docs_path / 'source'
    source_path.mkdir(exist_ok=True)

    docs_path = Path('docs')
    docs_path.mkdir(exist_ok=True)
    source_path = docs_path / 'source'
    source_path.mkdir(exist_ok=True)

    tutorials_source = docs_path / 'tutorials'
    tutorials_source.mkdir(exist_ok=True)

    tutorials_build = source_path / 'tutorials'
    tutorials_build.mkdir(exist_ok=True)

    conf_content = f"""
import os
import sys

# Add the package directory to Python path
package_path = os.path.abspath('{package_dir}')
src_path = os.path.dirname(package_path)
print(f"Adding to path: {{src_path}}")
print(f"Package path: {{package_path}}")
sys.path.insert(0, src_path)

project = "{project_info['name']}"
copyright = "2024, {project_info['authors'][0]['name']}"
author = "{project_info['authors'][0]['name']}"
version = "{project_info['version']}"

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx_autodoc_typehints',
    'myst_parser',
]

myst_update_mathjax = False
myst_enable_extensions = [
    "colon_fence",
    "deflist",
]
myst_heading_anchors = 3

html_extra_path = ['../tutorials']

def setup(app):
    print(f"Python path: {{sys.path}}")

html_theme = 'sphinx_rtd_theme'
"""

    index_content = """Redis Dict Documentation
========================

.. include:: ../../README.md
   :parser: myst_parser.sphinx_

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   modules
   redis_dict

Indices and tables
==================

* :ref:`genindex`
"""

    index_content1 = """
Redis Dict Documentation
=====================

.. include:: ../../README.md
   :parser: myst_parser.sphinx_

.. toctree::
    :maxdepth: 2
    :caption: Contents:

    modules

Indices and Tables
================

* :ref:`genindex`
"""

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

    with open(source_path / 'conf.py', 'w') as f:
        f.write(conf_content)

    with open(source_path / 'index.rst', 'w') as f:
        f.write(index_content)

    with open(docs_path / 'Makefile', 'w') as f:
        f.write(makefile_content)


if __name__ == '__main__':
    generate_configs()