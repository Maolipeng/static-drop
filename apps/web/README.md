# StaticDrop Web

Next.js web console for StaticDrop.

## Development

```bash
# From repo root
pnpm install
pnpm --filter web dev
```

Set `DEPLOY_TOKEN` and `API_URL` in `.env` for local dev. The token is used only
by the server-side API proxy and is never exposed to browser JavaScript.
