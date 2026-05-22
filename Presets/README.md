# Framekit Presets

This directory contains preset configurations for various Framekit modules. Presets allow you to save and reuse common configurations, making your workflow more efficient.

## Directory Structure

```
Presets/
├── CleanMKV/       # Track selection presets for CleanMKV module
├── Prez/           # Presentation presets for Prez module
├── Pipeline/       # Full pipeline presets combining multiple modules
└── README.md       # This file
```

## Module-Specific Presets

### CleanMKV Presets (`Presets/CleanMKV/`)

CleanMKV presets control which audio and subtitle tracks to keep when remuxing MKV files.

**File Format:** JSON (`.json`)

**Example Usage:**
```bash
# Create a preset using the wizard
framekit cleanmkv --wizard --save-preset "my_preset"

# Use a saved preset
framekit cleanmkv --external-preset "my_preset"

# List available presets
framekit cleanmkv --list-presets
```

**See:** `CleanMKV/example.yaml` for detailed examples and documentation.

### Prez Presets (`Presets/Prez/`)

Prez presets define how release presentations are generated, including template selection and MediaInfo options.

**File Format:** YAML (`.yaml`) or JSON (`.json`)

**Example Usage:**
```bash
# Use a preset
framekit prez --preset tracker

# Override preset values
framekit prez --preset tracker --html-template cinema
```

**See:** `Prez/example.yaml` for detailed examples and documentation.

### Pipeline Presets (`Presets/Pipeline/`)

Pipeline presets define complete workflows that combine multiple modules (Renamer, CleanMKV, NFO, Torrent, Prez).

**File Format:** YAML (`.yaml`) or JSON (`.json`)

**Example Usage:**
```bash
# Run a complete pipeline
framekit pipeline --preset complete_release

# Batch process multiple releases
framekit pipeline --preset complete_release --batch
```

**See:** `Pipeline/example.yaml` for detailed examples and documentation.

## Creating Custom Presets

### Method 1: Using the Wizard (CleanMKV)

The easiest way to create CleanMKV presets is using the interactive wizard:

```bash
framekit cleanmkv --wizard --save-preset "my_custom_preset"
```

This will guide you through selecting tracks and save the preset automatically.

### Method 2: Manual Creation

1. Copy an example from the `example.yaml` file in the appropriate subdirectory
2. Modify the configuration to match your needs
3. Save as a new file in the same directory
4. For CleanMKV: Convert YAML to JSON format (CleanMKV currently uses JSON)

### Method 3: Copying Existing Presets

If you have presets in the legacy location (`~/.config/framekit/presets/`), they will still work. However, we recommend copying them to the new location for better organization:

```bash
# Copy from legacy location to new location
cp ~/.config/framekit/presets/my_preset.json Presets/CleanMKV/
```

## Backward Compatibility

Framekit maintains backward compatibility with presets stored in the legacy location:
- **Legacy Location:** `~/.config/framekit/presets/` (or equivalent on your OS)
- **New Location:** `Presets/CleanMKV/` (in your project directory)

When loading presets, Framekit checks:
1. New project-level `Presets/CleanMKV/` directory first
2. Legacy config directory as fallback

When saving new presets, they are saved to the new `Presets/CleanMKV/` directory.

## Benefits of Project-Level Presets

1. **Portability:** Presets travel with your project
2. **Version Control:** Commit presets to Git for team sharing
3. **Organization:** Separate presets by module type
4. **Documentation:** Example files provide inline documentation
5. **Flexibility:** Override presets per-project without affecting global config

## Preset Priority

When multiple presets exist with the same name:
1. Project-level presets (`Presets/CleanMKV/`) take priority
2. Legacy presets (`~/.config/framekit/presets/`) are used as fallback
3. Built-in presets are used if no external preset is found

## Tips and Best Practices

### Naming Conventions

- Use descriptive names: `french_only`, `anime_jp_en`, `tracker_upload`
- Avoid special characters (they will be sanitized)
- Use lowercase with underscores for consistency

### Organization

- Keep related presets together in the same subdirectory
- Document complex presets with comments (in YAML files)
- Create a preset for each common workflow

### Version Control

If using Git, consider adding presets to your repository:

```bash
# Add all presets
git add Presets/

# Or add specific presets
git add Presets/CleanMKV/my_preset.json
```

Add to `.gitignore` if you want to keep presets private:
```
Presets/CleanMKV/*.json
!Presets/CleanMKV/example.yaml
```

### Sharing Presets

To share presets with others:
1. Export the preset file from `Presets/CleanMKV/`
2. Share the JSON file
3. Recipients place it in their `Presets/CleanMKV/` directory

## Troubleshooting

### Preset Not Found

If a preset isn't found:
1. Check the filename matches the preset name (sanitized)
2. Verify the file is in the correct directory
3. Check file extension (`.json` for CleanMKV)
4. Use `--list-presets` to see available presets

### Preset Validation Errors

If a preset fails to load:
1. Check JSON syntax (use a JSON validator)
2. Verify all required fields are present
3. Check language filters are valid
4. Refer to `example.yaml` for correct structure

### Legacy Presets Not Loading

If legacy presets aren't loading:
1. Verify they exist in `~/.config/framekit/presets/`
2. Check file permissions
3. Try copying to new location: `Presets/CleanMKV/`

## Further Reading

- **CleanMKV Documentation:** See `CleanMKV/example.yaml`
- **Prez Documentation:** See `Prez/example.yaml`
- **Pipeline Documentation:** See `Pipeline/example.yaml`
- **Main README:** See project root `README.md`

## Support

For issues or questions:
1. Check the example files in each subdirectory
2. Review the main project documentation
3. Open an issue on the project repository