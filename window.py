"""
YancoHub — pywebview Window
Opens the Flask UI in a native window.
"""

import webview
import sys


def main():
    window = webview.create_window(
        'YancoHub',
        'http://127.0.0.1:8745',
        width=1400,
        height=900,
        min_size=(1024, 600),
        background_color='#060b14',
        text_select=False,
    )
    webview.start(debug='--debug' in sys.argv)


if __name__ == '__main__':
    main()
