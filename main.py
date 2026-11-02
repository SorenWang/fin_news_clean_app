import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QTextEdit,
                             QFileDialog, QLineEdit, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import logging

from file_reader import WenJianDuQu
from basic_cleaner import JiChuQingXi
from llm_cleaner import DaMoXingQingXi
from utils_logger import setup_logger, TongJiXinXi

logger = setup_logger()


class QingXiWorker(QThread):
    progress_signal = pyqtSignal(str)
    finish_signal = pyqtSignal(list)
    error_signal = pyqtSignal(str)

    def __init__(self, df, use_llm=False, llm_url="http://localhost:8080"):
        super().__init__()
        self.df = df
        self.use_llm = use_llm
        self.llm_url = llm_url

    def run(self):
        try:
            stats = TongJiXinXi()
            stats.start_timer()

            logger.info("开始基础清洗")
            self.progress_signal.emit("正在进行基础清洗...")
            cleaner = JiChuQingXi()
            df_cleaned = cleaner.clean_all(self.df)

            text_list = df_cleaned['content'].tolist()
            stats.total_count = len(text_list)

            if self.use_llm:
                self.progress_signal.emit("正在调用LLM进行智能清洗...")
                logger.info("启动LLM清洗")
                llm_cleaner = DaMoXingQingXi(base_url=self.llm_url)

                if not llm_cleaner.check_service_status():
                    logger.warning("LLM服务未启动，跳过LLM清洗")
                    self.progress_signal.emit("警告: LLM服务未连接，仅完成基础清洗")
                else:
                    text_list = llm_cleaner.clean_with_llm(text_list)

            stats.clean_count = len(text_list)
            stats.stop_timer()

            report = stats.generate_report()
            logger.info(f"清洗完成报告: {report}")

            self.finish_signal.emit(text_list)

        except Exception as e:
            logger.error(f"清洗流程异常: {str(e)}", exc_info=True)
            self.error_signal.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("金融文本智能清洗工具")
        self.setGeometry(100, 100, 900, 700)

        self.file_path = None
        self.result_data = None

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 文件选择区域
        file_layout = QHBoxLayout()
        self.file_label = QLabel("未选择文件")
        self.file_label.setStyleSheet("color: gray;")
        select_btn = QPushButton("选择文件")
        select_btn.clicked.connect(self.select_file)
        file_layout.addWidget(QLabel("输入文件:"))
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(select_btn)
        main_layout.addLayout(file_layout)

        # LLM配置
        llm_layout = QHBoxLayout()
        self.llm_input = QLineEdit("http://localhost:8080")
        self.use_llm_check = QPushButton("启用LLM清洗")
        self.use_llm_check.setCheckable(True)
        self.use_llm_check.setStyleSheet("""
            QPushButton:checked { background-color: #4CAF50; color: white; }
            QPushButton:!checked { background-color: #f0f0f0; }
        """)
        llm_layout.addWidget(QLabel("LLM地址:"))
        llm_layout.addWidget(self.llm_input)
        llm_layout.addWidget(self.use_llm_check)
        main_layout.addLayout(llm_layout)

        # 控制按钮
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始清洗")
        self.start_btn.clicked.connect(self.start_cleaning)
        self.start_btn.setEnabled(False)
        self.export_btn = QPushButton("导出结果")
        self.export_btn.clicked.connect(self.export_result)
        self.export_btn.setEnabled(False)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.export_btn)
        main_layout.addLayout(btn_layout)

        # 状态显示
        # 状态显示
        self.status_label = QLabel("就绪")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-weight: bold; padding: 10px;")
        main_layout.addWidget(self.status_label)


        # 结果显示
        main_layout.addWidget(QLabel("处理结果:"))
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        main_layout.addWidget(self.result_text)

        # 日志显示
        main_layout.addWidget(QLabel("运行日志:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setStyleSheet("background-color: #f5f5f5; font-family: Consolas; font-size: 9pt;")
        main_layout.addWidget(self.log_text)

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择文件", "", "支持的文件 (*.csv *.txt *.xlsx)"
        )
        if file_path:
            self.file_path = file_path
            self.file_label.setText(file_path.split('/')[-1])
            self.file_label.setStyleSheet("color: black;")
            self.start_btn.setEnabled(True)
            logger.info(f"选择文件: {file_path}")

    def start_cleaning(self):
        if not self.file_path:
            QMessageBox.warning(self, "警告", "请先选择文件!")
            return

        self.start_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.status_label.setText("处理中...")
        self.result_text.clear()

        try:
            reader = WenJianDuQu()
            df = reader.read_file(self.file_path)

            if df is None or df.empty:
                QMessageBox.warning(self, "错误", "文件为空或格式不正确")
                self.start_btn.setEnabled(True)
                return

            use_llm = self.use_llm_check.isChecked()
            llm_url = self.llm_input.text().strip()

            self.worker = QingXiWorker(df, use_llm, llm_url)
            self.worker.progress_signal.connect(self.update_progress)
            self.worker.finish_signal.connect(self.show_result)
            self.worker.error_signal.connect(self.show_error)
            self.worker.start()

        except FileNotFoundError as e:
            logger.error(f"文件不存在: {e}")
            QMessageBox.critical(self, "错误", f"文件不存在: {str(e)}")
            self.start_btn.setEnabled(True)
        except Exception as e:
            logger.error(f"启动失败: {e}", exc_info=True)
            QMessageBox.critical(self, "错误", f"启动失败: {str(e)}")
            self.start_btn.setEnabled(True)

    def update_progress(self, msg):
        self.status_label.setText(msg)
        self.log_text.append(f"[{self.get_time()}] {msg}")

    def show_result(self, text_list):
        self.result_data = text_list
        self.status_label.setText(f"清洗完成! 共{len(text_list)}条")
        self.start_btn.setEnabled(True)
        self.export_btn.setEnabled(True)

        preview = '\n'.join(text_list[:20])
        if len(text_list) > 20:
            preview += f"\n\n... 还有{len(text_list) - 20}条"
        self.result_text.setText(preview)

        self.log_text.append(f"[{self.get_time()}] 处理完成")
        logger.info(f"清洗完成，共{len(text_list)}条数据")

    def show_error(self, error_msg):
        self.status_label.setText("处理失败")
        self.start_btn.setEnabled(True)
        QMessageBox.critical(self, "错误", f"处理失败:\n{error_msg}")
        self.log_text.append(f"[{self.get_time()}] 错误: {error_msg}")

    def export_result(self):
        if not self.result_data:
            QMessageBox.warning(self, "警告", "没有可导出的数据")
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存结果", "", "文本文件 (*.txt);;CSV文件 (*.csv)"
        )

        if save_path:
            try:
                if save_path.endswith('.csv'):
                    import pandas as pd
                    df = pd.DataFrame({'content': self.result_data})
                    df.to_csv(save_path, index=False, encoding='utf-8-sig')
                else:
                    with open(save_path, 'w', encoding='utf-8') as f:
                        for line in self.result_data:
                            f.write(line + '\n')

                logger.info(f"结果已导出到: {save_path}")
                QMessageBox.information(self, "成功", f"已保存到:\n{save_path}")
            except Exception as e:
                logger.error(f"导出失败: {e}")
                QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")

    def get_time(self):
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
