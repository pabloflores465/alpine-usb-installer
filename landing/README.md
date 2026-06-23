# LEDIT landing page

Static glassmorphism landing page for LEDIT.

## Local preview

From this folder:

```sh
python3 -m http.server 3000
```

Then open `http://localhost:3000`.

## Deploy on Vercel

Use this folder as the Vercel project root:

```txt
landing
```

Recommended Vercel settings:

- Framework preset: Other
- Root directory: `landing`
- Build command: leave empty or use `npm run build`
- Output directory: leave empty / static root

The site is intentionally static and does not require a JavaScript framework.
