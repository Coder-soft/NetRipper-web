import os
import sys
import requests
import tkinter as tk
from tkinter import filedialog
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.progress import (
    Progress,
    BarColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
    SpinnerColumn
)
from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from pathlib import Path
import tempfile
import signal
import asyncio
import time

console = Console()

class NetRipperGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
    
    def select_save_path(self, default_name):
        file_path = filedialog.asksaveasfilename(
            initialfile=default_name,
            title="Save file as",
            defaultextension=Path(default_name).suffix
        )
        return Path(file_path) if file_path else None

class NetRipper:
    def __init__(self):
        self.gui = NetRipperGUI()
        self.configure_settings()
        self.download_queue = []
        self.active_downloads = []
        self.layout = Layout()
        self.progress = None
        self.should_pause = False

    def print_banner(self):
        banner = Text(r"""
 _   _      _    ______ _                       
| \ | |    | |   | ___ (_)                      
|  \| | ___| |_  | |_/ /_ _ __  _ __   ___ _ __ 
| . ` |/ _ \ __| |    /| | '_ \| '_ \ / _ \ '__|
| |\  |  __/ |_  | |\ \| | |_) | |_) |  __/ |   
\_| \_/\___|\__| \_| \_|_| .__/| .__/ \___|_|   
                         | |   | |              
                         |_|   |_|                      
        """, style="bold cyan")
        console.print(Panel(banner, title="Net Ripper Beta v2.0", subtitle="Terminal Download Accelerator", style="blue"))

    def configure_settings(self):
        self.settings = {
            'max_threads': 16,
            'default_save_dir': str(Path.home() / "Downloads"),
            'auto_resume': True,
            'max_retries': 5,
            'theme': 'dark'
        }

    async def show_main_menu(self):
        choices = {
            "1": "Add Download",
            "2": "Settings",
            "3": "View Queue",
            "4": "Exit"
        }
        
        while True:
            console.clear()
            self.print_banner()
            console.print("\n[bold cyan]Main Menu:[/bold cyan]")
            for key, value in choices.items():
                console.print(f"  [bold yellow]{key}[/bold yellow]. {value}")
            
            choice = console.input("\n[bold]Enter your choice: [/bold]").strip()
            
            if choice == "1":
                await self.add_download()
            elif choice == "2":
                await self.show_settings()
            elif choice == "3":
                await self.show_queue()
            elif choice == "4":
                self.gui.root.destroy()
                sys.exit(0)
            else:
                console.print("[red]Invalid choice![/red]")
                await asyncio.sleep(1)

    async def add_download(self):
        console.clear()
        self.print_banner()
        
        url = ""
        while not url.startswith(("http://", "https://")):
            url = console.input("\n[bold]Enter download URL: [/bold]").strip()
            if not url:
                return
        
        try:
            file_name = Path(url).name
            default_path = Path(self.settings['default_save_dir']) / file_name
            save_path = self.gui.select_save_path(str(default_path))
            
            if not save_path:
                return

            console.print(f"\n[bold]File:[/bold] {file_name}")
            console.print(f"[bold]Save to:[/bold] {save_path}")
            
            threads = console.input(
                f"\n[bold]Enter number of threads (1-{self.settings['max_threads']}, default 8): [/bold]"
            ).strip() or "8"
            
            self.download_queue.append({
                "url": url,
                "save_path": save_path,
                "threads": min(int(threads), self.settings['max_threads'])
            })
            
            console.print("\n[green]Download added to queue![/green]")
            await asyncio.sleep(1)
            await self.start_downloads()
            
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")
            await asyncio.sleep(2)

    async def show_settings(self):
        console.clear()
        self.print_banner()
        console.print("\n[bold cyan]Current Settings:[/bold cyan]")
        for key, value in self.settings.items():
            console.print(f"  [bold]{key.capitalize()}:[/bold] {value}")
        
        console.print("\n[bold yellow]1.[/bold yellow] Change Maximum Threads")
        console.print("[bold yellow]2.[/bold yellow] Change Default Save Directory")
        console.print("[bold yellow]3.[/bold yellow] Back to Main Menu")
        
        choice = console.input("\n[bold]Select option: [/bold]").strip()
        
        if choice == "1":
            new_threads = console.input(f"\n[bold]New Maximum Threads (current: {self.settings['max_threads']}): [/bold]")
            if new_threads.isdigit():
                self.settings['max_threads'] = int(new_threads)
        elif choice == "2":
            new_dir = filedialog.askdirectory()
            if new_dir:
                self.settings['default_save_dir'] = new_dir
        await self.show_main_menu()

    async def show_queue(self):
        console.clear()
        self.print_banner()
        console.print("\n[bold cyan]Download Queue:[/bold cyan]")
        if not self.download_queue:
            console.print("[yellow]No downloads in queue[/yellow]")
        else:
            for idx, item in enumerate(self.download_queue, 1):
                console.print(f"{idx}. {item['url']} -> {item['save_path']}")
        console.input("\n[bold]Press Enter to return...[/bold]")
        await self.show_main_menu()

    async def start_downloads(self):
        while self.download_queue:
            download = self.download_queue.pop(0)
            duration = await self.process_download(download)
            
            if duration is not None:
                minutes, seconds = divmod(duration, 60)
                console.print(f"\n[bold green]✓ Download completed in {int(minutes)}m {seconds:.2f}s[/bold green]")
                choice = console.input("\n[bold]Download another file? (y/n): [/bold]").strip().lower()
                if choice == 'y':
                    await self.add_download()
                else:
                    break
            else:
                console.print("[red]Skipping to next download due to errors[/red]")
        
        await self.show_main_menu()

    async def process_download(self, download):
        try:
            downloader = DownloadManager(
                url=download['url'],
                output=download['save_path'],
                num_threads=download['threads'],
                max_retries=self.settings['max_retries'],
                auto_resume=self.settings['auto_resume']
            )
            
            self.active_downloads.append(downloader)
            await downloader.start()
            return downloader.duration
            
        except Exception as e:
            console.print(f"[red]Download failed: {str(e)}[/red]")
            return None
        finally:
            if downloader in self.active_downloads:
                self.active_downloads.remove(downloader)

class DownloadManager:
    def __init__(self, url, output, num_threads=8, max_retries=5, auto_resume=True):
        self.url = url
        self.output_path = Path(output)
        self.num_threads = num_threads
        self.max_retries = max_retries
        self.auto_resume = auto_resume
        self.file_size = 0
        self.temp_dir = None
        self.chunks = []
        self.progress = None
        self.task_id = None
        self.duration = 0
        self.headers = {
            'User-Agent': 'NetRipper/2.0',
            'Accept-Encoding': 'gzip, deflate, br'
        }

    def get_file_size(self):
        response = requests.head(self.url, headers=self.headers, allow_redirects=True)
        response.raise_for_status()
        self.file_size = int(response.headers.get('content-length', 0))
        return self.file_size

    def check_range_support(self):
        response = requests.head(self.url, headers=self.headers)
        return 'accept-ranges' in response.headers and response.headers['accept-ranges'].lower() == 'bytes'

    def prepare_chunks(self):
        chunk_size = self.file_size // self.num_threads
        self.chunks = []
        for i in range(self.num_threads):
            start = i * chunk_size
            end = start + chunk_size - 1 if i < self.num_threads - 1 else self.file_size - 1
            self.chunks.append({'start': start, 'end': end, 'downloaded': 0})

    def download_chunk(self, chunk_index):
        chunk = self.chunks[chunk_index]
        temp_file = self.temp_dir / f"chunk_{chunk_index}.tmp"
        
        headers = self.headers.copy()
        headers['Range'] = f"bytes={chunk['start'] + chunk['downloaded']}-{chunk['end']}"
        
        for attempt in range(self.max_retries):
            try:
                with requests.get(self.url, headers=headers, stream=True, allow_redirects=True) as r:
                    r.raise_for_status()
                    with open(temp_file, 'ab') as f:
                        for data in r.iter_content(chunk_size=8192):
                            f.write(data)
                            length = len(data)
                            self.chunks[chunk_index]['downloaded'] += length
                            self.progress.update(self.task_id, advance=length)
                return
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                console.print(f"[yellow]Chunk {chunk_index} attempt {attempt+1} failed: {str(e)}[/yellow]")

    def combine_files(self):
        with open(self.output_path, 'wb') as outfile:
            for i in range(self.num_threads):
                chunk_file = self.temp_dir / f"chunk_{i}.tmp"
                with open(chunk_file, 'rb') as infile:
                    while True:
                        data = infile.read(8192)
                        if not data:
                            break
                        outfile.write(data)
                os.remove(chunk_file)
        os.rmdir(self.temp_dir)

    async def start(self):
        start_time = time.time()
        try:
            if not self.check_range_support():
                console.print("[yellow]Server doesn't support partial content. Using single thread.[/yellow]")
                self.num_threads = 1

            self.file_size = self.get_file_size()
            self.prepare_chunks()
            self.temp_dir = Path(tempfile.mkdtemp(prefix="netripper_"))

            with Progress(
                SpinnerColumn(),
                "[progress.description]{task.description}",
                BarColumn(bar_width=None),
                "[progress.percentage]{task.percentage:>3.0f}%",
                "•",
                DownloadColumn(),
                "•",
                TransferSpeedColumn(),
                "•",
                TimeRemainingColumn(),
                console=console
            ) as progress:
                self.progress = progress
                total_size = sum(chunk['end'] - chunk['start'] + 1 for chunk in self.chunks)
                self.task_id = progress.add_task(
                    f"[cyan]Downloading {self.output_path.name}...",
                    total=total_size
                )

                with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
                    futures = [executor.submit(self.download_chunk, i) for i in range(self.num_threads)]
                    for future in as_completed(futures):
                        try:
                            future.result()
                        except Exception as e:
                            console.print(f"[red]Error in download thread: {str(e)}[/red]")
                            raise

                self.combine_files()
                console.print(f"\n[green]✓ Download complete: {self.output_path}[/green]")

        except KeyboardInterrupt:
            console.print("\n[yellow]Download paused. Use resume option to continue.[/yellow]")
            raise
        except Exception as e:
            console.print(f"\n[red]✗ Download failed: {str(e)}[/red]")
            raise
        finally:
            self.duration = time.time() - start_time

def signal_handler(sig, frame):
    console.print("\n[yellow]Download interrupted. Use resume option to continue later.[/yellow]")
    sys.exit(0)

async def main():
    signal.signal(signal.SIGINT, signal_handler)
    ripper = NetRipper()
    await ripper.show_main_menu()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass