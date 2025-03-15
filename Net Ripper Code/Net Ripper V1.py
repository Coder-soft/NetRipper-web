#!/usr/bin/env python3
import os
import sys
import time
import asyncio
import aiohttp
import aiofiles
import tempfile
import shutil
from urllib.parse import urlparse
from rich.console import Console
from rich.progress import Progress, BarColumn, DownloadColumn, TextColumn, TransferSpeedColumn, TimeRemainingColumn

console = Console()

async def download_range(session, url, start, end, index, temp_dir, progress, task_id, chunk_size=1048576):
    """
    Downloads a specific byte range from the URL using asynchronous I/O.
    Uses a large chunk size (1 MB) to maximize throughput.
    """
    headers = {'Range': f'bytes={start}-{end}'}
    temp_file = os.path.join(temp_dir, f"part_{index}")
    try:
        async with session.get(url, headers=headers) as response:
            response.raise_for_status()
            async with aiofiles.open(temp_file, "wb") as f:
                while True:
                    chunk = await response.content.read(chunk_size)
                    if not chunk:
                        break
                    await f.write(chunk)
                    progress.advance(task_id, advance=len(chunk))
    except Exception as e:
        console.print(f"[red]Error downloading part {index+1}: {e}[/red]")

async def main():
    console.print("[bold cyan]Welcome to Net Ripper Super Fast - Terminal Download Manager[/bold cyan]\n")
    # Create an unlimited connection pool to fully utilize resources
    connector = aiohttp.TCPConnector(limit=0)
    async with aiohttp.ClientSession(connector=connector) as session:
        while True:
            # Step 1: Get the direct download URL
            url = input("Step 1 - Enter the direct download URL: ").strip()
            if not url:
                console.print("[red]No URL provided. Exiting.[/red]")
                sys.exit(1)
            
            # Automatically extract the output file name (including extension)
            parsed_url = urlparse(url)
            output_file = os.path.basename(parsed_url.path)
            if not output_file:
                output_file = "downloaded_file"
            console.print(f"Output file will be: [bold]{output_file}[/bold]")
            
            # Step 2: Ask for the number of concurrent connections
            threads_input = input("Step 2 - Enter number of concurrent connections (default: 8): ").strip()
            try:
                thread_count = int(threads_input) if threads_input else 8
            except ValueError:
                console.print("[yellow]Invalid input for connections. Using default value 8.[/yellow]")
                thread_count = 8

            console.print("\n[cyan]Initializing download...[/cyan]\n")
            
            # Retrieve file metadata with a HEAD request
            try:
                async with session.head(url) as head_response:
                    head_response.raise_for_status()
                    file_size = int(head_response.headers.get("Content-Length", 0))
                    accept_ranges = head_response.headers.get("Accept-Ranges", "")
            except Exception as e:
                console.print(f"[red]Error accessing URL: {e}[/red]")
                continue

            if file_size == 0:
                console.print("[yellow]Could not determine file size. Falling back to a single connection download.[/yellow]")
                thread_count = 1
            elif accept_ranges.lower() != "bytes":
                console.print("[yellow]Server does not support multi-connection downloads. Falling back to a single connection download.[/yellow]")
                thread_count = 1

            console.print(f"[cyan]File Size: {file_size} bytes[/cyan]")
            console.print(f"[cyan]Using {thread_count} concurrent connection(s) for downloading.[/cyan]\n")
            
            # Calculate byte ranges for each connection
            ranges = []
            if thread_count == 1:
                ranges.append((0, file_size - 1))
            else:
                part_size = file_size // thread_count
                for i in range(thread_count):
                    start = i * part_size
                    end = file_size - 1 if i == thread_count - 1 else (i + 1) * part_size - 1
                    ranges.append((start, end))
            
            # Create a temporary directory to store file segments
            temp_dir = tempfile.mkdtemp(prefix="netripper_")
            
            # Set up the progress bar using rich
            progress = Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn()
            )
            
            start_time = time.time()
            
            # Create and run tasks for each file segment
            tasks = []
            with progress:
                for i, (start, end) in enumerate(ranges):
                    task_id = progress.add_task(f"Downloading part {i+1}", total=(end - start + 1))
                    tasks.append(download_range(session, url, start, end, i, temp_dir, progress, task_id))
                await asyncio.gather(*tasks)
            
            total_time = time.time() - start_time
            
            # Combine the downloaded segments into the final file
            try:
                with open(output_file, "wb") as outfile:
                    for i in range(len(ranges)):
                        part_path = os.path.join(temp_dir, f"part_{i}")
                        with open(part_path, "rb") as infile:
                            shutil.copyfileobj(infile, outfile)
                console.print(f"\n[green]Download complete! File saved as: {output_file}[/green]")
                console.print(f"[green]Total time taken: {total_time:.2f} seconds[/green]\n")
            except Exception as e:
                console.print(f"[red]Error combining parts: {e}[/red]")
            finally:
                shutil.rmtree(temp_dir)
            
            # Ask the user if they want to download another file
            another = input("Do you want to download another file? (Y/n): ").strip().lower()
            if another in ["n", "no"]:
                console.print("[bold cyan]Thank you for using Net Ripper Super Fast![/bold cyan]")
                break
            console.print("\n---------------------------------------------\n")

if __name__ == "__main__":
    asyncio.run(main())
