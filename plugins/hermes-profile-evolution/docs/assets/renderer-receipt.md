# Renderer receipt

The source diagram is `profile-evolution-claude-code-front-door.svg` with a
fixed 1600 by 900 view box. The checked-in PNG is rendered with:

```bash
rsvg-convert --width 1600 --height 900 \
  profile-evolution-claude-code-front-door.svg \
  --output profile-evolution-claude-code-front-door.png
```

The SVG is the editable source; the PNG is the portable rendered copy.
