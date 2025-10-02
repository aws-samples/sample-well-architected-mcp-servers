"""
Main entry point for the IAM validation module.
Allows running the module with: python -m iam_validation
"""

from .cli import main

if __name__ == '__main__':
    exit(main())