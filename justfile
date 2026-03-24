set shell := ["zsh", "-cu"]

build:
    uv run python tools/write_reviews.py

validate: build
    uv run python tools/validate_reviews.py
