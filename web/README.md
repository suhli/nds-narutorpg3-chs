# Web Patcher

Vue/Vite front end for applying the verified v36 BPS patch in the browser.

## Development

```powershell
npm install
npm run dev
```

## Build

```powershell
npm run build
```

The page loads `public/narutorpg3_chs_v36.bps`, asks the user to select the original `.nds` ROM, validates the original ROM SHA256, applies the BPS patch locally, validates the patched ROM SHA256, and downloads `narutorpg3_chs_v36.nds`.

No ROM data is uploaded.

Serve the page through `npm run dev`, `npm run preview`, or an HTTPS static host. Opening `index.html` directly through `file://` is not recommended because browser `fetch()` and `crypto.subtle` behavior is restricted there.

## Expected Hashes

- Original ROM SHA256: `A4D5B1A8AE88899A5CD62791FAF9CA102AA9FBEC768E3C5AFB0AB2EE8C1D1E2C`
- Patched ROM SHA256: `B29FEA1B5B7BBD5E2010BD5AF1262676B6B71CB1D6E126847BECCB9A71954BB9`
- BPS SHA256: `B2EC1D6803866CB6FCB716419B43DBA156807E6C9EEAFE8206DD35DE86E94347`
