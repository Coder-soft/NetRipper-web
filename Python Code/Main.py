import os
import math
import threading
import time
import requests
import sys

from PyQt5.QtCore import QThread, pyqtSignal, QPropertyAnimation, QEasingCurve, QSettings, Qt
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QProgressBar, QFileDialog, QCheckBox)

#############################################
# Custom Thread Selector Widget
#############################################

class ThreadSelector(QWidget):
    def __init__(self, min_value=1, max_value=32, initial_value=8, parent=None):
        super().__init__(parent)
        self.min_value = min_value
        self.max_value = max_value
        self.value = initial_value
        self.initUI()

    def initUI(self):
        layout = QHBoxLayout()
        self.setLayout(layout)
        self.decrement_button = QPushButton("–")
        self.decrement_button.clicked.connect(self.decrement)
        self.increment_button = QPushButton("+")
        self.increment_button.clicked.connect(self.increment)
        self.value_display = QLineEdit(str(self.value))
        self.value_display.setReadOnly(True)
        self.value_display.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.decrement_button)
        layout.addWidget(self.value_display)
        layout.addWidget(self.increment_button)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        self.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: #cccccc;
                font-size: 16px;
                font-weight: bold;
                min-width: 30px;
                max-width: 30px;
                min-height: 30px;
                max-height: 30px;
                border-radius: 15px;
            }
            QPushButton:hover {
                background-color: #aaaaaa;
            }
            QLineEdit {
                border: 2px solid #ccc;
                border-radius: 10px;
                background-color: #ffffff;
                font-size: 14px;
                padding: 5px;
                max-width: 50px;
            }
        """)

    def decrement(self):
        if self.value > self.min_value:
            self.value -= 1
            self.value_display.setText(str(self.value))

    def increment(self):
        if self.value < self.max_value:
            self.value += 1
            self.value_display.setText(str(self.value))

    def getValue(self):
        return self.value


#############################################
# Worker thread for downloading the file
#############################################

class DownloadWorker(QThread):
    # Signal parameters: downloaded bytes, total file size, current speed (B/s)
    progress_signal = pyqtSignal(int, int, float)
    status_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)

    def __init__(self, url, num_threads=8, save_folder=""):
        super().__init__()
        self.url = url
        self.num_threads = num_threads
        self.save_folder = save_folder if save_folder else os.getcwd()
        self._downloaded = 0
        self._lock = threading.Lock()

    def update_progress(self, bytes_downloaded):
        with self._lock:
            self._downloaded += bytes_downloaded

    def download_chunk(self, url, start, end, filename):
        headers = {'Range': f'bytes={start}-{end}'}
        try:
            response = requests.get(url, headers=headers, stream=True)
            if response.status_code not in (200, 206):
                self.status_signal.emit(f"Error: HTTP {response.status_code} while downloading chunk.")
                return
            with open(filename, "r+b") as f:
                f.seek(start)
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        self.update_progress(len(chunk))
        except Exception as e:
            self.status_signal.emit(f"Exception: {e}")

    def run(self):
        try:
            head = requests.head(self.url)
            file_size = int(head.headers.get('content-length', 0))
        except Exception as e:
            self.status_signal.emit(f"Failed to get file size: {e}")
            return

        if file_size == 0:
            self.status_signal.emit("Could not retrieve file size.")
            return

        filename_only = self.url.split("/")[-1] or "downloaded_file"
        filename = os.path.join(self.save_folder, filename_only)

        with open(filename, "wb") as f:
            f.truncate(file_size)

        self.status_signal.emit(f"Downloading {filename_only} ({file_size} bytes) with {self.num_threads} threads.")
        part_size = math.ceil(file_size / self.num_threads)
        threads = []
        start_time = time.time()

        def monitor_progress():
            while any(t.is_alive() for t in threads):
                elapsed = time.time() - start_time
                with self._lock:
                    downloaded = self._downloaded
                speed = downloaded / elapsed if elapsed > 0 else 0
                self.progress_signal.emit(downloaded, file_size, speed)
                time.sleep(0.5)
            elapsed = time.time() - start_time
            with self._lock:
                downloaded = self._downloaded
            speed = downloaded / elapsed if elapsed > 0 else 0
            self.progress_signal.emit(downloaded, file_size, speed)

        monitor_thread = threading.Thread(target=monitor_progress)
        monitor_thread.start()

        for i in range(self.num_threads):
            start_byte = i * part_size
            end_byte = file_size - 1 if i == self.num_threads - 1 else min(start_byte + part_size - 1, file_size - 1)
            t = threading.Thread(target=self.download_chunk, args=(self.url, start_byte, end_byte, filename))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        monitor_thread.join()
        total_time = time.time() - start_time
        self.finished_signal.emit(f"Download completed: {filename} in {total_time:.2f} seconds")


#############################################
# Main GUI Application
#############################################

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Net Ripper")
        self.setFixedSize(650, 450)
        self.settings = QSettings("MyCompany", "Net Ripper")
        self.initUI()
        self.download_worker = None

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        title = QLabel("Net Ripper - By Xe0n")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        self.url_label = QLabel("Download URL:")
        self.url_input = QLineEdit()
        layout.addWidget(self.url_label)
        layout.addWidget(self.url_input)

        self.threads_label = QLabel("Number of Threads:")
        layout.addWidget(self.threads_label)
        self.thread_selector = ThreadSelector(initial_value=8)
        layout.addWidget(self.thread_selector)

        folder_layout = QHBoxLayout()
        self.folder_label = QLabel("Save Location:")
        self.folder_input = QLineEdit()
        self.folder_button = QPushButton("Browse")
        self.folder_button.clicked.connect(self.browse_folder)
        folder_layout.addWidget(self.folder_label)
        folder_layout.addWidget(self.folder_input)
        folder_layout.addWidget(self.folder_button)
        layout.addLayout(folder_layout)

        self.remember_checkbox = QCheckBox("Remember save location")
        layout.addWidget(self.remember_checkbox)
        saved_folder = self.settings.value("save_folder", "")
        if saved_folder:
            self.folder_input.setText(saved_folder)
            self.remember_checkbox.setChecked(True)

        self.start_button = QPushButton("Start Download")
        self.start_button.clicked.connect(self.start_download)
        layout.addWidget(self.start_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Status: Idle")
        layout.addWidget(self.status_label)

        self.setStyleSheet("""
            QWidget {
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
                background-color: #f5f5f5;
            }
            QLineEdit, QPushButton {
                border-radius: 10px;
                border: 2px solid #ccc;
                padding: 5px;
            }
            QPushButton {
                background-color: #5cb85c;
                color: white;
            }
            QPushButton:hover {
                background-color: #4cae4c;
            }
            QProgressBar {
                border-radius: 10px;
                background-color: #eee;
                text-align: center;
                height: 25px;
            }
            QProgressBar::chunk {
                border-radius: 10px;
                background-color: #337ab7;
            }
            QLabel {
                margin: 5px;
            }
            QCheckBox {
                margin-left: 5px;
            }
        """)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Save Folder", os.getcwd())
        if folder:
            self.folder_input.setText(folder)

    def start_download(self):
        url = self.url_input.text().strip()
        if not url:
            self.status_label.setText("Status: Please enter a valid URL.")
            return

        num_threads = self.thread_selector.getValue()
        save_folder = self.folder_input.text().strip()

        if self.remember_checkbox.isChecked() and save_folder:
            self.settings.setValue("save_folder", save_folder)
        else:
            self.settings.remove("save_folder")

        self.progress_bar.setValue(0)
        self.status_label.setText("Status: Starting download...")
        self.start_button.setEnabled(False)

        self.download_worker = DownloadWorker(url, num_threads, save_folder)
        self.download_worker.progress_signal.connect(self.update_progress)
        self.download_worker.status_signal.connect(self.update_status)
        self.download_worker.finished_signal.connect(self.download_finished)
        self.download_worker.start()

    def update_progress(self, downloaded, file_size, speed):
        percent = int((downloaded / file_size) * 100)
        self.progress_bar.setValue(percent)
        eta = (file_size - downloaded) / speed if speed > 0 else 0
        self.status_label.setText(f"Downloaded: {percent}% | Speed: {speed/1024:.2f} KB/s | ETA: {eta:.2f}s")

    def update_status(self, message):
        self.status_label.setText("Status: " + message)

    def download_finished(self, message):
        self.status_label.setText("Status: " + message)
        self.start_button.setEnabled(True)
        animation = QPropertyAnimation(self.progress_bar, b"windowOpacity")
        animation.setDuration(1000)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.setEasingCurve(QEasingCurve.InOutQuad)
        animation.start()
        self.progress_bar.setValue(0)
        self.progress_bar.setWindowOpacity(1.0)


#############################################
# Application Entry Point
#############################################

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
