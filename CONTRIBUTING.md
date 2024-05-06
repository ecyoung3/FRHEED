# Contributing

Contributions to FRHEED are highly welcome, but should still adhere to the established standards for
code quality, style, and convention. The following tools are used to help enforce these standards:

 - [`uv`][uv]: Virtual environment and dependency management
 - [`ruff`][ruff]: Code formatting and linting
 - [`mypy`][mypy]: Static type checking
 - [`pytest`][pytest]: Automated code testing

## Preamble

When I first created FRHEED, I had _zero_ programming experience outside of the little MATLAB I
learned in an undergraduate CS 101 course. This documentation is written with the intent of being
accessible to people with similarly minimal experience.

Because many research facilities that use FRHEED use Windows computers, it is also recommended to
use Windows (specfically Windows 10 or 11) for development. That said, the ultimate goal is to
also support Linux and macOS, so introducing platform-specific features should be avoided.

## Virtual Environment and Dependency Management

Development should always be done from within a dedicated virtual environment with the required
dependencies installed. There are many ways to do this, but [`uv`][uv] is the tool of choice for
both virtual environment creation and dependency management.

### Virtual Environment

#### Creating the Virtual Environment

To create a virtual environment at `.venv` in the current directory:

```console
uv venv
```

#### Using the Virtual Environment

To activate the virtual environment:

```console
.venv\Scripts\activate     # Windows
source .venv/bin/activate  # Linux and Mac
```

To make FRHEED discoverable while the virtual environment is active:

```console
echo %cd%\src > .venv/frheed.pth  # Command Prompt
echo $pwd\src > .venv/frheed.pth  # PowerShell
echo $pwd/src > .venv/frheed.pth  # Bash
```

Additionally, if you are using Visual Studio Code as your code editor, you should [select the Python
interpreter][vscode-venv] associated with your virtual environment as the default for your code
workspace.

NOTE: All subsequent commands in this document should be run from the repository root while the
virtual environment is active unless stated otherwise.

### Dependency Management

In addition to being used to create the virtual environment, [`uv`][uv] is also the tool of choice
for compiling and installing dependencies. The required packages and their version constraints are
specified in [`pyproject.toml`][pyproject], where `project.dependencies` contains the core
dependencies required for using FRHEED, and `project.optional-dependencies` contains groups of extra
dependencies, including those required for development.

### Installing Dependencies

To install development requirements:

```
uv pip install requirements-dev.txt
```

#### Compiling Dependencies

Compiling dependencies should not be necessary unless you have modified either of the aforementioned
dependency-related sections of `pyproject.toml`, something which should only be done by a FRHEED
author or maintainer.

To compile core dependencies to [`requirements.txt`](requirements.txt):

```console
uv pip compile pyproject.toml -o requirements.txt
```

To compile development dependencies to [`requirements-dev.txt`](requirements-dev.txt):

```console
uv pip compile pyproject.toml -o requirements-dev.txt --extra dev
```

To upgrade existing dependencies to the newest versions allowed by constraints, add either the
`--upgrade` flag to upgrade all packages, or `--upgrade-package <package>` to upgrade a single
package. For example, to update the `numpy` version in the core requirements:

```console
uv pip compile pyproject.toml -o requirements.txt --upgrade-package numpy
```

## Formatting and Linting

Code formatting and linting are both done using [`ruff`][ruff], the settings for which are
configured in [`pyproject.toml`][pyproject] under the `tool.ruff` sections.

### Formatting

To automatically format all files:

```console
ruff format
```

To check formatting without making any changes:

```console
ruff format --check
```

### Linting

To lint all Python files without making any changes:

```console
ruff check
```

To lint all Python files and fix any fixable errors:

```console
ruff check --fix
```

## Type Checking

Because Python is a dynamic language, many errors do not occur until you actually run your code.
The best way to catch bugs _without_ running your code is through the use of a static type checker,
which analyzes your variables and functions for type compatibility. FRHEED uses [`mypy`][mypy] for
this purpose, and configures its default settings in [`pyproject.toml`][pyproject].

Because type checking is relatively slow compared to formatting and linting, it is recommended to
only check specific files or directories when making changes:

```console
mypy src/frheed/gui.py   # type check a single file
mypy src/frheed/widgets  # type check all files in a directory
```

## Testing

While static type checking is a powerful tool, it cannot test application logic or other issues that
can only be detected when actually running the code. This form of code testing is done using the
[`pytest`][pytest] framework (or will be, once I actually write tests and set it up).


[ruff]: https://docs.astral.sh/ruff/
[mypy]: https://mypy.readthedocs.io/
[pytest]: https://docs.pytest.org/
[uv]: https://github.com/astral-sh/uv
[vscode-venv]: https://code.visualstudio.com/docs/python/environments#_select-and-activate-an-environment
[pyproject]: pyproject.toml
