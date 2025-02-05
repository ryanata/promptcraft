from setuptools import setup, find_packages

setup(
    name="promptcraft",
    version="0.1.0",
    package_dir={"promptcraft": "src"},  # Changed to map 'promptcraft' directly to 'src'
    packages=["promptcraft"],  # Simplified package declaration
    install_requires=[
        "prompt_toolkit",
        "pyperclip",
        "gitignore_parser"
    ],
    entry_points={
        'console_scripts': [
            'promptcraft=promptcraft.cli:main',  # Updated to use the new package name
        ],
    },
    author="Ryan Ata",
    description="An interactive prompt crafting tool with auto-completion",
    python_requires=">=3.6",
)