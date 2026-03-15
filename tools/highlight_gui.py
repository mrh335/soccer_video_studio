"""Simple desktop GUI for the goalie highlight extractor.

Requirements:
    pip install pyside6 opencv-python numpy
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import cv2


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Goalie Highlight Tool")
        self.resize(1080, 720)

        self.video_path = QLineEdit()
        self.csv_path = QLineEdit("segments.csv")
        self.render_path = QLineEdit("highlight.mp4")
        self.roi = QLineEdit("0.2,0.25,0.6,0.5")
        self.threshold = QLineEdit("7.0")
        self.min_len = QLineEdit("2.0")
        self.pre_pad = QLineEdit("4.0")
        self.post_pad = QLineEdit("3.0")
        self.merge_gap = QLineEdit("4.0")

        self.preview_label = QLabel("Video preview")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(640, 360)
        self.preview_label.setStyleSheet("border: 1px solid #999; background: #111; color: #ddd;")

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Start (s)", "End (s)", "Duration (s)"])

        root = QWidget()
        self.setCentralWidget(root)

        outer = QHBoxLayout(root)
        controls = self._build_controls()
        outer.addWidget(controls, 1)

        right = QVBoxLayout()
        right.addWidget(self.preview_label, 3)
        right.addWidget(self.table, 2)
        right.addWidget(self.log, 2)
        outer.addLayout(right, 2)

    def _build_controls(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        input_group = QGroupBox("Input / Output")
        input_form = QFormLayout(input_group)

        row_video = QHBoxLayout()
        row_video.addWidget(self.video_path)
        btn_video = QPushButton("Browse...")
        btn_video.clicked.connect(self.pick_video)
        row_video.addWidget(btn_video)
        input_form.addRow("Video", self._wrap(row_video))

        input_form.addRow("Segments CSV", self.csv_path)
        input_form.addRow("Render output", self.render_path)

        params_group = QGroupBox("Detection Parameters")
        grid = QGridLayout(params_group)
        grid.addWidget(QLabel("ROI (x,y,w,h)"), 0, 0)
        grid.addWidget(self.roi, 0, 1)
        grid.addWidget(QLabel("Threshold"), 1, 0)
        grid.addWidget(self.threshold, 1, 1)
        grid.addWidget(QLabel("Min len"), 2, 0)
        grid.addWidget(self.min_len, 2, 1)
        grid.addWidget(QLabel("Pre pad"), 3, 0)
        grid.addWidget(self.pre_pad, 3, 1)
        grid.addWidget(QLabel("Post pad"), 4, 0)
        grid.addWidget(self.post_pad, 4, 1)
        grid.addWidget(QLabel("Merge gap"), 5, 0)
        grid.addWidget(self.merge_gap, 5, 1)

        btn_preview = QPushButton("Preview ROI")
        btn_preview.clicked.connect(self.preview_roi)

        btn_analyze = QPushButton("Run Analysis")
        btn_analyze.clicked.connect(self.run_analysis)

        btn_render = QPushButton("Run Analysis + Render Video")
        btn_render.clicked.connect(lambda: self.run_analysis(render=True))

        layout.addWidget(input_group)
        layout.addWidget(params_group)
        layout.addWidget(btn_preview)
        layout.addWidget(btn_analyze)
        layout.addWidget(btn_render)
        layout.addStretch(1)
        return panel

    @staticmethod
    def _wrap(layout: QHBoxLayout) -> QWidget:
        wrapper = QWidget()
        wrapper.setLayout(layout)
        return wrapper

    def pick_video(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Choose video", "", "Video Files (*.mp4 *.mov *.mkv *.avi)")
        if file_path:
            self.video_path.setText(file_path)
            self.csv_path.setText(str(Path(file_path).with_name("segments.csv")))
            self.render_path.setText(str(Path(file_path).with_name("highlight.mp4")))

    def preview_roi(self) -> None:
        path = self.video_path.text().strip()
        if not path:
            QMessageBox.warning(self, "Missing video", "Please choose a video first.")
            return

        cap = cv2.VideoCapture(path)
        ok, frame = cap.read()
        cap.release()
        if not ok:
            QMessageBox.critical(self, "Read error", "Could not read the first frame.")
            return

        try:
            x, y, w, h = [float(v.strip()) for v in self.roi.text().split(",")]
        except ValueError:
            QMessageBox.warning(self, "Bad ROI", "ROI must be four comma-separated numbers.")
            return

        fh, fw = frame.shape[:2]
        x1, y1, rw, rh = int(x * fw), int(y * fh), int(w * fw), int(h * fh)
        x2, y2 = x1 + rw, y1 + rh
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 3)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(image).scaled(
            self.preview_label.width(),
            self.preview_label.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.preview_label.setPixmap(pixmap)

    def run_analysis(self, render: bool = False) -> None:
        path = self.video_path.text().strip()
        if not path:
            QMessageBox.warning(self, "Missing video", "Please choose a video first.")
            return

        script = Path(__file__).with_name("extract_highlights.py")
        cmd = [
            sys.executable,
            str(script),
            path,
            "--roi",
            self.roi.text().strip(),
            "--threshold",
            self.threshold.text().strip(),
            "--min-len",
            self.min_len.text().strip(),
            "--pre-pad",
            self.pre_pad.text().strip(),
            "--post-pad",
            self.post_pad.text().strip(),
            "--merge-gap",
            self.merge_gap.text().strip(),
            "--segments-csv",
            self.csv_path.text().strip(),
        ]
        if render:
            cmd.extend(["--render", self.render_path.text().strip()])

        self.log.appendPlainText("$ " + " ".join(cmd))
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            if result.stdout:
                self.log.appendPlainText(result.stdout)
            self.load_segments(Path(self.csv_path.text().strip()))
            if render:
                QMessageBox.information(self, "Done", "Analysis and render completed.")
            else:
                QMessageBox.information(self, "Done", "Analysis completed.")
        except subprocess.CalledProcessError as exc:
            self.log.appendPlainText(exc.stdout or "")
            self.log.appendPlainText(exc.stderr or "")
            QMessageBox.critical(self, "Run failed", "Analysis failed. See log for details.")

    def load_segments(self, csv_path: Path) -> None:
        if not csv_path.exists():
            return
        with csv_path.open("r", encoding="utf-8") as f:
            rows = list(csv.reader(f))

        self.table.setRowCount(0)
        for row in rows[1:]:
            idx = self.table.rowCount()
            self.table.insertRow(idx)
            for col, value in enumerate(row[:3]):
                self.table.setItem(idx, col, QTableWidgetItem(value))


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
