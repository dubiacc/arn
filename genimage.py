import asyncio
import argparse
from pathlib import Path
from typing import List
from playwright.async_api import async_playwright, Browser
from tqdm.asyncio import tqdm

# --- Configuration ---
INPUT_DIR = Path("chapters")
OUTPUT_DIR = Path("img")
NUM_WORKERS = 10
# Viewport dimensions for the output image (e.g., for a 720p video)
IMG_WIDTH = 1280
IMG_HEIGHT = 720

def create_html_template(text_content: str) -> str:
    """
    Creates a simple HTML document with embedded CSS to display the text.
    The CSS centers the text vertically and horizontally.
    """
    # Sanitize text to prevent HTML injection issues
    import html
    escaped_text = html.escape(text_content)

    return f"""
    <!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Audiobook Chunk</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700&display=swap');

            body, html {{
                margin: 0;
                padding: 0;
                width: 100%;
                height: 100%;
                font-family: 'Merriweather', serif;
                background-color: #fdf6e3; /* A soft, parchment-like color */
            }}
            .container {{
                display: flex;
                justify-content: center;
                align-items: center;
                width: 100%;
                height: 100%;
                padding: 40px;
                box-sizing: border-box;
            }}
            p {{
                font-size: 42px;
                line-height: 1.6;
                color: #586e75; /* A gentle, dark color */
                text-align: center;
                max-width: 80%;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <p>{escaped_text}</p>
        </div>
    </body>
    </html>
    """

async def create_image_from_chunk(browser: Browser, txt_file: Path):
    """
    Reads a text file, generates an HTML page, and takes a screenshot.
    """
    try:
        # 1. Read the text content from the chunk file
        with open(txt_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()

        if not content:
            print(f"Skipping empty file: {txt_file}")
            return

        # 2. Determine the output path corresponding to the input path
        relative_path = txt_file.relative_to(INPUT_DIR)
        output_path = OUTPUT_DIR / relative_path.with_suffix(".png")

        # 3. Ensure the output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 4. Generate the HTML content
        html_content = create_html_template(content)

        # 5. Use Playwright to render and screenshot the HTML
        page = await browser.new_page(
            viewport={'width': IMG_WIDTH, 'height': IMG_HEIGHT}
        )
        await page.set_content(html_content)
        await page.screenshot(path=output_path, type="png")
        await page.close()

    except Exception as e:
        print(f"Error processing {txt_file}: {e}")

async def worker(name: str, queue: asyncio.Queue, browser: Browser, pbar: tqdm):
    """
    A worker task that continuously fetches files from the queue and processes them.
    """
    while not queue.empty():
        txt_file = await queue.get()
        await create_image_from_chunk(browser, txt_file)
        queue.task_done()
        pbar.update(1)

async def main(args):
    """
    Main function to orchestrate the file discovery and concurrent processing.
    """
    print("Starting image generation process...")

    # 1. Find all .txt files in the input directory
    print(f"Looking for .txt files in '{INPUT_DIR}'...")
    text_files = sorted(list(INPUT_DIR.rglob("*.txt")))

    if not text_files:
        print("No .txt files found. Exiting.")
        return

    # 2. Handle "test mode"
    if args.test_mode:
        print(f"--- TEST MODE: Processing only the first 3 files. ---")
        text_files = text_files[:3]
    
    total_files = len(text_files)
    print(f"Found {total_files} files to process.")

    # 3. Set up the queue and progress bar
    queue = asyncio.Queue()
    for file in text_files:
        queue.put_nowait(file)

    pbar = tqdm(total=total_files, desc="Rendering Images", unit="file")

    # 4. Launch the browser and create worker tasks
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        tasks = [
            asyncio.create_task(worker(f"Worker-{i+1}", queue, browser, pbar))
            for i in range(args.workers)
        ]

        # 5. Wait for all files in the queue to be processed
        await queue.join()

        # 6. Cancel any remaining worker tasks (they are in a while loop)
        for task in tasks:
            task.cancel()
        
        # Gather results (including potential cancellations)
        await asyncio.gather(*tasks, return_exceptions=True)

        await browser.close()
    
    pbar.close()
    print("\nImage generation complete!")
    print(f"Output images are located in the '{OUTPUT_DIR}' directory.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate PNG images from text file chunks using a headless browser."
    )
    parser.add_argument(
        "--test",
        action="store_true",
        dest="test_mode",
        help="Enable test mode to only render the first 3 images found.",
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=NUM_WORKERS,
        help=f"Number of async workers to run concurrently (default: {NUM_WORKERS}).",
    )
    args = parser.parse_args()

    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Exiting.")
