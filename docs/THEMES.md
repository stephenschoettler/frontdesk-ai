# Custom Themes Documentation

This document explains how to create custom themes for the Front Desk application. The theme system allows you to customize the visual appearance of the interface by defining color schemes in JSON format.

## Overview

Themes are stored as JSON files in the `static/themes/` directory. The application automatically discovers and loads all `*.json` files from this directory, making new themes immediately available in the theme switcher without requiring code changes.

## File Structure

```
static/themes/
├── your-theme-name.json
├── another-theme.json
└── ...
```

### File Naming Convention

- Use lowercase with hyphens: `my-custom-theme.json`
- Avoid spaces and special characters
- The filename becomes the theme identifier in the UI

## JSON Format

Each theme file contains one or more theme variants. Here's the complete structure:

```json
{
  "variant-name": {
    "description": "Optional description of this variant",
    "background": "#HEX_COLOR",
    "foreground": "#HEX_COLOR",
    "cursor": "#HEX_COLOR",
    "selection": "#HEX_COLOR",
    "ansi_colors": {
      "black": "#HEX_COLOR",
      "red": "#HEX_COLOR",
      "green": "#HEX_COLOR",
      "yellow": "#HEX_COLOR",
      "blue": "#HEX_COLOR",
      "magenta": "#HEX_COLOR",
      "cyan": "#HEX_COLOR",
      "white": "#HEX_COLOR",
      "bright_black": "#HEX_COLOR",
      "bright_red": "#HEX_COLOR",
      "bright_green": "#HEX_COLOR",
      "bright_yellow": "#HEX_COLOR",
      "bright_blue": "#HEX_COLOR",
      "bright_magenta": "#HEX_COLOR",
      "bright_cyan": "#HEX_COLOR",
      "bright_white": "#HEX_COLOR"
    }
  }
}
```

### Field Descriptions

#### Core Colors
- **`background`**: Main background color of the interface
- **`foreground`**: Primary text color
- **`cursor`**: Cursor/text selection color
- **`selection`**: Text selection background color

#### ANSI Colors
The `ansi_colors` object defines 16 colors that map to terminal/console color schemes:

**Normal Colors:**
- `black`, `red`, `green`, `yellow`, `blue`, `magenta`, `cyan`, `white`

**Bright Colors:**
- `bright_black`, `bright_red`, `bright_green`, `bright_yellow`, `bright_blue`, `bright_magenta`, `bright_cyan`, `bright_white`

## Color Mapping to CSS Variables

The theme colors are automatically mapped to CSS custom properties used throughout the application:

| Theme Field | CSS Variable | Usage |
|-------------|--------------|-------|
| `background` | `--tokyo-bg` | Main background |
| `foreground` | `--tokyo-fg` | Primary text |
| `ansi_colors.blue` | `--tokyo-blue` | Primary accent, links, buttons |
| `ansi_colors.magenta` | `--tokyo-purple` | Secondary accent, headers |
| `ansi_colors.green` | `--tokyo-green` | Success states, positive actions |
| `ansi_colors.yellow` | `--tokyo-orange` | Warning states, secondary buttons |
| `ansi_colors.red` | `--tokyo-red` | Error states, danger actions |
| `ansi_colors.bright_black` | `--tokyo-comment` | Muted text, comments |

### Derived Colors

Two additional CSS variables are automatically calculated from your `background` color:

- **`--tokyo-bg-dark`**: Darker version of background (used for cards, modals, navbar)
- **`--tokyo-bg-mid`**: Lighter version of background (used for card backgrounds, borders)

These are calculated using color manipulation functions that darken/lighten the background color appropriately.

## Examples

### Dark Theme Example

```json
{
  "my-dark-theme": {
    "description": "A dark theme with blue accents",
    "background": "#1a1b26",
    "foreground": "#c0caf5",
    "cursor": "#7aa2f7",
    "selection": "#283457",
    "ansi_colors": {
      "black": "#15161e",
      "red": "#f77693",
      "green": "#9ece6a",
      "yellow": "#e0af68",
      "blue": "#7aa2f7",
      "magenta": "#bb9af7",
      "cyan": "#7dcfff",
      "white": "#a9b1d6",
      "bright_black": "#414868",
      "bright_red": "#f77693",
      "bright_green": "#9ece6a",
      "bright_yellow": "#e0af68",
      "bright_blue": "#7aa2f7",
      "bright_magenta": "#bb9af7",
      "bright_cyan": "#7dcfff",
      "bright_white": "#c0caf5"
    }
  }
}
```

### Light Theme Example

```json
{
  "my-light-theme": {
    "description": "A light theme with dark text",
    "background": "#ffffff",
    "foreground": "#2d3748",
    "cursor": "#3182ce",
    "selection": "#bee3f8",
    "ansi_colors": {
      "black": "#2d3748",
      "red": "#e53e3e",
      "green": "#38a169",
      "yellow": "#d69e2e",
      "blue": "#3182ce",
      "magenta": "#805ad5",
      "cyan": "#319795",
      "white": "#718096",
      "bright_black": "#4a5568",
      "bright_red": "#e53e3e",
      "bright_green": "#38a169",
      "bright_yellow": "#d69e2e",
      "bright_blue": "#3182ce",
      "bright_magenta": "#805ad5",
      "bright_cyan": "#319795",
      "bright_white": "#2d3748"
    }
  }
}
```

### Multiple Variants in One File

You can define multiple variants in a single theme file:

```json
{
  "my-theme-dark": {
    "description": "Dark variant",
    "background": "#1a1b26",
    "foreground": "#c0caf5",
    "cursor": "#7aa2f7",
    "selection": "#283457",
    "ansi_colors": {
      "black": "#15161e",
      "red": "#f77693",
      "green": "#9ece6a",
      "yellow": "#e0af68",
      "blue": "#7aa2f7",
      "magenta": "#bb9af7",
      "cyan": "#7dcfff",
      "white": "#a9b1d6",
      "bright_black": "#414868",
      "bright_red": "#f77693",
      "bright_green": "#9ece6a",
      "bright_yellow": "#e0af68",
      "bright_blue": "#7aa2f7",
      "bright_magenta": "#bb9af7",
      "bright_cyan": "#7dcfff",
      "bright_white": "#c0caf5"
    }
  },
  "my-theme-light": {
    "description": "Light variant",
    "background": "#ffffff",
    "foreground": "#2d3748",
    "cursor": "#3182ce",
    "selection": "#bee3f8",
    "ansi_colors": {
      "black": "#2d3748",
      "red": "#e53e3e",
      "green": "#38a169",
      "yellow": "#d69e2e",
      "blue": "#3182ce",
      "magenta": "#805ad5",
      "cyan": "#319795",
      "white": "#718096",
      "bright_black": "#4a5568",
      "bright_red": "#e53e3e",
      "bright_green": "#38a169",
      "bright_yellow": "#d69e2e",
      "bright_blue": "#3182ce",
      "bright_magenta": "#805ad5",
      "bright_cyan": "#319795",
      "bright_white": "#2d3748"
    }
  }
}
```

## Tips for Creating Themes

### Color Harmony
- Choose colors that work well together and provide good contrast
- Ensure text remains readable on background elements
- Test your theme in both light and dark environments

### Accessibility
- Maintain sufficient contrast ratios between text and background
- Avoid using colors that could cause issues for color-blind users
- Test with different UI elements (buttons, forms, tables, etc.)

### Consistency
- Use the ANSI color palette as a foundation for your color scheme
- Ensure bright colors are actually brighter than their normal counterparts
- Keep the overall aesthetic cohesive

### Testing
- After creating your theme file, restart the application or refresh the page
- Test all UI components: buttons, forms, tables, modals, navigation
- Verify that scrollbars and selection states look good
- Check both light and dark variants if you create multiple

## Tools for Theme Creation

### Color Pickers
- [Coolors](https://coolors.co/) - Generate color palettes
- [Color Hunt](https://colorhunt.co/) - Curated color palettes
- [Material Color Tool](https://material.io/design/color/) - Google's color system

### Terminal Theme Inspiration
- [Terminal Sexy](https://terminal.sexy/) - Terminal color scheme browser
- [iTerm2 Color Schemes](https://iterm2colorschemes.com/) - Large collection of terminal themes
- [Base16](https://github.com/chriskempson/base16) - Popular color scheme framework

### Existing Theme References
Look at the existing themes in `static/themes/` for inspiration:
- `tokyo-night.json` - Popular dark theme with blue/purple accents
- `iceberg.json` - Clean theme with cyan/blue accents

## Troubleshooting

### Theme Not Appearing
- Ensure the JSON file is valid (use a JSON validator)
- Check that the file is in `static/themes/` directory
- Verify the filename ends with `.json`
- Restart the application or refresh the browser

### Colors Not Applying
- Check that all required fields are present in your theme
- Ensure hex colors are in the format `#RRGGBB`
- Verify that the theme variant name matches the key in your JSON

### Poor Contrast
- Use tools like [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/) to verify contrast ratios
- Aim for at least 4.5:1 contrast for normal text, 3:1 for large text

## Advanced Customization

### Custom Color Calculations
The application automatically calculates `--tokyo-bg-dark` and `--tokyo-bg-mid` from your background color. If you need more control, you could extend the theme system to include these values directly.

### Additional CSS Variables
If you need more customization, you can extend the `applyTheme()` function in `static/index.html` to map additional colors to new CSS variables.

## Contributing Themes

If you create a theme you'd like to share:
1. Test it thoroughly across all UI components
2. Ensure it follows the JSON format exactly
3. Consider adding a description field to help users understand the theme
4. Submit it as a pull request or share it in the community

Remember: themes are automatically discovered, so any valid theme file you add to the `static/themes/` directory will immediately be available in the application's theme switcher!</content>
<parameter name="filePath">docs/THEMES.md