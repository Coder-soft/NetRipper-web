import os
import math
import threading
import requests
from tqdm import tqdm

def download_chunk(url, start, end, filename, thread_index, progress_bar):
    headers = {'Range': f'bytes={start}-{end}'}
    print(f"[Thread {thread_index}] Downloading bytes: {start}-{end}")
    response = requests.get(url, headers=headers, stream=True)
    if response.status_code not in (200, 206):
        print(f"[Thread {thread_index}] Error: Server responded with {response.status_code}")
        return
    with open(filename, "r+b") as f:
        f.seek(start)
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                # Update the shared progress bar by the size of this chunk.
                progress_bar.update(len(chunk))
    print(f"[Thread {thread_index}] Finished downloading chunk.")

def download_file(url, num_threads=8):
    # Send a HEAD request to determine file size.
    head = requests.head(url)
    file_size = int(head.headers.get('content-length', 0))
    if file_size == 0:
        print("Could not retrieve file size. The server may not support HEAD requests or ranged downloads.")
        num_threads = 1  # Fallback to single-threaded download

    filename = url.split("/")[-1] or "downloaded_file"
    print(f"Downloading {filename} ({file_size} bytes) using {num_threads} threads.")

    # Pre-create the file with the expected size.
    with open(filename, "wb") as f:
        f.truncate(file_size)

    # Create a shared progress bar using tqdm.
    progress_bar = tqdm(total=file_size, unit='B', unit_scale=True, desc=filename)

    part_size = math.ceil(file_size / num_threads)
    threads = []

    # Start download threads for each chunk.
    for i in range(num_threads):
        start = i * part_size
        end = file_size - 1 if i == num_threads - 1 else min(start + part_size - 1, file_size - 1)
        t = threading.Thread(target=download_chunk, args=(url, start, end, filename, i+1, progress_bar))
        t.start()
        threads.append(t)

    # Wait for all threads to complete.
    for t in threads:
        t.join()

    progress_bar.close()
    print(f"Download of {filename} completed.")

if __name__ == '__main__':
    download_url = input("Enter the direct download URL: ").strip()
    thread_input = input("Enter number of threads to use (default 8): ").strip()
    num_threads = int(thread_input) if thread_input.isdigit() else 8

    download_file(download_url, num_threads)
