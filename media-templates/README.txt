Media Templates Directory

This directory stores user-configured default templates for disguise functionality.

Files in this directory:
- default.png - Custom PNG template (if set by user)
- default.jpg - Custom JPG template (if set by user)
- default.mp3 - Custom MP3 template (if set by user)
- default.mp4 - Custom MP4 template (if set by user)
- default.pdf - Custom PDF template (if set by user)

How it works:
1. PNG and PDF can be dynamically generated (random each time) - no template needed
2. JPG, MP3, MP4 require either a custom template or a carrier file specified at packaging time
3. Templates can be configured in Settings > Template Management
4. Each packaging session can optionally specify a different carrier file

Priority for carrier selection:
1. Custom carrier file specified by user (highest priority)
2. Default template from this directory
3. Dynamic generation (PNG/PDF only)