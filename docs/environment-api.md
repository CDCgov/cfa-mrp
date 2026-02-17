
# Environment API reference

The `Environment` is the main interface between MRP and your model.
Create one with `Environment.from_stdin()` and use it to read inputs
and write outputs.

## Properties

| Property     | Python type              | Rust type                  | Description                         |
|--------------|--------------------------|----------------------------|-------------------------------------|
| `input`      | `dict`                   | `Map<String, Value>`       | Parameters from `[input]`           |
| `files`      | `dict[str, Path]`        | `HashMap<String, PathBuf>` | Staged files from `model.files`     |

### Methods

**`write(filename, data)`** — Write a file to the output directory.
Falls back to stdout if no output directory is configured.

**`write_csv(filename, rows, fieldnames)`** — Write a CSV file to
the output directory. In Python, `rows` is a list of dicts; in Rust,
`rows` is `&[Vec<String>]` and `fieldnames` is `&[&str]`.
