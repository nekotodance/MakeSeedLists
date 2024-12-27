import sys
import os
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QListWidget, QListWidgetItem, QHBoxLayout, QStatusBar, QAbstractItemView, QTextEdit
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap, QIcon, QFont, QColor, QPainter, QImageReader
from datetime import datetime
import pvsubfunc
import pyperclip

# アプリ名称
WINDOW_TITLE = "Make Seed Lists"
# 設定ファイル
SETTINGS_FILE = "MakeSeedLists_settings.json"
# 設定ファイルのキー名
GEOMETRY_X = "geometry-x"
GEOMETRY_Y = "geometry-y"
GEOMETRY_W = "geometry-w"
GEOMETRY_H = "geometry-h"
# 定義値
THUMBNAIL_SIZE = 158
TEXT_HEIGHT = 48
NO_SEED_NUM = '---'

class ThumbnailViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    # 終了時処理
    def closeEvent(self, event):
        self.save_settings()
        super().closeEvent(event)

    #ドラッグ＆ドロップエンター時処理
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    #ドラッグ＆ドロップ時処理
    def dropEvent(self, event):
        new_files = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path) and self.is_image_file(path):
                if self.add_file_data(path):
                    new_files.append(path)
            elif os.path.isdir(path):
                new_files.extend(self.load_directory(path))
        # サムネイル部分はまず灰色で表示
        self.refresh_list()
        # memo:サムネイル生成（結構重いので非同期でマルチスレッド処理にしても良いかも）
        if new_files:
            self.generate_thumbnails(new_files)
        self.update_status_bar()

    # キー押下時処理
    def keyPressEvent(self, event):
        """deleteキーで選択アイテムを削除"""
        if event.key() == Qt.Key_Delete:
            self.delete_selected_items()
        super().keyPressEvent(event)

    #----------------------------------------
    #- 処理関数
    #----------------------------------------
    # UIの初期化
    def initUI(self):
        self.setWindowTitle(WINDOW_TITLE)
        self.setGeometry(100, 100, 848, 640)
        if not os.path.exists(SETTINGS_FILE):
            self.createSettingFile()
        self.load_settings()

        # ファイル情報を保持する辞書
        self.file_data = {}  # {file_path: (dummy_icon, size_text, seed, pixmap)}

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.layout = QVBoxLayout(main_widget)
        self.monospace_font = QFont("MS Gothic", 8)

        # ボタン部レイアウト
        button_layout = QHBoxLayout()
        self.sort_by_name_button = QPushButton("file名でソート")
        self.sort_by_seed_button = QPushButton("SEED番号でソート")
        self.delete_button = QPushButton("選択したファイルを削除")
        self.allclear_button = QPushButton("リストクリア")
        button_layout.addWidget(self.sort_by_name_button)
        button_layout.addWidget(self.sort_by_seed_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.allclear_button)
        self.layout.addLayout(button_layout)

        # サムネイルリスト部レイアウト
        self.thumbnail_list = QListWidget()
        self.thumbnail_list.setViewMode(QListWidget.IconMode)
        self.thumbnail_list.setIconSize(QSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE))
        self.thumbnail_list.setResizeMode(QListWidget.Adjust)
        self.thumbnail_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        #黒背景に白文字
        self.thumbnail_list.setStyleSheet("""
            QListWidget {
                background-color: black;
                color: white;
            }
            QListWidget::item {
                color: white;
            }
        """)
        self.layout.addWidget(self.thumbnail_list)

        # SEED番号コピー部レイアウト
        seed_copy_layout = QHBoxLayout()
        self.copy_seed_button = QPushButton("SEED番号リストを\n生成＆コピー")
        self.copy_seed_button.setFixedHeight(80)
        self.seedTextEdit = QTextEdit()
        font = self.seedTextEdit.font()
        font.setFamily('MS Gothic')
        self.seedTextEdit.setFont(font)
        self.seedTextEdit.setFixedHeight(80)
        seed_copy_layout.addWidget(self.copy_seed_button)
        seed_copy_layout.addWidget(self.seedTextEdit)
        self.layout.addLayout(seed_copy_layout)

        # ステータスバー
        self.statusBar = QStatusBar()
        self.statusBar.setStyleSheet("color: white; font-size: 14px; background-color: #31363b;")
        self.setStatusBar(self.statusBar)

        # シグナルの接続
        self.sort_by_name_button.clicked.connect(self.sort_by_name)
        self.sort_by_seed_button.clicked.connect(self.sort_by_seed)
        self.delete_button.clicked.connect(self.delete_selected_items)
        self.allclear_button.clicked.connect(self.all_clear_items)
        self.copy_seed_button.clicked.connect(self.copy_seed_list)

        self.setAcceptDrops(True)
        self.update_status_bar()

    #設定ファイルの初期値作成
    def createSettingFile(self):
        self.save_settings()

    #設定ファイルのロード
    def load_settings(self):
        geox = pvsubfunc.read_value_from_config(SETTINGS_FILE, GEOMETRY_X)
        geoy = pvsubfunc.read_value_from_config(SETTINGS_FILE, GEOMETRY_Y)
        geow = pvsubfunc.read_value_from_config(SETTINGS_FILE, GEOMETRY_W)
        geoh = pvsubfunc.read_value_from_config(SETTINGS_FILE, GEOMETRY_H)
        if any(val is None for val in [geox, geoy, geow, geoh]):
            self.setGeometry(100, 100, 848, 640)    #位置とサイズ
        else:
            self.setGeometry(geox, geoy, geow, geoh)    #位置とサイズ

    #設定ファイルのセーブ
    def save_settings(self):
        pvsubfunc.write_value_to_config(SETTINGS_FILE, GEOMETRY_X, self.geometry().x())
        pvsubfunc.write_value_to_config(SETTINGS_FILE, GEOMETRY_Y, self.geometry().y())
        pvsubfunc.write_value_to_config(SETTINGS_FILE, GEOMETRY_W, self.geometry().width())
        pvsubfunc.write_value_to_config(SETTINGS_FILE, GEOMETRY_H, self.geometry().height())

    # ステータスバー更新
    def update_status_bar(self):
        file_count = len(self.file_data)
        self.statusBar.showMessage(f"登録されたファイル数: {file_count}")


    # 対象画像ファイルチェック
    def is_image_file(self, path):
        return any(path.lower().endswith(ext) for ext in [".png", ".jpg", ".webp"])

    # SDの画像ファイルからSEED番号（文字列）の取得
    def get_seednum_from_file(self, file_path):
        seed = NO_SEED_NUM
        comment = ""
        try:
            if file_path.lower().endswith(('.jpg', '.jpeg', '.webp')):
                comment = str(pvsubfunc.get_jpg_comment(file_path))
            elif file_path.lower().endswith(('.png')):
                reader = QImageReader(file_path)
                comment = str(reader.text("parameters"))
            res = pvsubfunc.extract_between(comment, "Seed: ", ", Size:")
            if res:
                seed = str(res[0])
        except Exception:
            return NO_SEED_NUM
        return seed

    # ファイルリストへの追加（ただし重複時はスキップ）
    def add_file_data(self, file_path):
        if file_path in self.file_data:
            return False  # 重複をスキップ
        try:
            pixmap = QPixmap(file_path)
            size_text = f"{pixmap.width()}x{pixmap.height()}" if not pixmap.isNull() else "Unknown size"
        except Exception:
            size_text = "Unknown size"
        seed = self.get_seednum_from_file(file_path)
        dummy_icon = QPixmap(160, 160)
        dummy_icon.fill(Qt.gray)  # ダミーサムネイル
        self.file_data[file_path] = (QIcon(dummy_icon), size_text, seed, None)
        return True

    # ドロップ時のファイルリスト取得
    def load_directory(self, dir_path):
        new_files = []
        for root, _, files in os.walk(dir_path):
            for file in files:
                full_path = os.path.join(root, file).replace("\\", "/")
                if self.is_image_file(full_path) and self.add_file_data(full_path):
                    new_files.append(full_path)
        return new_files

    # サムネイルリストの作成（まずは灰色ダミー画像で）
    def refresh_list(self):
        self.thumbnail_list.clear()
        for file_path, (dummy_icon, size_text, seed, _) in self.file_data.items():
            item = QListWidgetItem(dummy_icon, self.format_item_text(file_path, size_text, seed))
            item.setData(Qt.UserRole, file_path)
            item.setFont(self.monospace_font)  # MSゴシックフォントを設定
            item.setSizeHint(QSize(THUMBNAIL_SIZE + 2, THUMBNAIL_SIZE + 2 + TEXT_HEIGHT))  # 各リスト項目の最小幅を160pxに設定
            self.thumbnail_list.addItem(item)

    # リストのテキスト部分文字列の生成
    def format_item_text(self, file_path, size_text, seed):
        file_name = os.path.basename(file_path)
        fname, fext = os.path.splitext(file_name)
        formatted_name = self.truncate_file_name(fname)
        return f"{formatted_name}\n{fext.replace('.', '')} : {size_text}\n{str(seed)}"

    # ファイル名が長すぎる場合省略する
    def truncate_file_name(self, file_name):
        # 現状は拡張子を除き最大で20文字、20文字以上なら先頭8文字..終端10文字としている
        # 好みもあるし、サムネイルサイズとあわせて調整が必要
        if len(file_name) <= 20:
            return file_name
        return f"{file_name[:8]}..{file_name[-10:]}"

    # サムネイルリストの上下幅を固定するためのパディング処理
    def resize_with_padding(self, original_pixmap, target_width, target_height):
        original_width = original_pixmap.width()
        original_height = original_pixmap.height()
        new_pixmap = QPixmap(target_width, target_height)
        new_pixmap.fill(QColor(25, 25, 25))  # 濃い灰色に塗りつぶし
        painter = QPainter(new_pixmap)
        painter.drawPixmap(
            (target_width - original_width) // 2,
            (target_height - original_height) // 2,
            original_pixmap
        )
        painter.end()
        return new_pixmap

    # サムネイル生成処理
    def generate_thumbnails(self, file_paths):
        # memo:サムネイル生成（結構重いので非同期でマルチスレッド処理にしても良いかも）
        for file_path in file_paths:
            # 同期的にサムネイル生成
            iconpixmap = QPixmap(file_path).scaled(THUMBNAIL_SIZE, THUMBNAIL_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            list_pixmap = self.resize_with_padding(iconpixmap, THUMBNAIL_SIZE, THUMBNAIL_SIZE)
            self.update_thumbnail(file_path, list_pixmap)

    # サムネイル生成完了時の登録処理
    def update_thumbnail(self, file_path, pixmap):
        if file_path in self.file_data:
            self.file_data[file_path] = (
                QIcon(pixmap), self.file_data[file_path][1], self.file_data[file_path][2], pixmap
            )
        for i in range(self.thumbnail_list.count()):
            item = self.thumbnail_list.item(i)
            if item.data(Qt.UserRole) == file_path:
                item.setIcon(QIcon(pixmap))
                break

    # 選択したアイテムの削除処理
    def delete_selected_items(self):
        for item in self.thumbnail_list.selectedItems():
            file_path = item.data(Qt.UserRole)
            if file_path in self.file_data:
                del self.file_data[file_path]
            self.thumbnail_list.takeItem(self.thumbnail_list.row(item))
        self.update_status_bar()

    # すべてのアイテムの削除処理
    def all_clear_items(self):
        self.file_data.clear()
        self.thumbnail_list.clear()
        # ステータスバーを更新
        self.update_status_bar()

    # シードリストの生成と、処理結果の表示
    def copy_seed_list(self):
        seedlists = [item[1][2] for item in self.file_data.items()]
        filterlists = [item for item in seedlists if item not in ("", NO_SEED_NUM)]
        #unique_lists = list(set(filterlists))
        seen = set()
        unique_lists = []
        for item in filterlists:
            if item not in seen:
                unique_lists.append(item)
                seen.add(item)
        result = ",".join(unique_lists)
        self.seedTextEdit.setText(result)
        pyperclip.copy(result)

        item_count = len(seedlists)         # 全SEED項目数
        filter_count = len(filterlists)     # 無効なSEED番号を除いた項目数
        unique_count = len(unique_lists)    # 重複するSEEDを除いた項目数
        if item_count == filter_count and filter_count == unique_count:
            mes = f"{unique_count}ファイルのシード番号をコピーしました"
        elif item_count == filter_count and filter_count != unique_count:
            mes = f"重複する{filter_count-unique_count}ファイルを除く、{unique_count}ファイルのシード番号をコピーしました"
        elif item_count != filter_count and filter_count == unique_count:
            mes = f"SEED番号が不明な{item_count-filter_count}ファイルを除く、{unique_count}ファイルのシード番号をコピーしました"
        else:
            mes = f"SEED番号が不明な{item_count-filter_count}ファイル、重複する{filter_count-unique_count}ファイルを除く、{unique_count}ファイルのシード番号をコピーしました"
        self.statusBar.showMessage(mes)

    # ファイル名でのソート処理
    def sort_by_name(self):
        sorted_files = sorted(self.file_data.items(), key=lambda x: os.path.basename(x[0]))
        self.file_data = dict(sorted_files)
        self.refresh_list()
        self.update_status_bar()

    # シード番号でのソート処理
    def sort_by_seed(self):
        sorted_files = sorted(self.file_data.items(), key=lambda x: x[1][2])  # SEED番号でソート
        self.file_data = dict(sorted_files)
        self.refresh_list()
        self.update_status_bar()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = ThumbnailViewer()
    viewer.show()
    sys.exit(app.exec_())
