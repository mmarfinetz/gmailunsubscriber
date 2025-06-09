# Contributing to Gmail Unsubscriber

Thanks for your interest in contributing! Please follow these guidelines.

## Setup
1. Fork the repository and clone your fork.
2. Create a virtual environment and install dependencies:
   ```bash
   pip install -r gmail-unsubscriber-backend/requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in your credentials.
4. Run the backend and frontend locally:
   ```bash
   cd gmail-unsubscriber-backend && python app.py
   ```
   In another terminal run:
   ```bash
   cd gmail-unsubscriber && python -m http.server 8000
   ```

## Pull Requests
* Create feature branches from `main`.
* Provide a clear description of your changes and link any related issues.
* Ensure `python -m py_compile gmail-unsubscriber-backend/app.py` succeeds before submitting.

## Code Style
* Follow PEP8 for Python code.
* Use descriptive variable names and add comments where helpful.

## Community
Feel free to open issues for bugs or feature requests. We welcome contributions!
