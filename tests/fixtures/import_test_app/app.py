"""Test app for import statement coverage."""
from flask import Flask
import os
import sys as system

app = Flask(__name__)

@app.route('/')
def index():
    # Use imported modules
    path = os.path.join('/', 'test')
    version = system.version
    return 'OK'
