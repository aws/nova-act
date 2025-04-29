import fire  # type: ignore

from nova_act import NovaAct


def main(user_data_dir: str = None, headless: bool = False) -> None:
    """
    Automates interaction with the MTCaptcha demo page using NovaAct.

    Args:
        user_data_dir (str, optional): Directory to store user data (e.g., for Chrome profile). Defaults to None.
        headless (bool, optional): Whether to run the browser in headless mode. Defaults to False.
    """
    with NovaAct(
        starting_page="https://2captcha.com/demo/mtcaptcha",
        user_data_dir=user_data_dir,
        headless=headless,
    ) as nova:
        nova.act(
            "If a cookie consent banner appears, close it. "
            "View the case-sensitive captcha character text at the center of the page. "
            "Enter the captcha text in the input field with placeholder 'Enter text from image'. "
            "Click the 'Check' button."
        )


if __name__ == "__main__":
    fire.Fire(main)
