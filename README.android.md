# Hermes Agent for Android

Hermes ships as a native Android app: the agent core runs in-process on Python 3.13
(bundled with [Chaquopy](https://chaquo.com/chaquopy/)), and the app's UI is the Hermes
web dashboard — the same FastAPI/SPA dashboard as desktop — rendered in a WebView bound to
`http://127.0.0.1:9119`.

There is no terminal inside the app: everything (config, API keys, sessions, skills,
settings) is done from the dashboard.

## 📱 Requirements

| | |
|---|---|
| Android version | 7.0 (API 24) or later |
| CPU | arm64-v8a or x86_64 (32-bit ABIs are not shipped — see [Python packaging](#python-packaging)) |
| Storage | ~250 MB free |
| Network | Internet for model providers and first launch |

## 🚀 Install

1. Download `Hermes-Agent-<version>-debug.apk` from the repository's
   [releases](../../releases) or CI artifacts (or build it below).
2. Allow your browser or file manager to install unknown apps
   (**Settings → Apps → Special access → Install unknown apps**).
3. Open the downloaded file and tap **Install**, then **Open**.

## ▶️ First launch

1. The app starts the Python runtime and the Hermes server (a few seconds; the
   progress line on screen reflects each phase).
2. The dashboard loads automatically — configure your model provider and API key
   there on first use.
3. An optional notification is requested on Android 13+. It announces the service
   that keeps the agent alive while the app is in the background; declining it does
   not stop the app.

State lives in app-private storage: `/data/data/com.nousresearch.hermes/files/hermes-home`
(`HERMES_HOME`). Clearing app data resets Hermes completely.

The dashboard is served on the device's loopback interface only; nothing is exposed to
the local network.

## 🛠️ Building from source

Prerequisites:

- JDK 17+
- Android SDK: `platform-tools`, `platforms;android-34`, `build-tools;34.0.0`
- Python 3.13 on `PATH` (Chaquopy byte-compiles the bundled packages with it; override
  with `HERMES_BUILD_PYTHON` if it lives elsewhere)

```bash
# Everything above, end to end:
./scripts/build_android_apk.sh --version 1.0.0 --debug
# → Hermes-Agent-1.0.0-debug.apk

# Or drive Gradle directly:
cd android
./gradlew assembleDebug      # app/build/outputs/apk/debug/app-debug.apk
./gradlew assembleRelease
```

CI (`.github/workflows/android-build.yml`) runs the same build on pushes and PRs that
touch `android/` and uploads the APK as an artifact (7 days; 30 for a release build).
The `versionCode` comes from the git commit count, so it only ever grows.

### Release signing

`build_android_apk.sh --release` refuses to build without real credentials: a keystore
at `ANDROID_KEYSTORE_PATH` (default `android/app/keystore/hermes-release.keystore`) plus
`ANDROID_STORE_PASSWORD` and `ANDROID_KEY_PASSWORD`. CI supplies them from the
`ANDROID_SIGNING_KEY` (base64 keystore), `ANDROID_STORE_PASSWORD`, `ANDROID_KEY_PASSWORD`
and `ANDROID_KEY_ALIAS` secrets.

Driving Gradle directly is laxer: `assembleRelease` signs with that keystore when it
exists and falls back to debug signing otherwise, so the APK stays installable while
you are iterating.

## 📦 Python packaging

The app pins Python **3.13**, the newest version for which Android wheels of every native
dependency exist (`pydantic-core` and `jiter` are only built for cp313 by
[ririv/android-wheels](https://github.com/ririv/android-wheels)).

`android/app/requirements-android.txt` is the **complete, pinned dependency closure** for
`hermes-agent`, installed with `pip --no-deps` from:

- PyPI (pure-Python packages),
- Chaquopy's wheel repository (native packages: cryptography, Pillow, psutil, …),
- `https://ririv.github.io/android-wheels/` (pydantic-core, jiter).

`--no-deps` is required because `hermes-agent`'s own metadata pins versions whose
Android wheels do not exist; the file's header explains every pin that was adjusted and
how it was verified:

```bash
pip install --no-deps --only-binary :all: \
  --platform android_24_arm64_v8a --platform android_24_x86_64 \
  --extra-index-url https://chaquo.com/pypi-13.1 \
  --extra-index-url https://ririv.github.io/android-wheels/ \
  -r android/app/requirements-android.txt
```

If you add a dependency, add it (and its transitive requirements) to that file and re-run
the command above — the build itself will fail loudly if a package has no Android wheel.

## 🔧 Troubleshooting

**"App not installed"** — uninstall the previous build first (debug and release APKs use
different signatures), or check free storage.

**Stuck on "Starting Python runtime…"** — the first launch does the most work. Force-stop
and reopen; if it persists, clear app data (Settings → Apps → Hermes Agent → Storage →
Clear data) and retry.

**Dashboard loads but the agent cannot answer** — configure a model provider in the
dashboard; Hermes needs outbound internet access (`INTERNET` permission, granted at
install).

**No 32-bit devices** — only `arm64-v8a` and `x86_64` are packaged. No public repository
publishes Android wheels for hermes-agent's native dependencies on `armeabi-v7a`/`x86`.

## 🔒 Security

- Install APKs only from this repository's releases.
- The dashboard binds `127.0.0.1` only; there is no remote exposure by design.
- API keys and conversation data stay on the device, in app-private storage.

## 📄 License

MIT — see [LICENSE](LICENSE).

---

**Hermes Agent** — [Nous Research](https://nousresearch.com)
