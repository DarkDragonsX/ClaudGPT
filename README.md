# ClaudGPT — Modular Telegram AI Bot

**Open-source project**  
**Original owner:** Rad Lamine  
**Original repository:** https://github.com/RadLamine/ClaudGPT

## Structure

The application is divided into ordered Python files in `bot_modules/`. `main.py` loads them in the listed order into one shared application namespace. This preserves the original registration order, handlers, and shared runtime state while allowing each feature area to be edited in its own file.

Run the bot with:

```bash
python main.py
```

Do not run the files inside `bot_modules/` separately. Edit the module files and keep the filenames/order in `main.py` unchanged unless you intentionally update the loader.

## Mandatory channel subscription

The two original channels are fixed in `bot_modules/01_configuration.py`:

- `@dexwep1`
- `@dexwep2`

They are not read from environment variables. A source-integrity check stops the application when either fixed channel identifier or its official link is changed or removed in the code. On startup, the bot also asks Telegram to resolve every required channel; startup stops if a required channel has been deleted or is unavailable. The membership check fails closed if Telegram cannot verify membership.

Two extra public channels can be appended through `.env`:

```env
CHANNEL_UPDATES=@extra_channel_one
CHANNEL_DEXWEP=@extra_channel_two
```

These two variables are treated only as optional extra channels. They cannot replace the two channels fixed in the source. Empty values are ignored, and duplicate values are not added twice. The subscription keyboard automatically displays two, three, or four channel buttons plus the verification button. Set the bot as an administrator in every required channel so Telegram can verify membership.

Supported extra-channel values are public channel usernames (`@channelname`, `channelname`) or public `https://t.me/channelname` links.

## Environment

Copy `.env.example` to `.env` and provide the credentials used by your deployment. Keep secrets out of source control.

## Dependencies

Install with:

```bash
pip install -r requirements.txt
```

## Integrity note

The channel guard detects accidental edits or deletion of the fixed channel settings. No Python source file can prevent a person with write access to the source code from deliberately removing the guard itself. For stronger deployment protection, restrict repository write access and deploy reviewed, immutable releases.
