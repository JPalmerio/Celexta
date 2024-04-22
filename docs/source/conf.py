# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
import sys
import os
# Load all the global Astropy configuration
from sphinx_astropy.conf import *

sys.path.insert(0, os.path.abspath("../../celexta/"))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Celexta'
copyright = '2024, Jesse T. Palmerio'
author = 'Jesse T. Palmerio'
release = '0.0.1'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

# Enable numref
numfig = True


extensions = [
    "sphinx.ext.duration",
    "sphinx_click.ext",
    "sphinx_rtd_theme",
    "sphinx.ext.autodoc",  # allows to generate .rst files from docstring
    "sphinx.ext.napoleon",  # allows sphinx to parse numpy and Google style docstrings
    "sphinx.ext.viewcode",  # add possibility to view source code
    "sphinx.ext.intersphinx",  # can generate automatic links to the documentation of objects in other projects.
    "sphinx.ext.extlinks",  # Markup to shorten external links
    "sphinx.ext.doctest",  # Test snippets in the documentation
    "sphinx.ext.autosummary",  # Generate autodoc summaries
    "numpydoc",
    "sphinx_automodapi.automodapi",  # Sphinx directives that help faciliate the automatic generation of API documentation pages. Need to install: pip install sphinx-automodapi
    "sphinx_automodapi.smart_resolver",
    "sphinx_copybutton",
    "sphinxemoji.sphinxemoji",
    "sphinx.ext.graphviz",
]

autosummary_generate = True

numpydoc_show_class_members = False
numpydoc_xref_param_type = True
numpydoc_xref_ignore = {"optional", "type_without_description", "BadException"}

# -- Options for autodoc ----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#configuration

# Automatically extract typehints when specified and place them in
# descriptions of the relevant function/method.
autodoc_typehints = "description"

# Don't show class signature with the class' name.
autodoc_class_signature = "separated"

# Templates
templates_path = ['_templates']
exclude_patterns = []

# Intersphinx mappings
intersphinx_mapping = {}
intersphinx_mapping["python"] = ("https://docs.python.org/3", None)
intersphinx_mapping["numpy"] = ("https://numpy.org/doc/stable/", None)
intersphinx_mapping["astropy"] = ("https://docs.astropy.org/en/latest/", None)
intersphinx_mapping["pandas"] = ("https://pandas.pydata.org/pandas-docs/stable/", None)
intersphinx_mapping["matplotlib"] = ("https://matplotlib.org/stable/", None)
intersphinx_mapping["scipy"] = ("https://docs.scipy.org/doc/scipy/", None)

# Inheritance diagram configuration
inheritance_graph_attrs = dict(rankdir="LR", size='""', fontsize=14, ratio="compress")

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
