# Web Patcher

Vue/Vite front end for applying the verified v36 BPS patch in the browser.

## Development

```powershell
npm install
New-Item -ItemType Directory -Force -Path public
Copy-Item ..\dist\narutorpg3_chs_v36.bps public\narutorpg3_chs_v36.bps -Force
npm run dev
```

## Build

```powershell
New-Item -ItemType Directory -Force -Path public
Copy-Item ..\dist\narutorpg3_chs_v36.bps public\narutorpg3_chs_v36.bps -Force
npm run build
```

The page loads `public/narutorpg3_chs_v36.bps`, asks the user to select the original `.nds` ROM, validates the original ROM SHA256, applies the BPS patch locally, validates the patched ROM SHA256, and downloads `narutorpg3_chs_v36.nds`.

`public/` is intentionally ignored and should not store a committed BPS copy. The release workflow creates it temporarily before building.

No ROM data is uploaded.

Serve the page through `npm run dev`, `npm run preview`, or an HTTPS static host. Opening `index.html` directly through `file://` is not recommended because browser `fetch()` and `crypto.subtle` behavior is restricted there.

## GitHub Pages

`.github/workflows/deploy-web.yml` runs when a tag matching `v*` is pushed. It copies `dist/narutorpg3_chs_v36.bps` into `web/public/`, builds the Vite app, and deploys `web/dist` to GitHub Pages.

## Expected Hashes

- Original ROM SHA256: `A4D5B1A8AE88899A5CD62791FAF9CA102AA9FBEC768E3C5AFB0AB2EE8C1D1E2C`
- Patched ROM SHA256: `B29FEA1B5B7BBD5E2010BD5AF1262676B6B71CB1D6E126847BECCB9A71954BB9`
- BPS SHA256: `B2EC1D6803866CB6FCB716419B43DBA156807E6C9EEAFE8206DD35DE86E94347`
