#!/usr/bin/env python3
"""Verificar versão do Streamlit e suporte a fragment"""

import streamlit as st

print(f"Streamlit version: {st.__version__}")
print(f"Has fragment: {'fragment' in dir(st)}")
print(f"Has experimental_fragment: {'experimental_fragment' in dir(st)}")
