import typing as t
from pathlib import PurePath

from playwright.async_api import BrowserContext, async_playwright

from ..const import EXTENSIONS_PATH


class Browser:

    async def init(
        self,
        *,
        headless: bool = False,
        user_agent: t.Optional[str] = None,
        user_data_dir: t.Optional[PurePath] = None,
        executable_path: t.Optional[PurePath] = None,
        extension_paths: t.Optional[t.List[PurePath]] = None,
    ):
        self.playwright = await async_playwright().start()
        if not user_agent:
            user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
        chromium = self.playwright.chromium
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-notifications",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
        ]

        if user_data_dir and not user_data_dir.is_dir():
            raise FileNotFoundError(f"User data directory {user_data_dir} does not exist")

        if extension_paths:
            for path in extension_paths:
                if not path.exists() or not path.is_dir():
                    raise FileNotFoundError(f"Extension path {path} does not exist")
                args.append(f"--disable-extensions-except={str(path)}")
                args.append(f"--load-extension={str(path)}")

        if EXTENSIONS_PATH.exists() and EXTENSIONS_PATH.is_dir():
            for extension_dir in EXTENSIONS_PATH.iterdir():
                if extension_dir.is_dir():
                    args.append(f"--disable-extensions-except={str(extension_dir)}")
                    args.append(f"--load-extension={str(extension_dir)}")

        if executable_path and not executable_path.exists():
            raise FileNotFoundError(f"Executable path {executable_path} does not exist")
        
        if executable_path:
            args.append("--bot-profile=/Users/ryoma/Downloads/chrome137_win10_x64.enc")

        self.context: BrowserContext = await chromium.launch_persistent_context(
            args=args,
            headless=headless,
            user_agent=user_agent,
            user_data_dir=str(user_data_dir) if user_data_dir else None,
            accept_downloads=True,
            executable_path=str(executable_path) if executable_path else None,
        )


    async def close(self):
        await self.context.close()
        await self.playwright.stop()